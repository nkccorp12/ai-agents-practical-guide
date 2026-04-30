### 11.5 Identity and Auth

In multi-user agent systems an agent calls downstream tools, MCP servers and APIs whose access is bound to the permissions of a specific human. When the agent operates under a technical service identity the user context is lost. The result is privilege escalation, the classic confused-deputy problem, and unusable audit logs. In early 2026 it was explicitly documented that Microsoft Foundry Agents in M365 Copilot do not propagate OAuth identity but operate under app identity instead [Source: ceposta, https://blog.christianposta.com/explaining-on-behalf-of-for-ai-agents/].

The established remedy is OAuth On-Behalf-Of (OBO) per RFC 8693 (Token Exchange) with the `act` claim from RFC 9068. The agent receives a delegated access token from the authorization server that carries both the user (`sub`) and the agent (`act.sub`). Resource servers validate both identities and reduce scopes to the intersection of user permissions, agent permissions, and requested scopes (capability attenuation). Multi-hop delegation (Agent A -> Agent B -> API) nests `act` recursively.

```python
# RFC 8693 Token Exchange -- agent swaps user token for delegated OBO token
import httpx, time
from jose import jwt

def exchange_for_obo(user_token: str, target_audience: str, agent_id: str) -> str:
    resp = httpx.post(
        "https://auth.example.com/oauth2/token",
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
            "subject_token": user_token,
            "subject_token_type": "urn:ietf:params:oauth:token-type:access_token",
            "actor_token": agent_credential(agent_id),
            "actor_token_type": "urn:ietf:params:oauth:token-type:access_token",
            "resource": target_audience,
            "scope": "read:contacts write:notes",
        },
        timeout=5,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]

def verify_obo(access_token: str, jwks) -> dict:
    claims = jwt.decode(access_token, jwks, algorithms=["RS256"])
    if "act" not in claims or claims["act"].get("sub") is None:
        raise PermissionError("Agent acting on behalf of user required")
    if claims["exp"] < time.time():
        raise PermissionError("Token expired")
    return claims  # claims["sub"] = user, claims["act"]["sub"] = agent

# Resource server: branch audit on agent path
claims = verify_obo(token, jwks)
audit.record(user=claims["sub"], agent=claims["act"]["sub"],
             scopes=claims["scope"].split(), action="crm.write")
```

Anti-patterns:
- Service-account token with superuser rights as a shared agent identity, so every tool call looks like the same bot.
- Embedding user tokens in system messages or prompts, where they end up in logs and KV cache.

Checklist:
- [ ] Every tool call carries user identity (`sub`) AND agent identity (`act.sub`).
- [ ] Scopes reduced to `intersection(user, agent, requested)`.
- [ ] PKCE mandatory, authorization codes single-use.
- [ ] Consent UI names the agent explicitly.
- [ ] Audit log persists user+agent+action+tool+resource per call.

---

### 11.6 Secret Handling

MCP servers aggregate dozens of API keys, DB passwords, and OAuth tokens, often in unencrypted config files. Tokens accidentally end up in prompts, logs, memory, or KV caches. OWASP MCP01:2025 (token mismanagement and secret exposure) is the most common MCP vulnerability in 2026 [Source: https://www.willvelida.com/posts/preventing-mcp01-token-mismanagement-secret-exposure]. The guiding principle: the agent process holds no long-lived credential at runtime, only session-scoped tokens with hard expiry of 15 min, fetched from a vault.

```python
# Vault-backed runtime fetch, short TTL, never visible in the prompt
import time, hmac
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

cred = DefaultAzureCredential()  # managed identity in prod
kv = SecretClient(vault_url="https://kv.example.net", credential=cred)

class SessionSecret:
    """Session-scoped token, TTL <= 15 min (OWASP MCP01:2025)."""
    HARD_EXPIRY = 15 * 60

    def __init__(self, name: str):
        self.name, self._val, self._exp = name, None, 0

    def get(self) -> str:
        if time.time() > self._exp:
            self._val = kv.get_secret(self.name).value
            self._exp = time.time() + self.HARD_EXPIRY
        return self._val

def authorized(presented: str, expected: str) -> bool:
    # constant-time compare against timing attacks
    return hmac.compare_digest(presented.encode(), expected.encode())

# OTel redaction: never export auth headers in spans
def redact_span(span):
    for k in ("http.request.header.authorization", "tool_call.arguments"):
        if span.attributes.get(k):
            span.set_attribute(k, "[REDACTED]")
```

Anti-patterns:
- API keys as environment variables that the agent can read directly via `os.environ` (they leak into tool outputs and stack traces).
- Secrets in system messages or tool descriptions, where they persist in KV cache and audit log.

Checklist:
- [ ] No secrets in repo, committed `.env` files, or container images.
- [ ] Secrets fetched at runtime only, TTL <= 15 min.
- [ ] Auto-rotation every 60 to 90 days (or shorter for dynamic secrets).
- [ ] Telemetry pipeline redacts auth headers and token fields.
- [ ] Constant-time comparison for key validation.

---

### 11.7 Tenant Isolation

Multi-tenant RAG and agent systems leak across customers as soon as a single layer forgets the tenant filter. OWASP LLM Top 10 v2025 introduced LLM08:2025 as a dedicated category for vector/embedding weaknesses [Source: https://genai.owasp.org/llm-top-10/]. Studies from 2025 (PROMPTPEEK, NDSS) show that in shared vector indexes without tenant filtering up to 95 percent of benign queries trigger cross-tenant leaks, and KV-cache sharing in vLLM/SGLang enables timing attacks through which tenant A reconstructs prefixes of tenant B from time-to-first-token measurements [Source: https://www.ndss-symposium.org/wp-content/uploads/2025-1772-paper.pdf]. Tenant ID must be threaded through every layer: embedding, vector store, cache, memory, logging.

```python
# 1) App-layer filter is mandatory, raise SecurityError otherwise
class SecurityError(Exception): ...

def retrieve(query: str, tenant_id: str, k: int = 5):
    if not tenant_id:
        raise SecurityError("Tenant filter mandatory")
    return vector_store.query(
        query_embedding=embed(query),
        filter={"tenant_id": {"$eq": tenant_id}},
        top_k=k,
    )

# 2) KV-cache bleed prevention (vLLM cache_salt)
def llm_call(messages, tenant_id: str):
    return llm.chat(
        model="llama-3.1-70b",
        messages=messages,
        extra_body={"cache_salt": f"tenant:{tenant_id}"},
    )
```

```sql
-- 3) Postgres row-level security as defense-in-depth
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON documents
  USING (tenant_id = current_setting('app.tenant_id')::uuid);

-- per request on the connection:
SET LOCAL app.tenant_id = '7f3c...e9a1';
```

Anti-patterns:
- Global vector store without metadata filter, "we'll filter in the UI later".
- Semantic cache returning hits across tenants, or knowledge-graph expansion without re-checking authorization.

Checklist:
- [ ] Every vector query carries a `tenant_id` filter, otherwise SecurityError.
- [ ] Postgres RLS enabled on every multi-tenant table.
- [ ] Prompt cache salted per tenant or disabled.
- [ ] Semantic cache separates keyspaces by tenant.
- [ ] Cross-tenant leak test in CI: query as tenant A, assert no tenant-B hits.

---

### 11.8 PII and Data Classification

Employees and agents send personal data carelessly to external LLM APIs. The result is GDPR violations (Art. 6, 9, 32), HIPAA violations on medical data, and PCI violations on credit cards. Agent memory is the critical wrinkle: persisted PII violates the right-to-be-forgotten (GDPR Art. 17) when memories are not indexed per user. The solution pattern is a pre-call redaction pipeline based on Microsoft Presidio plus output reverse-mapping, so the model only sees tokens like `<PERSON_1>` while the user gets the cleartext back [Source: https://docs.litellm.ai/docs/tutorials/presidio_pii_masking].

```python
# LiteLLM pre-call redaction with Presidio + per-user memory deletion
from litellm import completion
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine

analyzer, anonymizer = AnalyzerEngine(), AnonymizerEngine()

def redact(text: str) -> tuple[str, dict]:
    res = analyzer.analyze(text=text, language="en",
                           entities=["PERSON", "PHONE_NUMBER", "EMAIL_ADDRESS",
                                     "CREDIT_CARD", "IBAN_CODE"])
    anon = anonymizer.anonymize(text=text, analyzer_results=res)
    mapping = {item.entity_type: text[item.start:item.end] for item in res}
    return anon.text, mapping

def restore(text: str, mapping: dict) -> str:
    for entity, original in mapping.items():
        text = text.replace(f"<{entity}>", original)
    return text

def chat(user_id: str, tenant_id: str, prompt: str) -> str:
    redacted, mapping = redact(prompt)
    audit.write(user=user_id, tenant=tenant_id, action="llm.call",
                pii_entities=list(mapping.keys()))   # type only, no value
    resp = completion(model="claude-sonnet-4-5",
                      messages=[{"role": "user", "content": redacted}])
    return restore(resp.choices[0].message.content, mapping)

# GDPR Art. 17: right-to-be-forgotten in agent memory
def forget_user(user_id: str):
    memory_store.delete_by_user(user_id)         # embeddings + conversation logs
    semantic_cache.invalidate(prefix=f"u:{user_id}")
    audit.write(action="gdpr.erasure", subject=user_id)
```

Anti-patterns:
- Raw prompts in application logs (Datadog, Splunk) without redaction.
- Conversation history in a single vector collection without user indexing, making DSAR (data subject access request) infeasible.

Checklist:
- [ ] Pre-call redaction before every external LLM provider call.
- [ ] Tool outputs also routed through the redaction layer.
- [ ] Agent memory indexed per user, deletion within 30 days feasible.
- [ ] Application logs free of raw prompts and PII.
- [ ] DPA with every LLM provider, sub-processors listed.

<!-- KAP 12 -->
---

### 12.4 SLOs and Rate Limits

LLM latency is highly variable (P50 1 s, P99 30 s is not unusual), provider outages at OpenAI and Anthropic happen regularly, and without per-tenant token quotas a single customer can exhaust the entire platform budget ("denial-of-wallet"). Production-ready systems define explicit latency budgets per endpoint (P50/P95/P99), use separate buckets for input and output tokens (output is roughly 4x more expensive), and spread load over AI gateways with provider failover.

| Metric | P50 | P95 | P99 |
|---|---|---|---|
| Time-to-First-Token | 400 ms | 1.2 s | 3 s |
| Total response time | 2 s | 8 s | 20 s |
| Tool-call roundtrip | 200 ms | 800 ms | 2 s |
| Error rate | < 0.5 % | -- | -- |

```python
# Tenant quota check + backpressure + provider failover
import asyncio, time
from collections import defaultdict

class TenantQuota:
    def __init__(self):
        self.tpm = defaultdict(lambda: {"tokens": 0, "reset": time.time() + 60})
        self.limits = {"acme": 200_000, "default": 50_000}
        self.sem = defaultdict(lambda: asyncio.Semaphore(10))

    def check(self, tenant: str, tokens: int):
        b = self.tpm[tenant]
        if time.time() > b["reset"]:
            b["tokens"], b["reset"] = 0, time.time() + 60
        limit = self.limits.get(tenant, self.limits["default"])
        if b["tokens"] + tokens > limit:
            retry_after = int(b["reset"] - time.time())
            raise HTTPException(429, headers={"Retry-After": str(retry_after)})
        b["tokens"] += tokens

quota = TenantQuota()

async def generate(req):
    quota.check(req.tenant, req.estimated_tokens)
    async with quota.sem[req.tenant]:           # max 10 concurrent
        for provider in ["anthropic", "openai", "google"]:   # failover chain
            try:
                return await asyncio.wait_for(
                    llm_call(provider, req), timeout=30
                )
            except (asyncio.TimeoutError, ProviderError):
                continue
        return cached_or_degraded_response(req)
```

In 2026, provider failover is most often realized through Vercel AI Gateway or OpenRouter, both of which deliver multi-provider routing with sub-40 ms overhead [Source: https://openrouter.ai/docs/guides/best-practices/latency-and-performance].

Anti-patterns:
- Global rate limits without tenant splitting, so one customer can block all others.
- Hard-rejecting at 100 percent instead of graceful degradation to a cheaper model.

Checklist:
- [ ] SLO table (P50/P95/P99 for TTFT, total time, error rate) documented per endpoint.
- [ ] Token bucket per tenant, separate limits for input and output.
- [ ] At least one provider failover configured and tested.
- [ ] Streaming on, TTFT as primary latency SLO.
- [ ] Backpressure via semaphore or queue, not hard reject.

---

### 12.5 Audit Logs

SOC2, HIPAA, and GDPR demand traceable audit trails, but prompts and responses can contain PII, trade secrets, and auth tokens. Naive "log everything" approaches create a compliance nightmare instead of solving one. As of 2026 the OpenTelemetry GenAI Semantic Conventions are production-ready (Datadog v1.37+, Sentry, Langfuse, Helicone all support them natively), and custom schemas create vendor lock-in [Source: https://opentelemetry.io/docs/specs/semconv/gen-ai/]. What gets logged: tenant ID, hashed user ID, tool calls, token counts, cache hits -- but NOT cleartext prompts when PII is possible. Prompts and completions move to WORM storage as hash references (S3 Object Lock COMPLIANCE mode, 7 years for HIPAA).

```python
# OpenTelemetry GenAI Semantic Conventions (state of 2026)
from opentelemetry import trace
from hashlib import sha256

tracer = trace.get_tracer("ai-agent")

def chat_with_audit(tenant_id: str, user_id: str, agent_id: str,
                    model: str, messages: list, prompt_blob_uri: str):
    with tracer.start_as_current_span("chat") as span:
        span.set_attribute("gen_ai.operation.name", "chat")
        span.set_attribute("gen_ai.provider.name", "anthropic")
        span.set_attribute("gen_ai.request.model", model)
        span.set_attribute("gen_ai.agent.id", agent_id)
        span.set_attribute("tenant.id", tenant_id)
        span.set_attribute("enduser.id",
                           sha256(user_id.encode()).hexdigest()[:16])
        # Prompt NOT inline, only reference into WORM storage
        span.set_attribute("gen_ai.prompt.ref", prompt_blob_uri)
        span.set_attribute("gen_ai.prompt.hash",
                           sha256(str(messages).encode()).hexdigest())

        resp = anthropic.messages.create(model=model, messages=messages)

        span.set_attribute("gen_ai.response.model", resp.model)
        span.set_attribute("gen_ai.usage.input_tokens", resp.usage.input_tokens)
        span.set_attribute("gen_ai.usage.output_tokens", resp.usage.output_tokens)
        span.set_attribute("gen_ai.usage.cache_read_input_tokens",
                           getattr(resp.usage, "cache_read_input_tokens", 0))
        return resp
```

```yaml
# AWS S3 Object Lock for compliance-grade WORM storage
audit_logs:
  bucket: org-audit-2026
  storage_class: GLACIER_IR
  object_lock:
    mode: COMPLIANCE          # NOT GOVERNANCE
    retention_days: 2555      # 7 years for HIPAA
  encryption: aws:kms
```

Retention regimes: SOC2 at least 1 year, HIPAA 6 years plus BAA with the provider, GDPR purpose-limited with a documented deletion deadline.

Anti-patterns:
- Full prompts and completions in stdout/Datadog logs without redaction.
- Logs in mutable storage (S3 without Object Lock) -- compliance auditor will reject.

Checklist:
- [ ] OpenTelemetry GenAI Semantic Conventions as schema, not custom.
- [ ] Prompts/completions not in span, only hash reference into WORM storage.
- [ ] Tenant ID and hashed user ID on every span.
- [ ] Retention policy per compliance regime (SOC2 1y, HIPAA 6y, GDPR purpose-limited).
- [ ] Audit storage immutable (S3 Object Lock COMPLIANCE mode).

---

### 12.6 Rollback and Incident Response

Prompt changes are deployments. A new system prompt can double the hallucination rate without staging tests catching it, because staging does not have the production traffic mix. Without canary plus auto-rollback, changes go live blind. On top of that, tool failures, hallucination spikes, and cost anomalies each need their own runbook, because a generic "agent broken" alert leaves the on-call engineer with no actionable signal. Vercel Agent Investigations (AI-driven root-cause analysis) and Sentry GenAI auto-instrumentation are the 2026 reference tools for this [Source: https://vercel.com/docs/agent].

```ts
// Vercel Rolling Releases -- canary with auto-rollback on metric degradation
import { unstable_rolloutFlag } from "@vercel/flags";

export const promptVersion = unstable_rolloutFlag("prompt_v3", {
  rolloutPercent: 5,
  rolloutStages: [5, 25, 50, 100],
  rollbackOn: {
    metrics: ["hallucination_rate", "p95_latency", "cost_per_request"],
    thresholds: {
      hallucination_rate: 1.5,   // 1.5x 7-day baseline
      p95_latency: 1.3,
      cost_per_request: 1.5,
    },
    minSampleSize: 500,          // statistical significance before promote
  },
});
```

Example runbook for a hallucination spike as executable markdown:

```markdown
# Runbook: Hallucination Spike

**Trigger:** `hallucination_rate > 2x 7d-baseline` over 15 min window
**Severity:** High
**Owner:** AI Platform Oncall

## Steps
1. **Snapshot** current prompt diff: `git log -p prompts/ -n 5`
2. **Check model version:**
   `otel query 'gen_ai.response.model' | group by hour, last 6h`
   -> provider may have silently patched (e.g. claude-sonnet-4-5-20260315 -> -20260418).
3. **Rollback canary:** `vercel rolling-release rollback --to-stable`
4. **Confirm recovery:** `hallucination_rate < 1.2x baseline` in next window.
5. **Page oncall** if recovery does not happen within 10 min.
6. **Post-mortem** within 24 h, document root cause and test-coverage gap.
```

Additional runbooks (same shape) for tool failure (circuit-break, fallback response) and cost anomaly (identify top-3 power users, downgrade model to Haiku tier, Slack alert).

Anti-patterns:
- Editing prompts directly in production with no versioning and no diff in PR review.
- Generic "agent broken" alerts without distinguishing timeout, hallucination, tool error, and context overflow.

Checklist:
- [ ] Prompts versioned in git, every change in PR review.
- [ ] Canary rollout with auto-rollback on metric degradation enabled.
- [ ] Runbooks for at least 4 incident classes: hallucination, tool failure, cost spike, latency spike.
- [ ] Trace ID propagated through all sub-agents and tool calls.
- [ ] Failure modes differentiated (timeout/tool-error/hallucination/context-overflow).

---

### 12.7 Cost Management

LLM cost is often the largest variable cost line for a SaaS product. A single power user or a loop bug can burn five-figure amounts in a day ("denial-of-wallet"). Without per-tenant caps, cache-hit-rate monitoring, and model tiering, the unit economics are unmanageable. Best practice is hierarchical throttling at the 70/80/95/100 percent thresholds (alert -> soft throttle -> hard throttle -> block) and model tiering that routes trivial queries to the Haiku tier and only escalates complexity to Sonnet or Opus. Industry benchmarks show 60 to 90 percent cost reduction over single-tier setups [Source: https://www.clarifai.com/blog/ai-cost-controls].

```ts
// Tier router with streaming cancellation and budget cap
import { Anthropic } from "@anthropic-ai/sdk";

const client = new Anthropic();
type Tier = "haiku" | "sonnet" | "opus";

const MODEL: Record<Tier, string> = {
  haiku:  "claude-haiku-4-5",     // ~$0.25 / MTok in
  sonnet: "claude-sonnet-4-5",    // ~$3 / MTok in
  opus:   "claude-opus-4-5",      // ~$15 / MTok in
};

async function classifyTier(query: string): Promise<Tier> {
  // small model for routing, ~1-5 ms
  const c = await client.messages.create({
    model: MODEL.haiku,
    max_tokens: 8,
    messages: [{ role: "user", content:
      `Tier (haiku|sonnet|opus) for: ${query.slice(0, 400)}` }],
  });
  return (c.content[0] as any).text.trim() as Tier;
}

async function tierRoute(query: string, tenant: string, signal: AbortSignal) {
  // 1) hierarchical budget cap
  const used = await budget.usage(tenant);
  if (used.pct >= 1.0) throw new Error("Budget exhausted");
  if (used.pct >= 0.95) return degradedFallback(query);   // hard throttle
  let tier = await classifyTier(query);
  if (used.pct >= 0.80 && tier === "opus")   tier = "sonnet";  // soft throttle
  if (used.pct >= 0.80 && tier === "sonnet") tier = "haiku";

  // 2) streaming + cancellation, so abandoned UIs do not keep burning tokens
  const stream = await client.messages.stream({
    model: MODEL[tier],
    system: [{ type: "text", text: SYSTEM_PROMPT,
               cache_control: { type: "ephemeral" } }],   // up to 90% cheaper on cache hit
    messages: [{ role: "user", content: query }],
    max_tokens: 1024,
  }, { signal });

  // 3) hit-rate monitoring
  const res = await stream.finalMessage();
  metrics.cacheHit.observe({
    tenant, tier,
    ratio: res.usage.cache_read_input_tokens /
           Math.max(1, res.usage.input_tokens),
  });
  return res;
}
```

Anti-patterns:
- Premium model (Opus, GPT-4) as default for every query, no tiering.
- No streaming cancel, so abandoned streams keep producing tokens until `max_tokens`.

Checklist:
- [ ] Per-tenant daily cap configured, progressive throttling at 70/80/95/100 percent.
- [ ] Model tiering in place, trivial queries routed to Haiku/mini tier.
- [ ] Anthropic/OpenAI prompt caching enabled, hit-rate dashboard exists (target > 70 percent).
- [ ] Streaming cancellation propagates AbortSignal all the way to the provider.
- [ ] Cost attribution per tenant/feature/user visible in dashboard.
