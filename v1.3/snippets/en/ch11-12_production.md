### 11.5 Identity and Auth

Agents call tools and MCP servers that in turn hit APIs with user-specific permissions (mail, calendar, CRM). When the agent runs under a single service identity, the user context is lost. The result is privilege escalation, the classic "confused deputy", and audit gaps. Early 2026 saw explicit reports that Microsoft Foundry Agents in M365 Copilot do not propagate the OAuth identity but operate under app identity instead. The clean approach is OAuth On-Behalf-Of (OBO) per RFC 8693 with the `act` claim: the token carries both user (`sub`) and agent (`act.sub`), resource servers reduce scopes to the intersection of user, agent, and requested scopes (capability attenuation). Multi-hop chains nest `act` recursively.

```python
# OBO Token Exchange per RFC 8693, FastAPI / httpx
import httpx, time, jwt

TOKEN_URL = "https://auth.example.com/oauth2/token"
GRANT = "urn:ietf:params:oauth:grant-type:token-exchange"
TOKEN_TYPE = "urn:ietf:params:oauth:token-type:access_token"

async def exchange_for_downstream(
    user_token: str, agent_client_id: str, agent_secret: str,
    target_resource: str, requested_scopes: list[str]
) -> dict:
    async with httpx.AsyncClient(timeout=5) as c:
        r = await c.post(TOKEN_URL, data={
            "grant_type": GRANT,
            "subject_token": user_token,
            "subject_token_type": TOKEN_TYPE,
            "resource": target_resource,
            "scope": " ".join(requested_scopes),
            "client_id": agent_client_id,
            "client_secret": agent_secret,
            "actor_token": _agent_assertion(agent_client_id),
            "actor_token_type": TOKEN_TYPE,
        })
        r.raise_for_status()
        return r.json()

def verify_obo(access_token: str, jwks) -> dict:
    claims = jwt.decode(access_token, jwks, algorithms=["RS256"],
                        audience="crm-api")
    if not claims.get("act", {}).get("sub"):
        raise PermissionError("Missing agent actor claim")
    if claims["exp"] < time.time():
        raise PermissionError("Token expired")
    return claims  # claims['sub'] = user, claims['act']['sub'] = agent
```

The resource server then verifies that the requested scope is contained in both the user's and the agent's permissions, and logs both identities for every tool call.

**Anti-pattern**
- A single service-account token with superuser rights as a "shared agent identity"; every tool call looks like the same bot.
- Embedding user tokens into system messages or prompts (they end up in the KV cache and audit log).

**Checklist**
- [ ] Every tool call carries `sub` (user) AND `act.sub` (agent).
- [ ] Scope = `intersection(user, agent, requested)`.
- [ ] PKCE mandatory, authorization codes single-use.
- [ ] Consent UI names the agent explicitly.
- [ ] Audit log persists user + agent + action + resource.

Sources: [WorkOS OBO for AI agents](https://workos.com/blog/oauth-on-behalf-of-ai-agents), [Microsoft OBO Flow](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-on-behalf-of-flow), [TrueFoundry Agent Identity OBO](https://www.truefoundry.com/docs/ai-gateway/agents/agent-identity-obo), [Solo kagent OBO](https://docs.solo.io/kagent-enterprise/docs/latest/security/obo/).

---

### 11.6 Secret Handling

MCP servers typically aggregate dozens of API keys, database passwords, and OAuth tokens in one config file. Tokens accidentally end up in prompts, logs, agent memory, or KV caches. OWASP MCP01:2025 (Token Mismanagement & Secret Exposure) is the most common MCP vulnerability in 2026. The pattern is: the MCP server holds no long-lived credential at runtime. Instead it pulls short-lived, dynamically issued tokens from a vault or KMS, with a 15-minute hard expiry and automatic rotation at 80 percent of TTL. Telemetry must redact auth headers before export.

```python
# Vault dynamic secret + cached, constant-time check
import time, hmac, hashlib
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

KV = SecretClient(vault_url="https://my-kv.vault.azure.net",
                  credential=DefaultAzureCredential())

class CachedSecret:
    def __init__(self, name: str, ttl: int = 300):
        self.name, self.ttl = name, ttl
        self._val: str | None = None
        self._exp = 0.0

    def get(self) -> str:
        if time.time() > self._exp:
            self._val = KV.get_secret(self.name).value
            self._exp = time.time() + self.ttl
        return self._val

def verify_api_key(provided: str, expected: str) -> bool:
    # Constant-time, never == (timing attack)
    return hmac.compare_digest(
        hashlib.sha256(provided.encode()).digest(),
        hashlib.sha256(expected.encode()).digest(),
    )

# Telemetry hook: redact auth headers
def otel_redact(span):
    for k in ("http.request.header.authorization", "tool_call.arguments"):
        if k in span.attributes:
            span.set_attribute(k, "[REDACTED]")
```

For provider tokens use vault dynamic backends (e.g. `github-mcp-readonly` with TTL 15m), so even on leak the window is minimal.

**Anti-pattern**
- API keys as env vars in the container that the agent can read via `os.environ`.
- Secrets in system message or tool description; they end up in KV cache and audit log.

**Checklist**
- [ ] No secret in the repo, in committed `.env` files, or in the image.
- [ ] MCP server fetches secrets only at runtime, TTL <= 15min.
- [ ] Auto-rotation every 60 to 90 days.
- [ ] Telemetry redacts auth headers and tool-call arguments.
- [ ] Constant-time comparison for key validation (`hmac.compare_digest`).

Sources: [Will Velida: Preventing MCP01](https://www.willvelida.com/posts/preventing-mcp01-token-mismanagement-secret-exposure), [Doppler MCP Best Practices](https://www.doppler.com/blog/mcp-server-credential-security-best-practices), [HashiCorp Vault MCP Server](https://developer.hashicorp.com/vault/docs/mcp-server/prompt-model), [Azure Key Vault MCP](https://learn.microsoft.com/en-us/azure/developer/azure-mcp-server/services/azure-mcp-server-for-key-vault).

---

### 11.7 Tenant Isolation

Multi-tenant RAG and agent systems leak across customers when tenant ID is not propagated through every layer. The PROMPTPEEK study (NDSS 2025) shows that in shared vector indexes without a tenant filter, up to 95 percent of benign queries return cross-tenant data. Additionally, KV cache sharing in vLLM or SGLang enables timing attacks where tenant A reconstructs prefixes from tenant B via time-to-first-token. OWASP LLM08:2025 lists vector and embedding weaknesses as a dedicated category. Mandatory patterns: tenant ID as an explicit parameter on every function, Postgres row-level security as defense in depth, per-tenant `cache_salt` in vLLM, and cross-tenant leak tests in CI.

```python
# Application layer enforces filter
from fastapi import Request

def retrieve(query: str, tenant_id: str, k: int = 5):
    if not tenant_id:
        raise SecurityError("Tenant filter mandatory")
    return vector_store.query(
        query_embedding=embed(query),
        filter={"tenant_id": {"$eq": tenant_id}},
        top_k=k,
    )

async def llm_call(req: Request, messages: list[dict], tenant_id: str):
    # vLLM cache_salt prevents KV cache bleed across tenants
    return await vllm.chat.completions.create(
        model="llama-3.1-70b",
        messages=messages,
        extra_body={"cache_salt": f"tenant-{tenant_id}-2026"},
    )
```

```sql
-- Postgres RLS as backstop in case the app filter is bypassed
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON documents
  USING (tenant_id = current_setting('app.tenant_id')::uuid);

-- Set per request
SET LOCAL app.tenant_id = '7c1e...';
```

Pick *Silo* (one index per tenant), *Pool* (shared index with mandatory filter), or *Bridge* (high-risk tenants in silo, the rest pooled) based on data sensitivity.

**Anti-pattern**
- Global vector store without metadata filter, "we'll filter in the UI".
- Semantic cache returning hits across tenants, or a shared system prompt that contains tenant data.

**Checklist**
- [ ] Vector query without tenant filter raises `SecurityError`.
- [ ] Postgres RLS enabled on every multi-tenant table.
- [ ] `cache_salt` set per tenant in vLLM/SGLang.
- [ ] Semantic cache separates keyspaces by tenant.
- [ ] CI test: query as tenant A, assert no tenant B docs returned.

Sources: [NDSS 2025 PROMPTPEEK](https://www.ndss-symposium.org/wp-content/uploads/2025-1772-paper.pdf), [vLLM cache_salt](https://docs.vllm.ai/en/stable/design/prefix_caching/), [Mavik Multi-Tenant RAG 2026](https://www.maviklabs.com/blog/multi-tenant-rag-2026), [OWASP LLM Top 10](https://genai.owasp.org/llm-top-10/).

---

### 11.8 PII and Data Classification

Employees and agents send personal data to external LLM APIs without a second thought. The result: GDPR breaches under Art. 6, 9, 32, HIPAA breaches for medical data, PCI for credit cards. On top of that, agent memory persists PII for weeks, making GDPR Art. 17 (Right to be Forgotten) technically unenforceable without proper memory indexing. The 2026 default pattern is pre-call redaction with Microsoft Presidio plus optional output reverse-mapping. Redaction runs BEFORE every external provider call and also on tool outputs that flow back into the context window.

```python
# LiteLLM + Presidio: pre-call redaction with reverse mapping
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig
import litellm

analyzer = AnalyzerEngine()
anonymizer = AnonymizerEngine()

OPERATORS = {
    "PERSON":        OperatorConfig("replace", {"new_value": "<PERSON>"}),
    "EMAIL_ADDRESS": OperatorConfig("replace", {"new_value": "<EMAIL>"}),
    "PHONE_NUMBER":  OperatorConfig("replace", {"new_value": "<PHONE>"}),
    "US_SSN":        OperatorConfig("replace", {"new_value": "<BLOCKED>"}),
    "CREDIT_CARD":   OperatorConfig("replace", {"new_value": "<BLOCKED>"}),
}

def redact(text: str) -> tuple[str, dict[str, str]]:
    results = analyzer.analyze(text=text, language="en")
    anon = anonymizer.anonymize(text=text, analyzer_results=results,
                                operators=OPERATORS)
    mapping = {f"<{r.entity_type}_{i}>": text[r.start:r.end]
               for i, r in enumerate(results)}
    return anon.text, mapping

def restore(text: str, mapping: dict[str, str]) -> str:
    for placeholder, original in mapping.items():
        text = text.replace(placeholder, original)
    return text

async def safe_chat(user_msg: str, user_id: str) -> str:
    redacted, mapping = redact(user_msg)
    audit_log(user_id=user_id, redacted_in=redacted)  # never raw
    resp = await litellm.acompletion(
        model="claude-sonnet-4-5",
        messages=[{"role": "user", "content": redacted}],
    )
    return restore(resp.choices[0].message.content, mapping)

# GDPR Art. 17 -- per-user indexed memory store
def forget_user(user_id: str):
    memory_store.delete_by_user(user_id)
    embedding_index.delete(filter={"user_id": user_id})
    audit_store.mark_for_purge(user_id)
```

**Anti-pattern**
- Raw prompts in Datadog/Splunk logs without redaction.
- Conversation history in a single vector collection without user indexing; DSAR requests cannot be satisfied.

**Checklist**
- [ ] Pre-call redaction before every external LLM call.
- [ ] Tool outputs also pass through the redaction layer.
- [ ] Memory indexed by `user_id`, deletion within 30 days.
- [ ] Application logs contain no raw prompts or PII.
- [ ] DPA in place with every provider, sub-processors listed.

Sources: [Microsoft Presidio](https://github.com/microsoft/presidio), [LiteLLM Presidio Guardrail](https://docs.litellm.ai/docs/tutorials/presidio_pii_masking), [Ploomber: Preventing PII leakage](https://ploomber.io/blog/presidio/), [PII Redaction Pipeline](https://redteams.ai/topics/walkthroughs/defense/pii-redaction-pipeline).

<!-- KAP 11 ENDE / KAP 12 START -->

---

### 12.4 SLOs and Rate Limits

LLM latency is highly variable (P50 1s, P99 30s are not unusual). Provider outages at OpenAI and Anthropic happen regularly. Without per-tenant token quotas, a single power user can burn through the entire platform's budget, an effect now commonly named "denial of wallet". The 2026 standard pattern: an explicit SLO table per endpoint (TTFT, total time, error rate) at P50/P95/P99, a token bucket per tenant with separate input/output limits, at least one configured provider failover via an AI gateway, and backpressure as a queue-with-timeout instead of a hard reject.

| Metric | P50 | P95 | P99 |
|---|---|---|---|
| Time-to-First-Token | 400ms | 1.2s | 3s |
| Total Response Time | 2s | 8s | 20s |
| Tool-Call Roundtrip | 200ms | 800ms | 2s |
| Error Rate | <0.5% | -- | -- |

```python
# Tenant quota check + backpressure + provider failover
import asyncio, time
from collections import defaultdict

class TenantBucket:
    def __init__(self, tpm: int, rpm: int, daily_budget_usd: float):
        self.tpm, self.rpm = tpm, rpm
        self.daily_budget = daily_budget_usd
        self.tokens_used = 0
        self.requests_used = 0
        self.cost_today = 0.0
        self.window_start = time.time()

    def check(self, est_tokens: int, est_cost_usd: float):
        if time.time() - self.window_start > 60:
            self.tokens_used = self.requests_used = 0
            self.window_start = time.time()
        if self.requests_used + 1 > self.rpm:
            raise QuotaExceeded("rpm", retry_after=60)
        if self.tokens_used + est_tokens > self.tpm:
            raise QuotaExceeded("tpm", retry_after=60)
        if self.cost_today + est_cost_usd > self.daily_budget:
            raise QuotaExceeded("daily_budget", retry_after=86400)

BUCKETS: dict[str, TenantBucket] = defaultdict(
    lambda: TenantBucket(tpm=200_000, rpm=100, daily_budget_usd=50.0))

SEMA: dict[str, asyncio.Semaphore] = defaultdict(
    lambda: asyncio.Semaphore(10))

async def generate(tenant_id: str, prompt: str, est_tokens: int):
    BUCKETS[tenant_id].check(est_tokens, est_cost_usd=est_tokens * 3e-6)
    async with SEMA[tenant_id]:
        try:
            return await asyncio.wait_for(
                primary_call(prompt), timeout=10)
        except (asyncio.TimeoutError, ProviderError):
            return await fallback_call(prompt)  # OpenRouter / Vercel Gateway
```

In the HTTP layer `QuotaExceeded` maps to a `429` with a `Retry-After` header.

**Anti-pattern**
- Global rate limits with no tenant splitting; one customer blocks all the others.
- Identical limits for input and output tokens; output is roughly four times more expensive.

**Checklist**
- [ ] SLO table (TTFT, total, error) per endpoint documented.
- [ ] Token bucket per tenant, input and output split.
- [ ] At least one provider failover configured and tested.
- [ ] Streaming on, TTFT as the primary latency SLO.
- [ ] Backpressure via semaphore/queue, not hard reject.

Sources: [OpenRouter Latency](https://openrouter.ai/docs/guides/best-practices/latency-and-performance), [Inworld Best LLM Gateways 2026](https://inworld.ai/resources/best-llm-gateways), [Maxim Top LLM Gateways 2026](https://www.getmaxim.ai/articles/top-5-llm-gateways-for-2026-a-comprehensive-comparison/).

---

### 12.5 Audit Logs

SOC2, HIPAA, and GDPR all require traceable audit trails, but prompts and responses can contain PII, trade secrets, or auth tokens. Naive "log everything" approaches create a compliance nightmare instead of solving one. As of 2026 the OpenTelemetry GenAI Semantic Conventions are production-ready, with native support in Datadog v1.37+, Sentry, Langfuse, and Helicone. Logged: tenant ID and user ID (hashed), model, token counts, tool-call names, cache hits. Plain-text prompts and completions by default do NOT go in span attributes but as a hash reference into separate WORM storage (S3 Object Lock in COMPLIANCE mode).

```python
# OpenTelemetry GenAI Semantic Conventions, Python
from opentelemetry import trace
import hashlib, json

tracer = trace.get_tracer("agent.production")

def log_chat(tenant_id: str, user_id: str, agent_id: str,
             messages: list, response, tool_calls: list):
    with tracer.start_as_current_span("gen_ai.chat") as span:
        span.set_attribute("gen_ai.operation.name", "chat")
        span.set_attribute("gen_ai.provider.name", "anthropic")
        span.set_attribute("gen_ai.request.model", "claude-sonnet-4-5")
        span.set_attribute("gen_ai.response.model",
                           response.model)
        span.set_attribute("gen_ai.usage.input_tokens",
                           response.usage.input_tokens)
        span.set_attribute("gen_ai.usage.output_tokens",
                           response.usage.output_tokens)
        span.set_attribute("gen_ai.usage.cache_read_input_tokens",
                           getattr(response.usage,
                                   "cache_read_input_tokens", 0))
        # Compliance fields
        span.set_attribute("tenant.id", tenant_id)
        span.set_attribute("enduser.id",
                           hashlib.sha256(user_id.encode()).hexdigest())
        span.set_attribute("gen_ai.agent.id", agent_id)
        # Prompt hash, plain text goes to WORM
        prompt_blob = json.dumps(messages, sort_keys=True).encode()
        prompt_hash = hashlib.sha256(prompt_blob).hexdigest()
        span.set_attribute("gen_ai.prompt.hash", prompt_hash)
        worm_storage.put(f"prompts/{prompt_hash}", prompt_blob)
        for tc in tool_calls:
            span.add_event("gen_ai.tool.call", attributes={
                "tool.name": tc.name,
                # Hash args, auth tokens may end up there
                "tool.args.hash": hashlib.sha256(
                    json.dumps(tc.args).encode()).hexdigest(),
            })
```

WORM storage: AWS S3 Object Lock in COMPLIANCE mode with retention per regime (SOC2 1 year, HIPAA 6 years, GDPR purpose-bound). KMS encryption mandatory.

**Anti-pattern**
- Full prompts in application logs (stdout to Datadog) without redaction.
- Custom schema instead of OTel GenAI Semantic Conventions; vendor lock-in, no tooling support.

**Checklist**
- [ ] OTel GenAI Semantic Conventions as the schema, not custom.
- [ ] Plain-text prompts/completions in WORM storage, hash in the span.
- [ ] Tenant ID and hashed user ID on every span.
- [ ] Retention per compliance regime (SOC2 1y, HIPAA 6y).
- [ ] S3 Object Lock COMPLIANCE mode, KMS encrypted.

Sources: [OTel GenAI Spans](https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-spans/), [OTel Agentic Spans](https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-agent-spans/), [Datadog OTel GenAI](https://www.datadoghq.com/blog/llm-otel-semantic-convention/), [OpenObserve OTel for LLMs 2026](https://openobserve.ai/blog/opentelemetry-for-llms/).

---

### 12.6 Rollback and Incident Response

Prompt changes are deployments. A new system prompt can silently double the hallucination rate without staging tests catching it. Without canary plus auto-rollback, changes go live blind. By 2026 the established stack is: prompt versioning in git, canary rollout with statistical significance before promote (5/25/50/100 percent stages), auto-rollback on metric degradation, blue/green for agent versions via feature flag, and differentiated runbooks per failure mode (hallucination spike, tool failure, cost anomaly, latency spike). Vercel Agent Investigations correlates logs and metrics around the alert window automatically; Sentry instruments `gen_ai.invoke_agent` spans natively.

```yaml
# runbooks/hallucination-spike.yaml -- runnable as a tool
trigger:
  metric: hallucination_rate
  threshold: 2x_7day_baseline
  window: 15m
steps:
  - name: snapshot_prompt_diff
    action: git diff HEAD~1 -- prompts/
  - name: check_model_version_drift
    action: |
      query_otel "gen_ai.response.model"
        | group_by hour
        | last 24h
  - name: pause_canary
    action: vercel rolling-release pause
  - name: rollback_to_stable
    action: vercel rolling-release rollback --to-stable
  - name: page_oncall
    action: pagerduty.trigger("hallucination-spike", severity=high)
  - name: open_investigation
    action: vercel agent investigate --window=30m
```

```ts
// Vercel Rolling Release with auto-rollback thresholds
import { unstable_rolloutFlag } from "@vercel/flags";

export const promptVersion = unstable_rolloutFlag("prompt_v3", {
  rolloutPercent: 5,
  rolloutStages: [5, 25, 50, 100],
  rollbackOn: {
    metrics: ["hallucination_rate", "p95_latency",
              "error_rate", "cost_per_request"],
    thresholds: {
      hallucination_rate: 1.5,   // 1.5x baseline -> rollback
      p95_latency:        1.3,
      error_rate:         2.0,
      cost_per_request:   1.4,
    },
  },
});
```

The trace ID has to flow through every sub-agent and tool call, otherwise tracing ends at the agent boundary.

**Anti-pattern**
- Editing prompts directly in production, no versioning, no PR diff review.
- Generic "agent is broken" alerts with no failure-mode differentiation (timeout vs. hallucination vs. tool error vs. context overflow).

**Checklist**
- [ ] Prompts versioned in git, every change reviewed in a PR.
- [ ] Canary with auto-rollback on hallucination, latency, cost, error.
- [ ] Runbooks for at least 4 failure modes.
- [ ] Trace ID propagated through every sub-agent and tool call.
- [ ] Mean time to recovery documented under 10 minutes.

Sources: [Vercel Rolling Releases](https://vercel.com/docs/rolling-releases), [Vercel Agent](https://vercel.com/docs/agent), [Sentry Multi-Agent Observability](https://blog.sentry.io/scaling-observability-for-multi-agent-ai-systems/), [Canary Deployments for LLMs](https://medium.com/@oracle_43885/canary-deployments-for-securing-large-language-models-48393fa68efc).

---

### 12.7 Cost Control

LLM cost is often the largest variable cost line for SaaS products. A single power user or a loop bug can burn five-figure amounts in a day. Without per-tenant caps, cache hit-rate monitoring, and model tiering, unit economics are uncontrollable. The 2026 pattern: hierarchical budget caps with progressive throttling (70/80/95/100 percent), tier routing Haiku to Sonnet to Opus driven by a cheap complexity classifier (60 to 90 percent cost reduction per industry benchmarks), Anthropic prompt caching with a hit-rate target above 70 percent, streaming cancellation propagated to the provider via `AbortSignal`.

| Threshold | Action |
|---|---|
| 70% | Alert tenant + sales |
| 80% | Soft throttle: route to cheaper model |
| 95% | Hard throttle: queue or reject non-essential |
| 100% | Block, essential endpoints only |

```typescript
// Tier router with complexity classifier + budget awareness
import Anthropic from "@anthropic-ai/sdk";

const client = new Anthropic();

type Tier = "haiku" | "sonnet" | "opus";

interface TenantState {
  spentToday: number;
  dailyCap: number;
}

async function classifyComplexity(q: string): Promise<Tier> {
  // Cheap Haiku call, ~1ms, ~$0.0001
  const r = await client.messages.create({
    model: "claude-haiku-4-5",
    max_tokens: 8,
    messages: [{
      role: "user",
      content: `Classify: trivial|moderate|complex.\nQuery: ${q}`,
    }],
  });
  const label = (r.content[0] as any).text.trim().toLowerCase();
  if (label.startsWith("triv")) return "haiku";
  if (label.startsWith("mod"))  return "sonnet";
  return "opus";
}

export async function route(query: string, tenant: TenantState,
                             signal: AbortSignal) {
  let tier = await classifyComplexity(query);
  const ratio = tenant.spentToday / tenant.dailyCap;

  // Progressive degradation
  if (ratio > 0.95) throw new Error("Budget exhausted");
  if (ratio > 0.80 && tier === "opus")   tier = "sonnet";
  if (ratio > 0.70 && tier === "sonnet") tier = "haiku";

  const model = {
    haiku:  "claude-haiku-4-5",
    sonnet: "claude-sonnet-4-5",
    opus:   "claude-opus-4-7",
  }[tier];

  return client.messages.create({
    model,
    max_tokens: 1024,
    system: [{
      type: "text",
      text: LONG_SYSTEM_PROMPT,
      cache_control: { type: "ephemeral" }, // up to 90% cheaper
    }],
    messages: [{ role: "user", content: query }],
    stream: true,
  }, { signal });  // Streaming cancellation reaches the provider
}
```

At the application layer wire `req.on("close", () => controller.abort())` so abandoned streams stop generating tokens. Cache hit rate (`cache_read_input_tokens / input_tokens`) belongs on the primary cost dashboard.

**Anti-pattern**
- Premium model as the default for every query, no tiering.
- No streaming cancel; abandoned streams keep emitting tokens and cost.

**Checklist**
- [ ] Per-tenant daily cap, progressive throttling at 70/80/95/100%.
- [ ] Model tiering active, trivial queries on the Haiku/mini tier.
- [ ] Prompt caching on, hit-rate dashboard, target >70%.
- [ ] `AbortSignal` propagated all the way to the provider.
- [ ] Cost attribution per tenant/feature/user on the dashboard.

Sources: [Clarifai AI Cost Controls](https://www.clarifai.com/blog/ai-cost-controls), [Maxim Reduce LLM Cost 2026](https://www.getmaxim.ai/articles/reduce-llm-cost-and-latency-a-comprehensive-guide-for-2026/), [Redis LLM Token Optimization](https://redis.io/blog/llm-token-optimization-speed-up-apps/), [LLM Agent Cost Attribution 2026](https://www.digitalapplied.com/blog/llm-agent-cost-attribution-guide-production-2026).
