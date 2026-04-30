### 11.5 Identity und Auth

Agenten rufen Tools und MCP-Server auf, die ihrerseits APIs mit nutzerspezifischen Berechtigungen ansprechen (Mail, Kalender, CRM). Lauft der Agent unter einer einzigen Service-Identitaet, geht der User-Kontext verloren. Folge: Privilege-Escalation, "confused deputy", Audit-Luecken. Anfang 2026 wurde explizit gemeldet, dass Microsoft Foundry Agents in M365 Copilot die OAuth-Identitaet nicht durchreichen, sondern unter App-Identitaet operieren. Der saubere Weg ist OAuth On-Behalf-Of (OBO) nach RFC 8693 mit `act`-Claim: das Token traegt User (`sub`) und Agent (`act.sub`), Resource-Server schneiden Scopes auf den Schnitt aus User-, Agent- und Request-Scopes (Capability Attenuation). Multi-Hop verschachtelt `act` rekursiv.

```python
# OBO Token Exchange nach RFC 8693, FastAPI / httpx
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
    return claims  # claims['sub'] = User, claims['act']['sub'] = Agent
```

Der Resource-Server prueft anschliessend, dass der angeforderte Scope sowohl in den User-Permissions als auch in den Agent-Permissions liegt, und logt User plus Agent pro Tool-Call.

**Anti-Pattern**
- Ein einziges Service-Account-Token mit Superuser-Rechten als "shared agent identity"; jeder Tool-Call sieht aus wie derselbe Bot.
- User-Token in System-Message oder Prompt einbetten (landet im KV-Cache und Audit-Log).

**Checkliste**
- [ ] Jeder Tool-Call traegt `sub` (User) UND `act.sub` (Agent).
- [ ] Scope = `intersection(user, agent, requested)`.
- [ ] PKCE Pflicht, Authorization Codes single-use.
- [ ] Consent-UI nennt den Agent beim Namen.
- [ ] Audit-Log persistiert User + Agent + Action + Resource.

Quellen: [WorkOS OBO for AI agents](https://workos.com/blog/oauth-on-behalf-of-ai-agents), [Microsoft OBO Flow](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-on-behalf-of-flow), [TrueFoundry Agent Identity OBO](https://www.truefoundry.com/docs/ai-gateway/agents/agent-identity-obo), [Solo kagent OBO](https://docs.solo.io/kagent-enterprise/docs/latest/security/obo/).

---

### 11.6 Secret-Handling

MCP-Server aggregieren typischerweise Dutzende API-Keys, DB-Passwoerter und OAuth-Tokens in einer Config-Datei. Tokens landen versehentlich in Prompts, Logs, Memory oder KV-Caches. OWASP MCP01:2025 (Token Mismanagement & Secret Exposure) ist 2026 die haeufigste MCP-Schwachstelle. Loesungs-Pattern: der MCP-Server haelt zur Laufzeit kein langlebiges Credential, sondern bezieht Secrets als kurzlebige, dynamisch erzeugte Tokens aus Vault oder KMS, mit Hard-Expiry von 15 Minuten und automatischer Rotation bei 80 Prozent der TTL. Telemetrie redigiert Auth-Header verpflichtend vor dem Export.

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
    # Konstanzeit, nicht ==, sonst Timing-Attack
    return hmac.compare_digest(
        hashlib.sha256(provided.encode()).digest(),
        hashlib.sha256(expected.encode()).digest(),
    )

# Telemetry-Hook: Auth-Header redigieren
def otel_redact(span):
    for k in ("http.request.header.authorization", "tool_call.arguments"):
        if k in span.attributes:
            span.set_attribute(k, "[REDACTED]")
```

Fuer kurzlebige Provider-Tokens nutzt man Vault-Dynamic-Backends (z.B. `github-mcp-readonly` mit TTL 15m), sodass selbst bei Leak das Window minimal ist.

**Anti-Pattern**
- API-Keys als Env-Vars im Container, die der Agent ueber `os.environ` selbst lesen kann.
- Secrets in System-Message oder Tool-Description; sie landen in KV-Cache und Audit-Log.

**Checkliste**
- [ ] Kein Secret im Repo, in `.env` committed oder im Image.
- [ ] MCP-Server zieht Secrets nur zur Laufzeit, TTL <= 15min.
- [ ] Auto-Rotation alle 60 bis 90 Tage.
- [ ] Telemetrie redigiert Auth-Header und Tool-Call-Args.
- [ ] Konstanzzeit-Vergleich fuer Key-Validation (`hmac.compare_digest`).

Quellen: [Will Velida: Preventing MCP01](https://www.willvelida.com/posts/preventing-mcp01-token-mismanagement-secret-exposure), [Doppler MCP Best Practices](https://www.doppler.com/blog/mcp-server-credential-security-best-practices), [HashiCorp Vault MCP Server](https://developer.hashicorp.com/vault/docs/mcp-server/prompt-model), [Azure Key Vault MCP](https://learn.microsoft.com/en-us/azure/developer/azure-mcp-server/services/azure-mcp-server-for-key-vault).

---

### 11.7 Mandantentrennung

Multi-Tenant-RAG- und Agent-Systeme leaken zwischen Kunden, wenn Tenant-ID nicht auf jeder Schicht propagiert wird. Die PROMPTPEEK-Studie (NDSS 2025) zeigt, dass in shared Vector-Indexen ohne Tenant-Filter bis zu 95 Prozent benigner Queries Cross-Tenant-Daten zurueckgeben. Zusaetzlich erlaubt KV-Cache-Sharing in vLLM oder SGLang Timing-Attacks, bei denen Tenant A Prefixe von Tenant B per Time-To-First-Token rekonstruiert. OWASP LLM08:2025 fuehrt Vector- und Embedding-Schwaechen explizit als eigene Kategorie. Pflicht-Pattern sind: Tenant-ID als expliziter Parameter auf jeder Funktion, Postgres Row-Level-Security als Defense-in-Depth, `cache_salt` pro Tenant in vLLM und Cross-Tenant-Leak-Tests in CI.

```python
# Anwendungsschicht erzwingt Filter
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
    # vLLM cache_salt verhindert KV-Cache-Bleed quer ueber Tenants
    return await vllm.chat.completions.create(
        model="llama-3.1-70b",
        messages=messages,
        extra_body={"cache_salt": f"tenant-{tenant_id}-2026"},
    )
```

```sql
-- Postgres RLS als Backstop, falls App-Filter umgangen wird
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON documents
  USING (tenant_id = current_setting('app.tenant_id')::uuid);

-- Pro Request gesetzt
SET LOCAL app.tenant_id = '7c1e...';
```

Sensitivitaetsabhaengig waehlt man zwischen *Silo* (ein Index pro Tenant), *Pool* (shared Index mit Pflicht-Filter) oder *Bridge* (High-Risk im Silo, Rest im Pool).

**Anti-Pattern**
- Globaler Vector-Store ohne Metadaten-Filter, "wir filtern im UI".
- Semantic Cache, der Hits cross-tenant liefert, oder shared System-Prompt mit Tenant-Daten.

**Checkliste**
- [ ] Vector-Query ohne Tenant-Filter wirft `SecurityError`.
- [ ] Postgres RLS aktiv auf allen mandantenfaehigen Tabellen.
- [ ] `cache_salt` pro Tenant in vLLM/SGLang gesetzt.
- [ ] Semantic-Cache trennt Keyspaces nach Tenant.
- [ ] CI-Test: Query als Tenant A, assert keine Tenant-B-Docs.

Quellen: [NDSS 2025 PROMPTPEEK](https://www.ndss-symposium.org/wp-content/uploads/2025-1772-paper.pdf), [vLLM cache_salt](https://docs.vllm.ai/en/stable/design/prefix_caching/), [Mavik Multi-Tenant RAG 2026](https://www.maviklabs.com/blog/multi-tenant-rag-2026), [OWASP LLM Top 10](https://genai.owasp.org/llm-top-10/).

---

### 11.8 PII und Datenklassifizierung

Mitarbeiter und Agenten schicken Personendaten unbedacht an externe LLM-APIs. Daraus folgen Verstoesse gegen GDPR Art. 6, 9, 32, HIPAA bei medizinischen Daten und PCI bei Kreditkarten. Zusaetzlich persistiert Agent-Memory PII fuer Wochen, sodass GDPR Art. 17 (Right to be forgotten) ohne sauberes Memory-Indexing technisch nicht erfuellbar ist. Das Standard-Pattern 2026 ist Pre-Call-Redaction mit Microsoft Presidio plus optionalem Output-Reverse-Mapping. Die Redaction laeuft VOR jedem externen Provider-Call und auch auf Tool-Outputs, die zurueck ins Kontextfenster gehen.

```python
# LiteLLM + Presidio: Pre-Call-Redaction mit Reverse-Mapping
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig
import litellm, re

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
    results = analyzer.analyze(text=text, language="de")
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
    audit_log(user_id=user_id, redacted_in=redacted)  # nie raw
    resp = await litellm.acompletion(
        model="claude-sonnet-4-5",
        messages=[{"role": "user", "content": redacted}],
    )
    return restore(resp.choices[0].message.content, mapping)

# GDPR Art. 17 -- pro User indizierter Memory-Store
def forget_user(user_id: str):
    memory_store.delete_by_user(user_id)
    embedding_index.delete(filter={"user_id": user_id})
    audit_store.mark_for_purge(user_id)
```

**Anti-Pattern**
- Raw-Prompts in Datadog/Splunk-Logs ohne Redaction.
- Konversations-History in einer Vector-Collection ohne User-Indexing; DSAR nicht erfuellbar.

**Checkliste**
- [ ] Pre-Call-Redaction vor jedem externen LLM-Call.
- [ ] Tool-Outputs ebenfalls durch Redaction-Layer.
- [ ] Memory per `user_id` indiziert, Loeschung in unter 30 Tagen.
- [ ] Application-Logs enthalten keine Raw-Prompts.
- [ ] DPA mit allen Providern, Sub-Processors gelistet.

Quellen: [Microsoft Presidio](https://github.com/microsoft/presidio), [LiteLLM Presidio Guardrail](https://docs.litellm.ai/docs/tutorials/presidio_pii_masking), [Ploomber: Preventing PII leakage](https://ploomber.io/blog/presidio/), [PII Redaction Pipeline](https://redteams.ai/topics/walkthroughs/defense/pii-redaction-pipeline).

<!-- KAP 11 ENDE / KAP 12 START -->

---

### 12.4 SLOs und Rate Limits

LLM-Latenz ist hochvariant (P50 1s, P99 30s sind keine Seltenheit). Provider-Outages bei OpenAI und Anthropic treten regelmaessig auf. Ohne Token-Quotas pro Tenant kann ein einzelner Power-User das Budget der gesamten Plattform aufbrauchen, ein Effekt, der inzwischen als "denial-of-wallet" benannt wird. Standard-Pattern 2026: explizite SLO-Tabelle pro Endpoint (TTFT, Total-Time, Error-Rate) als P50/P95/P99, Token-Bucket pro Tenant mit getrennten Limits fuer Input- und Output-Tokens, mindestens ein konfigurierter Provider-Failover via AI-Gateway, und Backpressure als Queue mit Timeout statt hartem Reject.

| Metrik | P50 | P95 | P99 |
|---|---|---|---|
| Time-to-First-Token | 400ms | 1.2s | 3s |
| Total-Response-Time | 2s | 8s | 20s |
| Tool-Call-Roundtrip | 200ms | 800ms | 2s |
| Error-Rate | <0.5% | -- | -- |

```python
# Tenant-Quota-Check + Backpressure + Provider-Failover
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

Im HTTP-Layer wird `QuotaExceeded` zu `429` mit `Retry-After`-Header.

**Anti-Pattern**
- Globale Rate-Limits ohne Tenant-Splitting; ein Kunde blockiert alle anderen.
- Identische Limits fuer Input- und Output-Tokens; Output ist rund viermal teurer.

**Checkliste**
- [ ] SLO-Tabelle (TTFT, Total, Error) pro Endpoint dokumentiert.
- [ ] Token-Bucket pro Tenant, Input und Output getrennt.
- [ ] Mindestens ein Provider-Failover konfiguriert und getestet.
- [ ] Streaming aktiv, TTFT als primaere Latency-SLO.
- [ ] Backpressure via Semaphore/Queue, nicht harter Reject.

Quellen: [OpenRouter Latency](https://openrouter.ai/docs/guides/best-practices/latency-and-performance), [Inworld Best LLM Gateways 2026](https://inworld.ai/resources/best-llm-gateways), [Maxim Top LLM Gateways 2026](https://www.getmaxim.ai/articles/top-5-llm-gateways-for-2026-a-comprehensive-comparison/).

---

### 12.5 Audit Logs

SOC2, HIPAA und GDPR verlangen nachvollziehbare Audit-Trails, aber Prompts und Responses koennen PII, Geschaeftsgeheimnisse oder Auth-Tokens enthalten. Naive "log everything"-Ansaetze schaffen einen Compliance-Albtraum statt ihn zu loesen. Stand 2026 sind die OpenTelemetry GenAI Semantic Conventions produktionsreif, mit nativem Support in Datadog v1.37+, Sentry, Langfuse und Helicone. Geloggt werden Tenant- und User-ID (gehasht), Modell, Token-Counts, Tool-Call-Namen, Cache-Hits. Klartext-Prompts und -Completions kommen per default NICHT als Span-Attribute, sondern als Hash-Referenz in separates WORM-Storage (S3 Object Lock im COMPLIANCE-Mode).

```python
# OpenTelemetry GenAI Semantic Conventions, Python
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
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
        # Compliance-Felder
        span.set_attribute("tenant.id", tenant_id)
        span.set_attribute("enduser.id",
                           hashlib.sha256(user_id.encode()).hexdigest())
        span.set_attribute("gen_ai.agent.id", agent_id)
        # Prompt-Hash statt Klartext, Klartext in WORM
        prompt_blob = json.dumps(messages, sort_keys=True).encode()
        prompt_hash = hashlib.sha256(prompt_blob).hexdigest()
        span.set_attribute("gen_ai.prompt.hash", prompt_hash)
        worm_storage.put(f"prompts/{prompt_hash}", prompt_blob)
        for tc in tool_calls:
            span.add_event("gen_ai.tool.call", attributes={
                "tool.name": tc.name,
                # Args hashen, da Auth-Tokens drin landen koennen
                "tool.args.hash": hashlib.sha256(
                    json.dumps(tc.args).encode()).hexdigest(),
            })
```

WORM-Storage: AWS S3 Object Lock im COMPLIANCE-Mode mit Retention je nach Regime (SOC2 1 Jahr, HIPAA 6 Jahre, GDPR Zweckbindung). KMS-Verschluesselung Pflicht.

**Anti-Pattern**
- Volle Prompts in Application-Logs (stdout zu Datadog) ohne Redaction.
- Custom-Schema statt OTel GenAI Semantic Conventions; Vendor-Lock-in, kein Tooling-Support.

**Checkliste**
- [ ] OTel GenAI Semantic Conventions als Schema, nicht Custom.
- [ ] Klartext-Prompts/Completions in WORM-Storage, Hash im Span.
- [ ] Tenant-ID und gehashte User-ID auf jedem Span.
- [ ] Retention je Compliance-Regime (SOC2 1y, HIPAA 6y).
- [ ] S3 Object Lock COMPLIANCE-Mode, KMS-verschluesselt.

Quellen: [OTel GenAI Spans](https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-spans/), [OTel Agentic Spans](https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-agent-spans/), [Datadog OTel GenAI](https://www.datadoghq.com/blog/llm-otel-semantic-convention/), [OpenObserve OTel for LLMs 2026](https://openobserve.ai/blog/opentelemetry-for-llms/).

---

### 12.6 Rollback und Incident Response

Prompt-Aenderungen sind Deployments. Ein neuer System-Prompt kann silent die Hallucination-Rate verdoppeln, ohne dass Staging-Tests es zeigen. Ohne Canary plus Auto-Rollback gehen Aenderungen blind in Produktion. Stand 2026 etabliert: Prompt-Versioning in Git, Canary-Rollout mit statistischer Signifikanz vor Promote (Stages 5/25/50/100 Prozent), Auto-Rollback bei Metric-Degradation, Blue/Green fuer Agent-Versionen via Feature-Flag, und differenzierte Runbooks pro Failure-Mode (Hallucination-Spike, Tool-Failure, Cost-Anomaly, Latency-Spike). Vercel Agent Investigations korreliert Logs und Metriken um den Alert-Zeitpunkt automatisch, Sentry instrumentiert `gen_ai.invoke_agent`-Spans nativ.

```yaml
# runbooks/hallucination-spike.yaml -- ausfuehrbar als Tool
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
// Vercel Rolling Release mit Auto-Rollback-Schwelle
import { unstable_rolloutFlag } from "@vercel/flags";

export const promptVersion = unstable_rolloutFlag("prompt_v3", {
  rolloutPercent: 5,
  rolloutStages: [5, 25, 50, 100],
  rollbackOn: {
    metrics: ["hallucination_rate", "p95_latency",
              "error_rate", "cost_per_request"],
    thresholds: {
      hallucination_rate: 1.5,   // 1.5x Baseline -> Rollback
      p95_latency:        1.3,
      error_rate:         2.0,
      cost_per_request:   1.4,
    },
  },
});
```

Trace-ID muss durch alle Sub-Agents und Tool-Calls propagiert werden, sonst endet das Tracing am Agent-Eingang.

**Anti-Pattern**
- Prompts werden direkt in Production editiert, kein Versioning, kein Diff im PR-Review.
- Generische "Agent kaputt"-Alerts ohne Failure-Mode-Differenzierung (Timeout vs. Hallucination vs. Tool-Error vs. Context-Overflow).

**Checkliste**
- [ ] Prompts versioniert in Git, jeder Change im PR-Review.
- [ ] Canary mit Auto-Rollback auf Hallucination, Latency, Cost, Error.
- [ ] Runbooks fuer mind. 4 Failure-Modes vorhanden.
- [ ] Trace-ID propagiert durch alle Sub-Agents und Tool-Calls.
- [ ] Mean-Time-To-Recovery unter 10 Minuten dokumentiert.

Quellen: [Vercel Rolling Releases](https://vercel.com/docs/rolling-releases), [Vercel Agent](https://vercel.com/docs/agent), [Sentry Multi-Agent Observability](https://blog.sentry.io/scaling-observability-for-multi-agent-ai-systems/), [Canary Deployments for LLMs](https://medium.com/@oracle_43885/canary-deployments-for-securing-large-language-models-48393fa68efc).

---

### 12.7 Kostensteuerung

LLM-Cost ist fuer SaaS-Produkte oft der groesste variable Kostenblock. Ein einzelner Power-User oder ein Loop-Bug kann an einem Tag fuenfstellige Betraege verbrennen. Ohne per-Tenant-Caps, Cache-Hitrate-Monitoring und Modell-Tiering ist die Unit-Economy nicht steuerbar. Pattern 2026: hierarchische Budget-Caps mit progressivem Throttling (70/80/95/100 Prozent), Tier-Routing Haiku zu Sonnet zu Opus auf Basis eines billigen Komplexitaets-Klassifikators (60 bis 90 Prozent Cost-Reduktion laut Industry-Benchmarks), Anthropic Prompt-Caching mit Hit-Rate-Ziel ueber 70 Prozent, Streaming-Cancellation bis zum Provider per `AbortSignal`.

| Threshold | Action |
|---|---|
| 70% | Alert an Tenant + Sales |
| 80% | Soft-Throttle: Routing auf billigeres Modell |
| 95% | Hard-Throttle: Queue oder Reject non-essential |
| 100% | Block, nur essentielle Endpoints |

```typescript
// Tier-Router mit Komplexitaets-Classifier + Budget-Awareness
import Anthropic from "@anthropic-ai/sdk";

const client = new Anthropic();

type Tier = "haiku" | "sonnet" | "opus";

interface TenantState {
  spentToday: number;
  dailyCap: number;
}

async function classifyComplexity(q: string): Promise<Tier> {
  // Billiges Haiku-Call, ~1ms, ~$0.0001
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

  // Progressive Degradation
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
      cache_control: { type: "ephemeral" }, // bis zu 90% billiger
    }],
    messages: [{ role: "user", content: query }],
    stream: true,
  }, { signal });  // Streaming-Cancellation propagiert bis zum Provider
}
```

Auf Anwendungsebene: `req.on("close", () => controller.abort())`, sodass abandoned Streams nicht weiter Tokens produzieren. Cache-Hitrate (`cache_read_input_tokens / input_tokens`) gehoert auf das primaere Cost-Dashboard.

**Anti-Pattern**
- Premium-Modell als Default fuer alle Queries, kein Tiering.
- Kein Streaming-Cancel; abandoned Streams produzieren weiter Tokens und Kosten.

**Checkliste**
- [ ] Per-Tenant-Daily-Cap, progressives Throttling bei 70/80/95/100%.
- [ ] Modell-Tiering aktiv, Trivial-Queries auf Haiku/Mini-Tier.
- [ ] Prompt-Caching aktiv, Hit-Rate-Dashboard, Ziel >70%.
- [ ] `AbortSignal` propagiert bis zum Provider.
- [ ] Cost-Attribution pro Tenant/Feature/User im Dashboard.

Quellen: [Clarifai AI Cost Controls](https://www.clarifai.com/blog/ai-cost-controls), [Maxim Reduce LLM Cost 2026](https://www.getmaxim.ai/articles/reduce-llm-cost-and-latency-a-comprehensive-guide-for-2026/), [Redis LLM Token Optimization](https://redis.io/blog/llm-token-optimization-speed-up-apps/), [LLM Agent Cost Attribution 2026](https://www.digitalapplied.com/blog/llm-agent-cost-attribution-guide-production-2026).
