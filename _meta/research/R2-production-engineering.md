# R2 Production Engineering fuer KI-Agent-Systeme

Stand: April 2026. Recherche-Input fuer Praxisbuch v1.3. Acht Themenfelder, jeweils mit Problem, Loesungs-Pattern, Anti-Pattern, Tooling und Mini-Checkliste.

---

## 1. Identity & Auth (User-Identity-Propagation, OAuth, OBO)

### Problem
Agenten rufen Tools/MCP-Server auf, die ihrerseits APIs mit Nutzer-spezifischen Berechtigungen ansprechen (Mail, Calendar, CRM). Wenn der Agent unter einer Service-Identitaet laeuft, geht der User-Kontext verloren -- Folge: Privilege-Escalation, "confused deputy", Audit-Luecken. Frueher 2026 wurde explizit gemeldet, dass Microsoft Foundry Agents in M365 Copilot die OAuth-Identity nicht durchreichen, sondern unter App-Identitaet operieren.

### Loesungs-Pattern
**OAuth On-Behalf-Of (OBO) + RFC 8693 Token Exchange mit `act`-Claim.** Der Agent erhaelt vom Auth-Server ein delegiertes Token, das sowohl den User (`sub`) als auch den Agent (`act.sub`) traegt. Resource-Server validieren beide Identitaeten und schneiden Scopes auf den Schnitt aus User-Permissions, Agent-Permissions und angeforderten Scopes (Capability Attenuation).

```jsonc
// JWT Access Token (RFC 9068) mit OBO-Erweiterung
{
  "iss": "https://auth.example.com",
  "aud": "crm-api",
  "sub": "user-456",
  "azp": "client-id",
  "scope": "read:contacts write:notes",
  "act": { "sub": "agent-finance-v1" },
  "exp": 1746009896
}
```

Multi-Hop (Agent A ruft Agent B, der API foo aufruft) verschachtelt `act` rekursiv:

```http
POST /token
grant_type=urn:ietf:params:oauth:grant-type:token-exchange
&subject_token=ORIGINAL_ACCESS_TOKEN
&subject_token_type=urn:ietf:params:oauth:token-type:access_token
&resource=https://downstream-api.example.com
```

MCP-Server-seitig: Audit nur dann auf Agent-Pfad branchen, wenn `act` gesetzt ist.

```ts
const t = verifyJWT(accessToken);
if (t.act?.sub) {
  audit.record({ user: t.sub, agent: t.act.sub, action });
  // engerer Scope, mehr Logging
}
```

### Anti-Pattern
- Service-Account-Token mit Superuser-Rechten als "shared agent identity" -- jeder Tool-Call sieht aus wie der gleiche Bot.
- User-Token im Prompt oder System-Message einbetten (geht in Logs/KV-Cache).
- Generische Consent-UIs ("Diese App will Zugriff") ohne Agent-Namen.
- Agent darf Tools aufrufen, die mehr koennen als der User selbst (kein Capability-Attenuation).
- Authorization Codes mehrfach verwenden, kein PKCE.

### Tooling 2026
- **Microsoft Entra Agent Identity** (Agent als first-class actor in OBO).
- **WorkOS** -- OAuth-Provider mit OBO-Support fuer AI-Agents.
- **TrueFoundry AI Gateway** -- OBO-Token-Exchange mit Agent-Credentials, sub=user, act=agent.
- **Solo Enterprise / kagent** -- OBO-Implementierung fuer Kubernetes-Agent-Mesh.
- **MuleSoft Agent Fabric** -- "Trusted Agent Identity" fuer Enterprise-Service-Mesh.
- AWS Bedrock AgentCore -- aktive Diskussion, OBO-Token-Pass-Through als Option.

### Checkliste
- [ ] Jeder Tool-Call traegt User-Identity (`sub`) UND Agent-Identity (`act.sub`).
- [ ] Scopes werden auf `intersection(user, agent, requested)` reduziert.
- [ ] PKCE ist Pflicht, Authorization Codes single-use.
- [ ] Consent-UI nennt den Agent explizit beim Namen.
- [ ] Audit-Log persistiert User+Agent+Action+Tool+Resource pro Call.

### Quellen
- [WorkOS: OAuth's On-Behalf-Of flow for AI agents](https://workos.com/blog/oauth-on-behalf-of-ai-agents)
- [Microsoft: OAuth2 OBO flow](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-on-behalf-of-flow)
- [ceposta: Explaining OAuth Delegation, OBO, and Agent Identity](https://blog.christianposta.com/explaining-on-behalf-of-for-ai-agents/)
- [TrueFoundry: Agent Identity and Delegation](https://www.truefoundry.com/docs/ai-gateway/agents/agent-identity-obo)
- [Solo: OBO tokens for kagent](https://docs.solo.io/kagent-enterprise/docs/latest/security/obo/)
- [Heeki Park: Identity-aware MCP servers](https://heeki.medium.com/understanding-oauth2-and-implementing-identity-aware-mcp-servers-221a06b1a6cf)

---

## 2. Secret-Handling (Vault/KMS, Rotation, MCP-API-Keys)

### Problem
MCP-Server aggregieren oft Dutzende API-Keys, DB-Passwoerter, OAuth-Tokens in einer einzigen unverschluesselten Config-Datei. Tokens landen versehentlich in Prompts, Logs, Model-Kontext-Memory oder KV-Caches. OWASP MCP01:2025 (Token Mismanagement & Secret Exposure) ist 2026 die haeufigste MCP-Schwachstelle.

### Loesungs-Pattern
**MCP-Server haelt zur Laufzeit kein langlebiges Credential.** Stattdessen Session-scoped Token, das im Vault auf das echte Credential mappt. Rotation bei 80% der TTL, Hard-Expiry bei 15 Minuten.

```yaml
# config.yaml -- Key Vault Reference statt Plaintext
secrets:
  openai_api_key:
    type: keyvault_ref
    uri: https://my-kv.vault.azure.net/secrets/openai-key
    refresh_interval: 300s   # 5min lokaler Cache
    expires_after: 90d       # automatische Rotation

  github_pat:
    type: vault_dynamic
    backend: hashicorp_vault
    role: github-mcp-readonly
    ttl: 15m
```

```python
# Runtime-Injection statt Build-Time
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

cred = DefaultAzureCredential()  # Managed Identity in Prod
kv = SecretClient(vault_url=KV_URL, credential=cred)

class CachedSecret:
    def __init__(self, name, ttl=300):
        self.name, self.ttl, self._val, self._exp = name, ttl, None, 0
    def get(self):
        if time.time() > self._exp:
            self._val = kv.get_secret(self.name).value
            self._exp = time.time() + self.ttl
        return self._val
```

**Telemetry-Redaction Pflicht.** OpenTelemetry-Enrichment-Callback ueberschreibt Auth-Header mit `[REDACTED]` bevor Spans exportiert werden.

### Anti-Pattern
- Hardcoded Keys im Source-Code oder `.env` im Container-Image.
- Secrets in System-Message oder Tool-Description (landen im KV-Cache und Audit-Log!).
- Persistente Sessions im MCP-Server (`Stateless = false`) -- Tokens akkumulieren im Process-Memory.
- Naive String-Vergleiche fuer API-Keys (Timing-Attack); statt `==` immer `hmac.compare_digest` / `FixedTimeEquals`.
- Ein einziges "super-secret" pro MCP-Server ohne Scope-Aufteilung.

### Tooling 2026
- **HashiCorp Vault MCP Server** -- LLM kann Secrets/Policies via MCP managen, inkl. automatischer Rotation.
- **Azure Key Vault MCP Server** -- Managed Identity + DefaultAzureCredential.
- **Doppler** -- moderne Secret-Plattform mit MCP-Support.
- **Anthropic Managed Agents "vaults"** -- vault-authentifizierte Tool-Calls direkt im Claude API.
- **Stainless MCP Portal** -- API-Key-Management-Best-Practices fuer MCP.

### Checkliste
- [ ] Kein Secret im Repo, in `.env`-Files committed, oder im Container-Image.
- [ ] MCP-Server bezieht Secrets nur zur Laufzeit, mit TTL <= 15min.
- [ ] Auto-Rotation alle 60-90 Tage (oder kuerzer fuer dynamische Secrets).
- [ ] Telemetry-Pipeline redigiert Auth-Header und Token-Felder.
- [ ] Constant-Time-Comparison fuer Key-Validation.

### Quellen
- [Will Velida: Preventing MCP01 Token Mismanagement](https://www.willvelida.com/posts/preventing-mcp01-token-mismanagement-secret-exposure)
- [API Stronghold: MCP Servers Don't Need Long-Lived API Keys](https://www.apistronghold.com/blog/mcp-servers-no-long-lived-api-keys-v2)
- [Doppler: MCP security best practices](https://www.doppler.com/blog/mcp-server-credential-security-best-practices)
- [HashiCorp Vault MCP Server](https://developer.hashicorp.com/vault/docs/mcp-server/prompt-model)
- [Azure Key Vault MCP](https://learn.microsoft.com/en-us/azure/developer/azure-mcp-server/services/azure-mcp-server-for-key-vault)
- [Stainless: MCP Server API Key Management](https://www.stainless.com/mcp/mcp-server-api-key-management-best-practices)
- [Claude API: Authenticate with vaults](https://platform.claude.com/docs/en/managed-agents/vaults)

---

## 3. Mandantentrennung (Multi-Tenancy)

### Problem
Multi-Tenant-RAG- und Agent-Systeme leaken zwischen Kunden. OWASP LLM Top 10 v2025 fuehrte LLM08:2025 als eigene Kategorie fuer Vector-/Embedding-Schwaechen ein. Studien zeigen: in shared Vector-Indexen ohne Tenant-Filter loesen bis zu **95% der "harmlosen" Queries Cross-Tenant-Leaks** aus. Daneben: KV-Cache-Sharing in vLLM/SGLang erlaubt **PROMPTPEEK**-Style-Timing-Attacks, wo Tenant A Prefixe von Tenant B durch Time-To-First-Token rekonstruiert.

### Loesungs-Pattern

**a) Tenant-ID auf jeder Schicht propagieren** -- Ingestion, Embedding, Indexing, Retrieval, Generation, Logging. Jede Funktion hat `tenant_id: str` als expliziten Parameter.

```python
def retrieve(query: str, tenant_id: str, k: int = 5):
    if not tenant_id:
        raise SecurityError("Tenant filter mandatory")
    return vector_store.query(
        query_embedding=embed(query),
        filter={"tenant_id": {"$eq": tenant_id}},  # PFLICHT
        top_k=k,
    )
```

**b) Postgres Row-Level-Security** zusaetzlich zur App-Filter-Logik, als Defense-in-Depth.

```sql
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON documents
  USING (tenant_id = current_setting('app.tenant_id')::uuid);

-- Pro Request:
SET LOCAL app.tenant_id = '<tenant-uuid>';
```

**c) Prompt-Cache-Salting gegen KV-Cache-Bleed** (vLLM unterstuetzt das nativ):

```json
{
  "model": "llama-3.1-70b",
  "messages": [...],
  "cache_salt": "tenant-acme-corp-2026"
}
```

Anthropic Prompt-Caching: Cache ist per-Organisation isoliert, aber bei Self-Hosted (vLLM, SGLang) muss der Salt explizit gesetzt werden -- sonst Cross-Tenant Timing-Leak.

**d) Isolations-Modelle nach Sensitivitaet:**
- *Silo* -- ein Index pro Tenant (sicherste, teuerste Option).
- *Pool* -- shared Index mit mandatorischem `tenant_id`-Filter (skalierbar).
- *Bridge* -- High-Risk-Tenants im Silo, Rest im Pool.

### Anti-Pattern
- Tenant-Filter in Application-Layer **nach** dem Retrieval (kann bei semantischer Cache-Hit-Rueckgabe umgangen werden).
- Globaler Embedding-Index ohne Metadaten-Filter, "wir filtern das im UI".
- Semantic Cache, der ueber Tenants hinweg Hits liefert.
- Knowledge-Graph-Expansion ohne erneuten Authz-Check (autoritativer Hop verlaesst Tenant-Grenze).
- Shared System-Prompt mit Tenant-Daten ("Kunde XY hat folgende Praeferenzen ...") -- landet im Cache.

### Tooling 2026
- **Pinecone, Qdrant, Weaviate** -- alle mit nativer Metadata-Filter-Pflicht-Option.
- **vLLM** -- `cache_salt` per Request fuer KV-Cache-Isolation.
- **LiteLLM Proxy** -- Virtual Keys mit Tenant-Scope, automatische Tenant-Header-Propagation.
- **Blaxel, GoClaw** -- Multi-Tenant-Agent-Runtimes mit eingebauter Isolation.
- **Postgres + pgvector + RLS** -- DB-Level-Isolation als Backstop.

### Checkliste
- [ ] Jede Vector-Query enthaelt `tenant_id`-Filter; SecurityError sonst.
- [ ] Postgres RLS aktiviert auf allen mandantenfaehigen Tabellen.
- [ ] Prompt-Cache wird per Tenant gesalted (oder ist deaktiviert).
- [ ] Semantic-Cache trennt Keyspaces nach Tenant.
- [ ] Cross-Tenant-Leak-Test in CI: Query als Tenant A, assert keine Tenant-B-Docs.

### Quellen
- [Mavik Labs: Multi-Tenant RAG in 2026](https://www.maviklabs.com/blog/multi-tenant-rag-2026)
- [Blaxel: Multi-tenant isolation for AI agents](https://blaxel.ai/blog/multi-tenant-isolation-ai-agents)
- [InstaTunnel: Multi-Tenant Leakage when RLS fails](https://medium.com/@instatunnel/multi-tenant-leakage-when-row-level-security-fails-in-saas-da25f40c788c)
- [NDSS 2025: Prompt Leakage via KV-Cache Sharing](https://www.ndss-symposium.org/wp-content/uploads/2025-1772-paper.pdf)
- [vLLM: Automatic Prefix Caching with cache_salt](https://docs.vllm.ai/en/stable/design/prefix_caching/)
- [LiteLLM: Multi-Tenant Architecture](https://docs.litellm.ai/docs/proxy/multi_tenant_architecture)
- [Multi-Tenant Isolation Challenges in Enterprise LLM Agent Platforms](https://www.researchgate.net/publication/399564099_Multi-Tenant_Isolation_Challenges_in_Enterprise_LLM_Agent_Platforms)

---

## 4. PII & Datenklassifizierung (Presidio, Redaction, GDPR)

### Problem
Mitarbeiter und Agenten schicken Personendaten unbedacht an externe LLM-APIs. GDPR-Verstoss (Art. 6, 9, 32), HIPAA-Verstoss bei medizinischen Daten, PCI bei Kreditkarten. Zusaetzlich: Agent-Memory persistiert PII fuer Wochen, "Right to be forgotten" (GDPR Art. 17) ist ohne Memory-Indexing nicht erfuellbar.

### Loesungs-Pattern
**Pre-Call-Redaction-Pipeline mit Microsoft Presidio**, optional Output-Reverse-Mapping.

```yaml
# LiteLLM Proxy Config -- Presidio als Guardrail
guardrails:
  - guardrail_name: "pii-pre-call"
    litellm_params:
      guardrail: presidio
      mode: "pre_call"
      output_parse_pii: true   # Re-Insertion nach LLM-Antwort
      presidio_score_thresholds:
        CREDIT_CARD: 0.8
        EMAIL_ADDRESS: 0.6
        US_SSN: 0.9
      pii_entities_config:
        US_SSN: "BLOCK"        # harte Verweigerung
        CREDIT_CARD: "BLOCK"
        PERSON: "MASK"         # <PERSON_1> -> Output-Resolve
        EMAIL_ADDRESS: "MASK"
        PHONE_NUMBER: "MASK"
```

```yaml
# docker-compose.yml -- Presidio-Services
services:
  presidio-analyzer:
    image: mcr.microsoft.com/presidio-analyzer:latest
    ports: ["5002:5002"]
  presidio-anonymizer:
    image: mcr.microsoft.com/presidio-anonymizer:latest
    ports: ["5001:5001"]
```

Flow:
1. User: "Mein Name ist Jane Doe, Tel 555-1234"
2. LLM sieht: "Mein Name ist `<PERSON_1>`, Tel `<PHONE_NUMBER_1>`"
3. LLM antwortet: "Hallo `<PERSON_1>`!"
4. User sieht: "Hallo Jane Doe!"

**Right-to-be-forgotten**:
```python
# Memory-Store mit per-User-Indexing
memory.delete_by_user(user_id="user-456")
# loescht alle Embeddings, Konversations-Logs, Cache-Entries
```

**Audit-Trail mit OpenTelemetry-PII-Redaction-Processor** -- Telemetrie-Daten werden in-transit sanitisiert, bevor sie das Backend erreichen.

### Anti-Pattern
- Raw-Prompts in Application-Logs (Datadog, Splunk) ohne Redaction.
- Konversations-History in einer einzigen Vector-Collection ohne User-Indexing -- DSAR (Data Subject Access Request) nicht erfuellbar.
- Nur Regex-basierte Redaction ohne NER -- "Mein Vater Heinz" wird nicht als Person erkannt.
- Redaction nur Pre-Call, aber Tool-Outputs (Sales-CRM-Daten) gehen unredigiert in den Kontext zurueck.
- "Wir nutzen ja nur OpenAI Enterprise" -- DPA loest nicht das App-interne PII-Audit-Problem.

### Tooling 2026
- **Microsoft Presidio** -- Open-Source NER + Regex + Checksum (CC, IBAN, US_SSN etc.).
- **Microsoft Purview** -- Enterprise-Datenklassifizierung, DLP-Policies.
- **AWS Comprehend PII**, **Google DLP API** -- Cloud-managed Alternativen.
- **LiteLLM + Presidio Guardrails** -- fertiger Drop-in.
- **Fabric AI Functions** (Microsoft Fabric) -- PII-Detection nativ in Lakehouse.
- **OpenTelemetry PII-Redaction-Processor** -- Telemetrie-Sanitization in-transit.

### Checkliste
- [ ] Pre-Call-Redaction vor jedem externen LLM-Provider-Call.
- [ ] Tool-Outputs werden ebenfalls durch Redaction-Layer geschickt.
- [ ] Agent-Memory ist per-User indiziert, Loeschung in <30 Tagen umsetzbar.
- [ ] Application-Logs enthalten keine Raw-Prompts oder PII.
- [ ] DPA mit allen LLM-Providern, Sub-Processors gelistet.

### Quellen
- [Microsoft Presidio (GitHub)](https://github.com/microsoft/presidio)
- [LiteLLM: Presidio PII Masking](https://docs.litellm.ai/docs/tutorials/presidio_pii_masking)
- [Ploomber: Preventing PII leakage with Presidio](https://ploomber.io/blog/presidio/)
- [Enterprise-Scale PII De-Identification](https://ijaibdcms.org/index.php/ijaibdcms/article/view/339)
- [PII Redaction Pipeline (redteams.ai)](https://redteams.ai/topics/walkthroughs/defense/pii-redaction-pipeline)
- [Microsoft Fabric AI Functions: PII Detection](https://community.fabric.microsoft.com/t5/Data-Engineering-Community-Blog/PII-Detection-and-Redaction-with-Fabric-AI-Functions/ba-p/4731952)

---

## 5. SLOs & Rate Limits (Latenz-Budgets, Token-Quotas, Failover)

### Problem
LLM-Latenz ist hochvariant (P50 1s, P99 30s nicht selten). Provider-Outages (OpenAI, Anthropic) treten regelmaessig auf. Ohne Token-Quotas pro Tenant kann ein einzelner Kunde das Budget der gesamten Plattform fressen ("denial-of-wallet").

### Loesungs-Pattern

**a) SLO-Definition pro Endpoint** (Beispielwerte fuer Customer-Support-Agent):

| Metrik | P50 | P95 | P99 |
|---|---|---|---|
| Time-to-First-Token | 400ms | 1.2s | 3s |
| Total-Response-Time | 2s | 8s | 20s |
| Tool-Call-Roundtrip | 200ms | 800ms | 2s |
| Error-Rate | <0.5% | -- | -- |

**b) Token-Bucket pro Tenant** mit getrennten Buckets fuer Input/Output:

```yaml
# LiteLLM virtual_keys
- key: tenant-acme
  rpm_limit: 100
  tpm_limit: 200000
  budget_duration: "1d"
  max_budget: 50.00
  allowed_models: ["gpt-4o-mini", "claude-haiku-4-5"]
  fallback_models: ["gpt-3.5-turbo"]
```

**c) Provider-Failover via AI-Gateway** (Vercel AI Gateway / OpenRouter):

```ts
// Vercel AI SDK 5 -- Gateway-Routing
import { generateText } from "ai";
import { gateway } from "@ai-sdk/gateway";

const { text } = await generateText({
  model: gateway("anthropic/claude-sonnet-4.5"),
  fallback: ["openai/gpt-4o", "google/gemini-2.5-pro"],
  experimental_telemetry: { isEnabled: true },
  prompt: "...",
});
```

**d) Backpressure** -- bei TPM-Limit nicht hart rejecten, sondern Queue mit Timeout:

```python
async def generate(req):
    async with tenant_semaphore[req.tenant_id]:  # max 10 concurrent
        try:
            return await asyncio.wait_for(llm_call(req), timeout=30)
        except asyncio.TimeoutError:
            return cached_or_degraded_response(req)
```

### Anti-Pattern
- Globale Rate-Limits ohne Tenant-Splitting -- ein Kunde kann alle anderen blockieren.
- Identische Limits fuer Input und Output Tokens -- Output ist ~4x teurer.
- Hard-Reject bei 100% statt Graceful-Degradation auf billigeres Modell.
- Kein Provider-Failover -- bei OpenAI-Outage steht das Produkt.
- Latency-SLO ohne Streaming-First-Token-Metric (User-Perception != Total-Latency).

### Tooling 2026
- **Vercel AI Gateway** -- Unified API, $5/Monat Free, Zero-Markup, Auto-Failover.
- **OpenRouter** -- 25-40ms Overhead, 200+ Modelle, automatischer Provider-Fallback.
- **LiteLLM Proxy** -- Virtual Keys, RPM/TPM/Budget pro Tenant, Open-Source.
- **Bifrost** (Go) -- schnellster Open-Source AI-Gateway 2026.
- **Cloudflare AI Gateway**, **Kong AI Gateway** -- Edge-nahe Alternativen.
- **TrueFoundry, Maxim** -- Enterprise-AI-Gateways mit Observability.
- **Helicone** -- Proxy + Cost-/Latency-Analytics.

### Checkliste
- [ ] SLO-Tabelle (P50/P95/P99 fuer TTFT, Total-Time, Error-Rate) pro Endpoint dokumentiert.
- [ ] Token-Bucket pro Tenant, separate Limits fuer Input/Output.
- [ ] Mindestens ein Provider-Failover konfiguriert und getestet.
- [ ] Streaming aktiv, TTFT als primaeres Latency-SLO.
- [ ] Backpressure via Semaphore oder Queue, nicht harter Reject.

### Quellen
- [TrueFoundry: Observability in AI Gateways](https://www.truefoundry.com/blog/observability-in-ai-gateway)
- [OpenRouter: Latency and Performance](https://openrouter.ai/docs/guides/best-practices/latency-and-performance)
- [OpenRouter vs Vercel AI Gateway 2026](https://www.respan.ai/market-map/compare/openrouter-vs-vercel-ai-gateway)
- [Inworld: Best LLM Gateways 2026](https://inworld.ai/resources/best-llm-gateways)
- [Maxim: Top 5 LLM Gateways for 2026](https://www.getmaxim.ai/articles/top-5-llm-gateways-for-2026-a-comprehensive-comparison/)

---

## 6. Audit Logs (Was loggen, Compliance, OTel GenAI)

### Problem
SOC2/HIPAA/GDPR verlangen nachvollziehbare Audit-Trails. Aber: Prompts und Responses koennen PII, Geschaeftsgeheimnisse, Auth-Tokens enthalten. Naive "log everything"-Ansaetze schaffen einen Compliance-Albtraum statt ihn zu loesen.

### Loesungs-Pattern

**a) OpenTelemetry GenAI Semantic Conventions** als Standard-Schema (seit 2024 entwickelt, in 2026 stabil bei Datadog v1.37+, Sentry, Langfuse, Helicone).

```python
# OTel Span fuer Chat-Completion
span.set_attribute("gen_ai.operation.name", "chat")
span.set_attribute("gen_ai.provider.name", "anthropic")
span.set_attribute("gen_ai.request.model", "claude-sonnet-4-5")
span.set_attribute("gen_ai.response.model", "claude-sonnet-4-5-20260315")
span.set_attribute("gen_ai.usage.input_tokens", 1532)
span.set_attribute("gen_ai.usage.output_tokens", 218)
span.set_attribute("gen_ai.request.temperature", 0.2)
# Tenant + User + Agent fuer Compliance
span.set_attribute("tenant.id", tenant_id)
span.set_attribute("enduser.id", hashed_user_id)
span.set_attribute("gen_ai.agent.id", "support-agent-v3")
```

**b) Was loggen, was nicht:**

| Feld | Default | Begruendung |
|---|---|---|
| `gen_ai.operation.name` | log | Unkritisch |
| `gen_ai.usage.*` | log | Cost/Quota |
| `gen_ai.request.model` | log | Versionierung |
| `gen_ai.prompt` | **opt-in, redacted** | PII-Risiko |
| `gen_ai.completion` | **opt-in, redacted** | PII-Risiko |
| `tool_call.arguments` | **redact**, hash bei Bedarf | Auth-Token-Risiko |
| `tenant.id` / `enduser.id` | log (gehasht) | Compliance |

OTel-Empfehlung: Prompts/Completions per default NICHT als Span-Attribute, sondern in separates Storage uploaden mit Hash-Referenz im Span.

**c) Immutable Storage fuer Compliance:**

```yaml
# AWS S3 Object Lock (WORM) fuer SOC2/HIPAA
audit_logs:
  bucket: org-audit-2026
  storage_class: GLACIER_IR
  object_lock:
    mode: COMPLIANCE        # nicht GOVERNANCE
    retention_days: 2555    # 7 Jahre
  encryption: aws:kms
  kms_key: arn:aws:kms:eu-west-1:...
```

Alternativ: Datadog Cloud SIEM, Splunk, Loki mit Retention-Policies.

**d) Compliance-spezifisch:**
- **SOC2** -- Audit-Trail fuer Access, Changes, Anomalies; Retention >= 1 Jahr.
- **HIPAA** -- 6 Jahre, BAA mit Provider, kein PHI im Prompt-Log ohne Redaction.
- **GDPR** -- Personenbezogene Logs unter Art. 6 Abs. 1 lit. f rechtfertigen, Zweckbindung, max. notwendige Retention.

### Anti-Pattern
- Volle Prompts/Completions in Application-Logs (Stdout -> Datadog) ohne Redaction.
- Logs in mutable Storage (S3 ohne Object Lock, normale DB) -- Compliance-Auditor lehnt ab.
- Kein Tenant- oder User-Index -- DSAR nicht erfuellbar.
- Custom-Schema statt OTel GenAI Semantic Conventions -- Vendor-Lock-in, kein Tooling-Support.
- Tool-Call-Arguments im Klartext loggen, obwohl da Auth-Tokens drin landen koennen.

### Tooling 2026
- **OpenTelemetry GenAI Semconv** (experimental, aber Industry-Standard).
- **Langfuse** -- Open-Source LLM-Observability mit OTel-Support, self-hostable.
- **Helicone** -- Proxy + Audit-Log + Cost-Analytics.
- **Datadog LLM Observability** -- nativer OTel-GenAI-Support seit v1.37.
- **Sentry AI Monitoring** -- Auto-Instrumentation fuer Vercel AI SDK, LangChain, Anthropic SDK.
- **AWS S3 Object Lock**, **Azure Immutable Blob Storage**, **GCS Bucket Lock** -- WORM-Storage.
- **Traceloop OpenLLMetry** -- OTel-Auto-Instrumentation Lib.

### Checkliste
- [ ] OpenTelemetry GenAI Semantic Conventions als Schema, nicht Custom.
- [ ] Prompts/Completions nicht im Span, sondern referenziert in WORM-Storage.
- [ ] Tenant-ID und gehashte User-ID auf jedem Span.
- [ ] Retention-Policy je Compliance-Regime (SOC2 1y, HIPAA 6y, GDPR Zweckbindung).
- [ ] Audit-Log-Storage ist immutable (S3 Object Lock COMPLIANCE-Mode).

### Quellen
- [OpenTelemetry: GenAI Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/)
- [OpenTelemetry: GenAI Spans](https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-spans/)
- [OpenTelemetry: Agentic Systems Spans](https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-agent-spans/)
- [Datadog: Native OTel GenAI Support](https://www.datadoghq.com/blog/llm-otel-semantic-convention/)
- [OpenObserve: OTel for LLMs SRE Guide 2026](https://openobserve.ai/blog/opentelemetry-for-llms/)
- [Traceloop GenAI Conventions](https://www.traceloop.com/docs/openllmetry/contributing/semantic-conventions)

---

## 7. Rollback & Incident Response (Canary, Blue/Green, Runbooks)

### Problem
Prompt-Aenderungen sind Deployments. Ein neuer System-Prompt kann silent die Hallucination-Rate verdoppeln, ohne dass Tests es zeigen. Ohne Canary + Auto-Rollback gehen Aenderungen blind in Produktion. Tool-Failures, Cost-Spikes, Hallucination-Spikes sind eigenstaendige Incident-Klassen mit eigenen Runbooks.

### Loesungs-Pattern

**a) Prompt-Versioning + Canary-Rollout** (z.B. via Vercel Rolling Releases):

```ts
// Edge-Middleware -- 5% Traffic auf neue Prompt-Version
import { unstable_rolloutFlag } from "@vercel/flags";

export const promptVersion = unstable_rolloutFlag("prompt_v3", {
  rolloutPercent: 5,
  rolloutStages: [5, 25, 50, 100],
  rollbackOn: {
    metrics: ["hallucination_rate", "p95_latency", "error_rate", "cost_per_request"],
    thresholds: { hallucination_rate: 1.5, p95_latency: 1.3 }, // 1.5x Baseline
  },
});
```

**b) Blue/Green fuer Agent-Versions** -- zwei Endpoint-Versionen, sofortige Umschaltung via Feature-Flag oder Weighted-Routing.

**c) Runbook-Templates** (operational knowledge as runnable tools, Vercel-Style):

```yaml
# runbooks/hallucination-spike.yaml
trigger:
  metric: hallucination_rate
  threshold: 2x_7day_baseline
  window: 15m
steps:
  - name: snapshot_prompt_diff
    action: git diff HEAD~1 -- prompts/
  - name: check_model_version
    action: query_otel "gen_ai.response.model" group by hour
  - name: rollback_canary
    action: vercel rolling-release rollback --to-stable
  - name: page_oncall
    action: pagerduty.trigger("hallucination-spike", severity=high)
```

```yaml
# runbooks/tool-failure.yaml
trigger:
  metric: tool_error_rate
  service: github_mcp
  threshold: 5%
steps:
  - check: github_status_page
  - circuit_break: github_mcp for 5m
  - fallback: prompt_user("GitHub temporaer nicht verfuegbar")
```

```yaml
# runbooks/cost-anomaly.yaml
trigger:
  metric: tokens_per_minute
  threshold: 3x_24h_baseline
  per: tenant
steps:
  - identify: top_3_users_by_cost_last_1h
  - downgrade_model: route to haiku/mini-tier
  - alert: slack #ai-cost-watch
```

**d) Anomalie-Detection automatisiert** -- Vercel Agent Investigations queryt Logs/Metrics um Alert-Zeitpunkt, korreliert, schlaegt Root-Cause vor. Sentry instrumentiert agent_invocation/tool_call/llm_request automatisch ueber `gen_ai.invoke_agent`-Spans.

### Anti-Pattern
- Prompts werden direkt in Production editiert, kein Versioning, kein Diff im PR-Review.
- 100%-Rollout auf einmal, kein Canary -- "wir testen ja in Staging" (Staging hat nicht den realen Traffic-Mix).
- Generische "Agent kaputt"-Alerts ohne Failure-Mode-Differenzierung (Timeout vs. Hallucination vs. Tool-Error vs. Context-Overflow).
- Manuelle Rollbacks per ssh -- mittlere Time-To-Recovery > 30min.
- Tracing nur bis zum Agent-Eingang, nicht durch Sub-Agents (Trace-ID muss durch alle Hops).

### Tooling 2026
- **Vercel Rolling Releases** -- Auto-Rollback bei Metrik-Degradation.
- **Vercel Agent Investigations** -- AI-gestuetzte Root-Cause-Analyse ($0.30 + Token-Cost pro Investigation).
- **Sentry AI Monitoring** -- Auto-Instrumentation fuer Vercel AI SDK, LangChain, OpenAI Agents.
- **LaunchDarkly + AI-Configs** -- Prompt-Versioning + Feature-Flagging.
- **PromptLayer, PromptOps** -- Git-style Versioning fuer Prompts.
- **Langfuse Prompt Management** -- Versioning + A/B-Testing.
- **Datadog Watchdog**, **PagerDuty AIOps** -- Anomalie-Detection.

### Checkliste
- [ ] Prompts liegen versioniert in Git, jeder Change im PR-Review.
- [ ] Canary-Rollout mit Auto-Rollback bei Metric-Degradation aktiv.
- [ ] Runbooks fuer mind. 4 Incident-Klassen: Hallucination, Tool-Failure, Cost-Spike, Latency-Spike.
- [ ] Trace-ID propagiert durch alle Sub-Agents und Tool-Calls.
- [ ] Failure-Modes differenziert (Timeout/Tool-Error/Hallucination/Context-Overflow).

### Quellen
- [Vercel: Rolling Releases](https://vercel.com/docs/rolling-releases)
- [Vercel: Implementing Canary Deployments](https://vercel.com/kb/guide/implementing_canary_deployments_on_vercel)
- [Vercel Agent](https://vercel.com/docs/agent)
- [Vercel: Agent Responsibly](https://vercel.com/blog/agent-responsibly)
- [Sentry: Scaling observability for multi-agent AI](https://blog.sentry.io/scaling-observability-for-multi-agent-ai-systems/)
- [Canary Deployments for Securing LLMs](https://medium.com/@oracle_43885/canary-deployments-for-securing-large-language-models-48393fa68efc)

---

## 8. Kostensteuerung (Budget-Caps, Quotas, Cache, Tiering)

### Problem
LLM-Cost ist fuer SaaS-Produkte oft groesster variabler Kostenblock. Ein einzelner Power-User oder ein Loop-Bug kann an einem Tag $10k verbrennen ("denial-of-wallet"). Ohne per-Tenant-Caps, Cache-Monitoring und Modell-Tiering ist die Unit-Economy nicht steuerbar.

### Loesungs-Pattern

**a) Hierarchische Budget-Caps** mit progressivem Throttling:

| Threshold | Action |
|---|---|
| 70% | Alert an Tenant + Sales |
| 80% | Soft-Throttle: Routing auf billigeres Modell |
| 95% | Hard-Throttle: Queue oder Reject non-essential |
| 100% | Block, nur essentielle Endpoints durchlassen |

```yaml
# LiteLLM Virtual Key
- key_alias: tenant-acme-prod
  max_budget: 500.00
  budget_duration: "30d"
  soft_budget: 350.00          # 70%
  rpm_limit: 200
  tpm_limit: 500000
  model_max_budget:
    "gpt-4o": 300.00
    "claude-opus": 100.00
  metadata:
    tenant_tier: "enterprise"
```

**b) Modell-Tiering-Routing**:

```ts
async function route(query: Query) {
  const complexity = await classifier(query); // small model, ~1ms

  if (complexity === "trivial") {
    return haiku(query);                    // $0.25/MTok
  } else if (complexity === "moderate") {
    return sonnet(query);                   // $3-15/MTok
  } else {
    return opus(query);                     // $15-75/MTok
  }
}
// 60-90% Cost-Reduction laut Industry-Benchmarks
```

**c) Cache-Hitrate-Monitoring**:

```ts
// Anthropic Prompt Caching mit cache_control
const response = await anthropic.messages.create({
  model: "claude-sonnet-4-5",
  system: [
    {
      type: "text",
      text: LONG_SYSTEM_PROMPT,
      cache_control: { type: "ephemeral" }, // 5min TTL, ~10x billiger
    },
  ],
  messages: [...],
});

// Metrik: cache_creation_input_tokens / cache_read_input_tokens
// Ziel: > 70% Hit-Rate auf System-Prompt-Block
```

Studien zeigen: 31% der Enterprise-LLM-Queries sind semantisch identisch zu vorherigen. Semantic-Caching (GPTCache, Redis Semantic Cache) lohnt sich.

**d) Streaming-Cancellation** -- wenn User abbricht, Stream sofort cancellen, kein "weiterproduzieren in den Muell":

```ts
const controller = new AbortController();
req.on("close", () => controller.abort());

const stream = await openai.chat.completions.create({
  model: "gpt-4o",
  messages,
  stream: true,
}, { signal: controller.signal });
```

**e) Anomaly-Detection** -- daily Token-Usage > 150% des 7-Tage-Schnitts loest Auto-Investigation aus.

### Anti-Pattern
- Globaler Budget-Cap ohne Tenant-Splitting -- ein Kunde kann das gesamte Budget aufbrauchen.
- Uniform Rate-Limits (RPM only) -- High-Cost-Operations slippen durch (denial-of-wallet).
- Premium-Modell als Default fuer alle Queries, kein Tiering.
- Kein Streaming-Cancel -- abandoned Streams produzieren weiter Tokens.
- Prompt-Cache nicht aktiviert oder unter 30% Hit-Rate ohne Investigation.
- Kein Cost-Attribution pro Feature/Endpoint -- Optimierung im Blindflug.

### Tooling 2026
- **LiteLLM Proxy** -- Virtual-Keys, Budgets, Tiering, Open-Source.
- **Vercel AI Gateway** -- Budget-Controls, Usage-Monitoring eingebaut.
- **Helicone** -- Cost-Tracking + Cache-Analytics.
- **Langfuse** -- Cost-Per-User/Trace-Attribution.
- **GPTCache, Redis Semantic Cache** -- Semantic-Caching-Libs.
- **Anthropic Prompt Caching** (5min ephemeral, 1h beta) -- bis zu 90% Cost-Reduktion auf wiederverwendete Prefixe.
- **OpenAI Prompt Caching** -- automatisch bei Prompts > 1024 Tokens.
- **Clarifai, Maxim** -- Enterprise Cost-Control-Plattformen.

### Checkliste
- [ ] Per-Tenant-Daily-Cap konfiguriert, progressives Throttling bei 80/95/100%.
- [ ] Modell-Tiering aktiv, Trivial-Queries auf Haiku/Mini-Tier geroutet.
- [ ] Anthropic/OpenAI Prompt-Caching aktiv, Hit-Rate-Dashboard existiert (Ziel >70%).
- [ ] Streaming-Cancellation propagiert AbortSignal bis zum Provider.
- [ ] Cost-Attribution pro Tenant/Feature/User in Dashboard sichtbar.

### Quellen
- [Clarifai: AI Cost Controls -- Budgets, Throttling, Model Tiering](https://www.clarifai.com/blog/ai-cost-controls)
- [Maxim: Reduce LLM Cost and Latency Guide 2026](https://www.getmaxim.ai/articles/reduce-llm-cost-and-latency-a-comprehensive-guide-for-2026/)
- [Maxim: 5 Tools for LLM Cost Controls](https://www.getmaxim.ai/articles/5-tools-for-llm-cost-controls/)
- [Redis: LLM Token Optimization](https://redis.io/blog/llm-token-optimization-speed-up-apps/)
- [Silicon Data: LLM Cost Per Token 2026 Guide](https://www.silicondata.com/blog/llm-cost-per-token)
- [LLM Agent Cost Attribution Guide 2026](https://www.digitalapplied.com/blog/llm-agent-cost-attribution-guide-production-2026)
- [LLM API Rate Limiting & Cost Control](https://igotasite4that.com/blog/llm-api-rate-limiting-cost-control/)

---

## Querschnitts-Sources

- [OWASP LLM Top 10 v2025 / 2026](https://genai.owasp.org/llm-top-10/) -- LLM08 Vector/Embedding Weaknesses, Multi-Tenant-Risks.
- [OpenTelemetry GenAI Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/) -- Industry-Standard.
- [Anthropic Skills + Managed Agents Vault Auth](https://platform.claude.com/docs/en/managed-agents/vaults).
- [MCP Spec + OWASP MCP Top 10:2025](https://modelcontextprotocol.io/) -- Token Mismanagement, Tool Poisoning.
