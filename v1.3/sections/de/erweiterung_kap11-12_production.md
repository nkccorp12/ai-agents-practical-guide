### 11.5 Identity und Auth

In Multi-User-Agentensystemen ruft ein Agent nachgelagerte Tools, MCP-Server und APIs auf, deren Zugriffe an die Berechtigungen einer realen Person gebunden sind. Wenn der Agent unter einer technischen Service-Identitaet operiert, geht der Nutzungs-Kontext verloren. Die Folge sind Privilege-Escalation, der klassische "Confused Deputy" und unbrauchbare Audit-Logs. Anfang 2026 wurde explizit dokumentiert, dass Microsoft Foundry Agents in M365 Copilot die OAuth-Identity nicht durchreichen, sondern unter App-Identitaet operieren [Quelle: ceposta, https://blog.christianposta.com/explaining-on-behalf-of-for-ai-agents/].

Der etablierte Loesungsweg ist OAuth On-Behalf-Of (OBO) nach RFC 8693 (Token Exchange) mit dem `act`-Claim aus RFC 9068. Der Agent erhaelt vom Authorization-Server ein delegiertes Access-Token, das sowohl den User (`sub`) als auch den Agent (`act.sub`) traegt. Resource-Server validieren beide Identitaeten und schneiden Scopes auf den Schnitt aus User-Permissions, Agent-Permissions und angefragten Scopes (Capability-Attenuation). Multi-Hop-Delegation (Agent A -> Agent B -> API) verschachtelt `act` rekursiv.

```python
# Token-Exchange nach RFC 8693 -- Agent tauscht User-Token gegen delegiertes Token
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
    return claims  # claims["sub"] = User, claims["act"]["sub"] = Agent

# Resource-Server: Audit auf Agent-Pfad branchen
claims = verify_obo(token, jwks)
audit.record(user=claims["sub"], agent=claims["act"]["sub"],
             scopes=claims["scope"].split(), action="crm.write")
```

Anti-Pattern:
- Service-Account-Token mit Superuser-Rechten als gemeinsame Agent-Identity, sodass jeder Tool-Call wie der gleiche Bot aussieht.
- User-Tokens in System-Message oder Prompt einbetten, wo sie in Logs und KV-Cache landen.

Checkliste:
- [ ] Jeder Tool-Call traegt User-Identity (`sub`) UND Agent-Identity (`act.sub`).
- [ ] Scopes werden auf `intersection(user, agent, requested)` reduziert.
- [ ] PKCE Pflicht, Authorization-Codes single-use.
- [ ] Consent-UI nennt den Agent explizit beim Namen.
- [ ] Audit-Log persistiert User+Agent+Action+Tool+Resource pro Call.

---

### 11.6 Secret-Handling

MCP-Server aggregieren Dutzende API-Keys, DB-Passwoerter und OAuth-Tokens, oft in unverschluesselten Config-Dateien. Tokens landen versehentlich in Prompts, Logs, Memory oder KV-Caches. OWASP MCP01:2025 (Token Mismanagement & Secret Exposure) ist 2026 die haeufigste MCP-Schwachstelle [Quelle: https://www.willvelida.com/posts/preventing-mcp01-token-mismanagement-secret-exposure]. Das Leitprinzip lautet: der Agent-Prozess haelt zur Laufzeit kein langlebiges Credential, sondern bezieht Session-scoped Tokens mit Hard-Expiry (15 min) aus einem Vault.

```python
# Vault-Bezug zur Laufzeit, kurze TTL, niemals im Prompt sichtbar
import time, hmac
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

cred = DefaultAzureCredential()  # Managed Identity in Prod
kv = SecretClient(vault_url="https://kv.example.net", credential=cred)

class SessionSecret:
    """Session-scoped Token, TTL <= 15 min (OWASP MCP01:2025)."""
    HARD_EXPIRY = 15 * 60

    def __init__(self, name: str):
        self.name, self._val, self._exp = name, None, 0

    def get(self) -> str:
        if time.time() > self._exp:
            self._val = kv.get_secret(self.name).value
            self._exp = time.time() + self.HARD_EXPIRY
        return self._val

def authorized(presented: str, expected: str) -> bool:
    # Constant-Time-Compare gegen Timing-Attacks
    return hmac.compare_digest(presented.encode(), expected.encode())

# OTel-Redaction: Auth-Header NIE in Spans exportieren
def redact_span(span):
    for k in ("http.request.header.authorization", "tool_call.arguments"):
        if span.attributes.get(k):
            span.set_attribute(k, "[REDACTED]")
```

Anti-Pattern:
- API-Keys als Environment-Variablen, die der Agent direkt aus `os.environ` lesen kann (lecken in Tool-Outputs und Stack-Traces).
- Secrets in System-Message oder Tool-Description, wo sie im KV-Cache und Audit-Log persistieren.

Checkliste:
- [ ] Kein Secret im Repo, in `.env`-Files committed oder im Container-Image.
- [ ] Secrets nur zur Laufzeit, TTL <= 15 min.
- [ ] Auto-Rotation alle 60 bis 90 Tage (oder kuerzer fuer dynamische Secrets).
- [ ] Telemetry-Pipeline redigiert Auth-Header und Token-Felder.
- [ ] Constant-Time-Comparison fuer Key-Validation.

---

### 11.7 Mandantentrennung

Multi-Tenant-RAG- und Agentensysteme leaken zwischen Kunden, sobald nur eine Schicht den Tenant-Filter vergisst. OWASP LLM Top 10 v2025 hat LLM08:2025 als eigene Kategorie fuer Vector-/Embedding-Schwaechen eingefuehrt [Quelle: https://genai.owasp.org/llm-top-10/]. Studien aus 2025 (PROMPTPEEK, NDSS) zeigen, dass in shared Vector-Indexen ohne Tenant-Filter bis zu 95 Prozent benigner Queries Cross-Tenant-Leaks ausloesen, und KV-Cache-Sharing in vLLM/SGLang ermoeglicht Timing-Attacks, ueber die Tenant A Prefixe von Tenant B aus der Time-To-First-Token rekonstruiert [Quelle: https://www.ndss-symposium.org/wp-content/uploads/2025-1772-paper.pdf]. Tenant-ID muss explizit durch jede Schicht gereicht werden: Embedding, Vector-Store, Cache, Memory, Logging.

```python
# 1) App-Layer-Filter PFLICHT, sonst SecurityError
class SecurityError(Exception): ...

def retrieve(query: str, tenant_id: str, k: int = 5):
    if not tenant_id:
        raise SecurityError("Tenant filter mandatory")
    return vector_store.query(
        query_embedding=embed(query),
        filter={"tenant_id": {"$eq": tenant_id}},
        top_k=k,
    )

# 2) KV-Cache-Bleed-Praevention (vLLM cache_salt)
def llm_call(messages, tenant_id: str):
    return llm.chat(
        model="llama-3.1-70b",
        messages=messages,
        extra_body={"cache_salt": f"tenant:{tenant_id}"},
    )
```

```sql
-- 3) Postgres Row-Level-Security als Defense-in-Depth
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON documents
  USING (tenant_id = current_setting('app.tenant_id')::uuid);

-- pro Request in der Connection setzen:
SET LOCAL app.tenant_id = '7f3c...e9a1';
```

Anti-Pattern:
- Globaler Vector-Store ohne Metadaten-Filter, Tenant-Trennung "spaeter im UI".
- Semantischer Cache, der Hits ueber Tenants hinweg liefert oder Knowledge-Graph-Expansion ohne erneuten Authz-Check.

Checkliste:
- [ ] Jede Vector-Query enthaelt `tenant_id`-Filter, sonst SecurityError.
- [ ] Postgres RLS aktiviert auf allen mandantenfaehigen Tabellen.
- [ ] Prompt-Cache wird per Tenant gesalted oder ist deaktiviert.
- [ ] Semantic-Cache trennt Keyspaces nach Tenant.
- [ ] Cross-Tenant-Leak-Test in CI: Query als Tenant A, assert keine Tenant-B-Treffer.

---

### 11.8 PII und Datenklassifizierung

Mitarbeitende und Agenten schicken Personendaten unbedacht an externe LLM-APIs. Daraus folgen GDPR-Verstoesse (Art. 6, 9, 32), HIPAA-Verstoesse bei medizinischen Daten und PCI-Verstoesse bei Kreditkarten. Kritisch ist Agent-Memory: persistierte PII verstoesst gegen das Right-to-be-forgotten (GDPR Art. 17), wenn Memories nicht per User indiziert sind. Loesungs-Pattern ist eine Pre-Call-Redaction-Pipeline mit Microsoft Presidio plus Output-Reverse-Mapping, sodass das Modell nur Tokens wie `<PERSON_1>` sieht, der User aber den Klartext zurueckbekommt [Quelle: https://docs.litellm.ai/docs/tutorials/presidio_pii_masking].

```python
# LiteLLM Pre-Call-Redaction mit Presidio + per-User-Memory-Loeschung
from litellm import completion
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine

analyzer, anonymizer = AnalyzerEngine(), AnonymizerEngine()

def redact(text: str) -> tuple[str, dict]:
    res = analyzer.analyze(text=text, language="de",
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
                pii_entities=list(mapping.keys()))   # nur Typ, nicht Wert
    resp = completion(model="claude-sonnet-4-5",
                      messages=[{"role": "user", "content": redacted}])
    return restore(resp.choices[0].message.content, mapping)

# GDPR Art. 17: Right-to-be-forgotten in Agent-Memory
def forget_user(user_id: str):
    memory_store.delete_by_user(user_id)         # Embeddings + Konversations-Logs
    semantic_cache.invalidate(prefix=f"u:{user_id}")
    audit.write(action="gdpr.erasure", subject=user_id)
```

Anti-Pattern:
- Raw-Prompts in Application-Logs (Datadog, Splunk) ohne Redaction.
- Konversations-History in einer einzigen Vector-Collection ohne User-Indexing, sodass DSAR (Data Subject Access Request) nicht erfuellbar ist.

Checkliste:
- [ ] Pre-Call-Redaction vor jedem externen LLM-Provider-Call.
- [ ] Tool-Outputs werden ebenfalls durch den Redaction-Layer geschickt.
- [ ] Agent-Memory ist per User indiziert, Loeschung in unter 30 Tagen umsetzbar.
- [ ] Application-Logs enthalten keine Raw-Prompts oder PII.
- [ ] DPA mit allen LLM-Providern, Sub-Processors gelistet.

<!-- KAP 12 -->
---

### 12.4 SLOs und Rate Limits

LLM-Latenz ist hochvariant (P50 1 s, P99 30 s sind nicht selten), Provider-Outages bei OpenAI und Anthropic treten regelmaessig auf, und ohne Token-Quotas pro Tenant kann ein einzelner Kunde das gesamte Budget der Plattform aufbrauchen ("Denial-of-Wallet"). Produktionsreife Systeme definieren explizite Latenz-Budgets pro Endpoint (P50/P95/P99), trennen Buckets fuer Input- und Output-Tokens (Output ist rund 4x teurer) und verteilen Last ueber AI-Gateways mit Provider-Failover.

| Metrik | P50 | P95 | P99 |
|---|---|---|---|
| Time-to-First-Token | 400 ms | 1.2 s | 3 s |
| Total-Response-Time | 2 s | 8 s | 20 s |
| Tool-Call-Roundtrip | 200 ms | 800 ms | 2 s |
| Error-Rate | < 0.5 % | -- | -- |

```python
# Tenant-Quota-Check + Backpressure + Provider-Failover
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
        for provider in ["anthropic", "openai", "google"]:   # Failover
            try:
                return await asyncio.wait_for(
                    llm_call(provider, req), timeout=30
                )
            except (asyncio.TimeoutError, ProviderError):
                continue
        return cached_or_degraded_response(req)
```

Provider-Failover wird in 2026 fast immer ueber Vercel AI Gateway oder OpenRouter realisiert, weil beide Multi-Provider mit unter 40 ms Overhead liefern [Quelle: https://openrouter.ai/docs/guides/best-practices/latency-and-performance].

Anti-Pattern:
- Globale Rate-Limits ohne Tenant-Splitting, sodass ein Kunde alle anderen blockiert.
- Hard-Reject bei 100 Prozent statt Graceful-Degradation auf billigeres Modell.

Checkliste:
- [ ] SLO-Tabelle (P50/P95/P99 fuer TTFT, Total-Time, Error-Rate) pro Endpoint dokumentiert.
- [ ] Token-Bucket pro Tenant, getrennte Limits fuer Input und Output.
- [ ] Mindestens ein Provider-Failover konfiguriert und getestet.
- [ ] Streaming aktiv, TTFT als primaeres Latency-SLO.
- [ ] Backpressure via Semaphore oder Queue, nicht harter Reject.

---

### 12.5 Audit Logs

SOC2, HIPAA und GDPR verlangen nachvollziehbare Audit-Trails, aber Prompts und Responses koennen PII, Geschaeftsgeheimnisse und Auth-Tokens enthalten. Naive "log everything"-Ansaetze schaffen einen Compliance-Albtraum statt ihn zu loesen. Stand 2026 sind die OpenTelemetry GenAI Semantic Conventions produktionsreif (Datadog v1.37+, Sentry, Langfuse, Helicone unterstuetzen sie nativ), und Custom-Schemas erzeugen Vendor-Lock-in [Quelle: https://opentelemetry.io/docs/specs/semconv/gen-ai/]. Geloggt werden Tenant-ID, gehashte User-ID, Tool-Calls, Token-Counts und Cache-Hits, aber NICHT Klartext-Prompts, wenn PII moeglich ist. Prompts und Completions wandern als Hash-Referenz in WORM-Storage (S3 Object Lock COMPLIANCE-Mode, 7 Jahre fuer HIPAA).

```python
# OpenTelemetry GenAI Semantic Conventions (Stand 2026)
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
        # Prompt NICHT inline, nur Referenz auf WORM-Storage
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
# AWS S3 Object Lock fuer Compliance-konforme WORM-Storage
audit_logs:
  bucket: org-audit-2026
  storage_class: GLACIER_IR
  object_lock:
    mode: COMPLIANCE          # NICHT GOVERNANCE
    retention_days: 2555      # 7 Jahre fuer HIPAA
  encryption: aws:kms
```

Retention-Regime: SOC2 mindestens 1 Jahr, HIPAA 6 Jahre und BAA mit Provider, GDPR Zweckbindung mit dokumentierter Loeschfrist.

Anti-Pattern:
- Volle Prompts und Completions in stdout-/Datadog-Logs ohne Redaction.
- Logs in mutablem Storage (S3 ohne Object Lock) -- Compliance-Auditor lehnt ab.

Checkliste:
- [ ] OpenTelemetry GenAI Semantic Conventions als Schema, nicht Custom.
- [ ] Prompts/Completions nicht im Span, sondern als Hash-Referenz in WORM-Storage.
- [ ] Tenant-ID und gehashte User-ID auf jedem Span.
- [ ] Retention-Policy je Compliance-Regime (SOC2 1y, HIPAA 6y, GDPR Zweckbindung).
- [ ] Audit-Storage immutable (S3 Object Lock COMPLIANCE-Mode).

---

### 12.6 Rollback und Incident Response

Prompt-Aenderungen sind Deployments. Ein neuer System-Prompt kann die Hallucination-Rate verdoppeln, ohne dass Tests in Staging es zeigen, weil Staging nicht den Traffic-Mix von Produktion hat. Ohne Canary mit Auto-Rollback gehen Aenderungen blind live. Zusaetzlich brauchen Tool-Failures, Hallucination-Spikes und Cost-Anomalien jeweils eigene Runbooks, weil ein generischer "Agent kaputt"-Alert keine Aktion ermoeglicht. Vercel Agent Investigations (AI-gestuetzte Root-Cause-Analyse) und Sentry GenAI-Auto-Instrumentation sind 2026 die Referenz-Tools dafuer [Quelle: https://vercel.com/docs/agent].

```ts
// Vercel Rolling Releases -- Canary mit Auto-Rollback bei Metric-Degradation
import { unstable_rolloutFlag } from "@vercel/flags";

export const promptVersion = unstable_rolloutFlag("prompt_v3", {
  rolloutPercent: 5,
  rolloutStages: [5, 25, 50, 100],
  rollbackOn: {
    metrics: ["hallucination_rate", "p95_latency", "cost_per_request"],
    thresholds: {
      hallucination_rate: 1.5,   // 1.5x 7-Tage-Baseline
      p95_latency: 1.3,
      cost_per_request: 1.5,
    },
    minSampleSize: 500,          // statistische Signifikanz vor Promote
  },
});
```

Beispiel-Runbook fuer einen Hallucination-Spike als ausfuehrbares Markdown:

```markdown
# Runbook: Hallucination-Spike

**Trigger:** `hallucination_rate > 2x 7d-baseline` ueber 15 min Fenster
**Severity:** High
**Owner:** AI-Platform-Oncall

## Schritte
1. **Snapshot** aktueller Prompt-Diff: `git log -p prompts/ -n 5`
2. **Pruefe Modell-Version:**
   `otel query 'gen_ai.response.model' | group by hour, last 6h`
   -> Provider hat eventuell still gepatcht (z.B. claude-sonnet-4-5-20260315 -> -20260418).
3. **Rollback Canary:** `vercel rolling-release rollback --to-stable`
4. **Bestaetige Recovery:** `hallucination_rate < 1.2x baseline` in Folgefenster.
5. **Page Oncall** falls Recovery > 10 min ausbleibt.
6. **Post-Mortem** binnen 24 h, Root-Cause + Test-Coverage-Gap dokumentieren.
```

Weitere Runbooks (gleiches Format) fuer Tool-Failure (Circuit-Break, Fallback-Antwort) und Cost-Anomaly (Top-3-Power-User identifizieren, Modell auf Haiku-Tier downgraden, Slack-Alert).

Anti-Pattern:
- Prompts werden direkt in Produktion editiert, kein Versioning, kein Diff im PR-Review.
- Generische "Agent kaputt"-Alerts ohne Differenzierung zwischen Timeout, Hallucination, Tool-Error und Context-Overflow.

Checkliste:
- [ ] Prompts versioniert in Git, jeder Change im PR-Review.
- [ ] Canary-Rollout mit Auto-Rollback bei Metric-Degradation aktiv.
- [ ] Runbooks fuer mindestens 4 Incident-Klassen: Hallucination, Tool-Failure, Cost-Spike, Latency-Spike.
- [ ] Trace-ID propagiert durch alle Sub-Agents und Tool-Calls.
- [ ] Failure-Modes differenziert (Timeout/Tool-Error/Hallucination/Context-Overflow).

---

### 12.7 Kostensteuerung

LLM-Cost ist fuer SaaS-Produkte oft der groesste variable Kostenblock. Ein einzelner Power-User oder ein Loop-Bug kann an einem Tag fuenfstellige Betraege verbrennen ("Denial-of-Wallet"). Ohne per-Tenant-Caps, Cache-Hitrate-Monitoring und Modell-Tiering ist die Unit-Economy nicht steuerbar. Bewaehrt sind hierarchisches Throttling bei den Schwellen 70/80/95/100 Prozent (Alert -> Soft-Throttle -> Hard-Throttle -> Block) und Modell-Tiering, das triviale Queries auf Haiku-Tier routet und nur Komplexes auf Sonnet oder Opus eskaliert. Industry-Benchmarks zeigen 60 bis 90 Prozent Cost-Reduktion gegenueber Single-Tier-Setups [Quelle: https://www.clarifai.com/blog/ai-cost-controls].

```ts
// Tier-Router mit Streaming-Cancellation und Budget-Cap
import { Anthropic } from "@anthropic-ai/sdk";

const client = new Anthropic();
type Tier = "haiku" | "sonnet" | "opus";

const MODEL: Record<Tier, string> = {
  haiku:  "claude-haiku-4-5",     // ~$0.25 / MTok in
  sonnet: "claude-sonnet-4-5",    // ~$3 / MTok in
  opus:   "claude-opus-4-5",      // ~$15 / MTok in
};

async function classifyTier(query: string): Promise<Tier> {
  // kleines Modell fuer Routing, ~1-5 ms
  const c = await client.messages.create({
    model: MODEL.haiku,
    max_tokens: 8,
    messages: [{ role: "user", content:
      `Tier (haiku|sonnet|opus) fuer: ${query.slice(0, 400)}` }],
  });
  return (c.content[0] as any).text.trim() as Tier;
}

async function tierRoute(query: string, tenant: string, signal: AbortSignal) {
  // 1) Hierarchischer Budget-Cap
  const used = await budget.usage(tenant);
  if (used.pct >= 1.0) throw new Error("Budget exhausted");
  if (used.pct >= 0.95) return degradedFallback(query);   // Hard-Throttle
  let tier = await classifyTier(query);
  if (used.pct >= 0.80 && tier === "opus")  tier = "sonnet";  // Soft-Throttle
  if (used.pct >= 0.80 && tier === "sonnet") tier = "haiku";

  // 2) Streaming + Cancellation, damit abgebrochene UIs nicht weiter Tokens fressen
  const stream = await client.messages.stream({
    model: MODEL[tier],
    system: [{ type: "text", text: SYSTEM_PROMPT,
               cache_control: { type: "ephemeral" } }],   // 90% billiger bei Cache-Hit
    messages: [{ role: "user", content: query }],
    max_tokens: 1024,
  }, { signal });

  // 3) Hit-Rate-Monitoring
  const res = await stream.finalMessage();
  metrics.cacheHit.observe({
    tenant, tier,
    ratio: res.usage.cache_read_input_tokens /
           Math.max(1, res.usage.input_tokens),
  });
  return res;
}
```

Anti-Pattern:
- Premium-Modell (Opus, GPT-4) als Default fuer alle Queries, kein Tiering.
- Kein Streaming-Cancel, sodass abandoned Streams weiter Tokens produzieren bis zum `max_tokens`-Limit.

Checkliste:
- [ ] Per-Tenant-Daily-Cap konfiguriert, progressives Throttling bei 70/80/95/100 Prozent.
- [ ] Modell-Tiering aktiv, Trivial-Queries auf Haiku/Mini-Tier geroutet.
- [ ] Anthropic/OpenAI Prompt-Caching aktiv, Hit-Rate-Dashboard existiert (Ziel > 70 Prozent).
- [ ] Streaming-Cancellation propagiert AbortSignal bis zum Provider.
- [ ] Cost-Attribution pro Tenant/Feature/User in Dashboard sichtbar.
