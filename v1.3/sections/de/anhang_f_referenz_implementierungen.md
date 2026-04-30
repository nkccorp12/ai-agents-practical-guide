## Anhang F: Referenz-Implementierungen

Dieser Anhang verweist auf zwei lauffähige Referenz-Implementierungen im
Verzeichnis `examples/` des Repositoriums. Sie decken die zwei Archetypen ab,
denen man in der Praxis am häufigsten begegnet: einen Tool-Agent mit
Schreibrechten und Approval-Gate sowie einen RAG-Agent mit Hybrid-Suche und
nativen Quellen-Zitaten. Beide Beispiele liegen parallel in Python (FastAPI +
Anthropic SDK) und TypeScript (Next.js + Vercel AI SDK 6) vor und lassen sich
mit minimalem Setup starten. Der Code ist an offiziellen Cookbooks von
Anthropic, Vercel, Tigerdata und Cohere verifiziert. Lizenz: CC BY 4.0,
identisch mit dem restlichen Buch.

### F.1 Use-Case 1: Tool-Agent (Customer-Support mit Approval-Gate)

#### Anforderungen

- **RBAC**: drei Rollen (`tier1_support`, `tier2_support`, `admin`); Refunds
  über 100 USD sind nur mit `tier2_support` direkt ausführbar.
- **Tenant-Isolation**: jede Datenbank-Operation filtert auf `tenant_id` aus
  dem JWT-Claim; Postgres-Row-Level-Security als zweite Verteidigungslinie.
- **Approval-Gate**: bei Refunds über 100 USD pausiert die Agent-Schleife,
  ein `approval_token` wird zurückgegeben und nach Freigabe wird der Lauf mit
  einem `tool_result`-Block fortgesetzt.
- **Audit-Log**: jede Tool-Aktion (Erfolg, Fehler, Pending) landet mit
  `actor`, `tool_name`, `args_hash`, `result_status`, `latency_ms` und
  `trace_id` in der Tabelle `audit_log`.
- **Failure-Handling**: harte Tool-Timeouts (5 s via `asyncio.timeout`),
  Token-Bucket-Rate-Limit pro Tenant, Hallucination-Guard über eine
  Tool-Namens-Allowlist plus Pydantic-Validierung der Tool-Argumente.

#### Architektur

Der Datenfluss ist linear: HTTP-Client mit Bearer-Token erreicht eine
FastAPI-Route, die JWT verifiziert, RBAC prüft und ein Rate-Limit anwendet.
Der Agent-Orchestrator ruft die Anthropic Messages API mit System-Prompt und
Tool-Definitionen auf. Drei Tools sind verfügbar: `get_order` (read-only),
`refund_order` (write, mit Approval-Gate) und `escalate_to_human`. Sämtliche
Lese- und Schreibvorgänge laufen gegen Postgres mit RLS pro `tenant_id`.
Refunds über dem Schwellwert führen zu einem Eintrag in `pending_approvals`
und beenden den Request mit einem `requires_approval`-Objekt; Tier-2 ruft
einen separaten Endpoint zum Konsumieren des Tokens auf, woraufhin der
ursprüngliche Lauf mit einem `tool_result` weiterläuft. Spans gehen über
OpenTelemetry an Langfuse.

#### Python-Auszug

Der Kern der Agent-Schleife: pro Iteration einmal Modell aufrufen, bei
`tool_use` die Approval-Bedingung prüfen, sonst Tool dispatchen und das
Ergebnis ans Modell zurückgeben. Vollständige Implementierung in
`examples/tool-agent/python/main.py`.

```python
for _ in range(MAX_HOPS):
    resp = await client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=[{
            "type": "text",
            "text": SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }],
        tools=TOOLS,
        messages=messages,
    )
    messages.append({"role": "assistant", "content": resp.content})

    if resp.stop_reason == "end_turn":
        text = "".join(b.text for b in resp.content if b.type == "text")
        return ChatResponse(output=text, trace_id=trace_id, ...)

    if resp.stop_reason == "tool_use":
        tool_results = []
        for tb in [b for b in resp.content if b.type == "tool_use"]:
            if (
                tb.name == "refund_order"
                and tb.input.get("amount", 0) > REFUND_APPROVAL_THRESHOLD_USD
                and principal.role != "tier2_support"
            ):
                token = await _stash_approval(req.conversation_id, principal,
                                              tb.id, tb.name, tb.input)
                return ChatResponse(requires_approval={
                    "tool": tb.name, "args": tb.input, "approval_token": token,
                }, trace_id=trace_id, ...)

            try:
                result = await dispatch_tool(_pool, tb.name, tb.input,
                                             principal, approved=False)
                tool_results.append({"type": "tool_result",
                                     "tool_use_id": tb.id,
                                     "content": json.dumps(result)})
            except ToolError as exc:
                tool_results.append({"type": "tool_result",
                                     "tool_use_id": tb.id,
                                     "is_error": True,
                                     "content": str(exc)})
        messages.append({"role": "user", "content": tool_results})
```

#### TypeScript-Auszug

Vercel AI SDK 6 liefert das Approval-Gate deklarativ über `needsApproval` auf
der Tool-Definition. Vollständige Implementierung in
`examples/tool-agent/typescript/route.ts`.

```typescript
refund_order: tool({
  description: "Refund (part of) an order. Refunds > $100 require Tier-2 approval.",
  inputSchema: z.object({
    order_id: z.string().uuid(),
    amount: z.number().positive(),
    reason: z.string().min(5),
  }),
  needsApproval: async ({ amount }) =>
    amount > REFUND_THRESHOLD && principal.role !== "tier2_support",
  execute: async ({ order_id, amount, reason }) => {
    // Transaktional: Order verifizieren, Refund eintragen, Audit schreiben.
    return await db.transaction(async (tx) => { /* ... */ });
  },
}),
```

#### Test-Strategie

Die Goldens in `examples/tool-agent/tests/goldens.yaml` decken vier Klassen
ab: kleiner Refund läuft direkt durch, grosser Refund triggert Approval-Gate,
Tenant-Isolation verhindert Cross-Tenant-Zugriff, und der Agent halluziniert
keine Tools (Test mit `Delete the order completely`). Aufruf in CI:

```yaml
# tool-agent/tests/promptfooconfig.yaml (gekürzt)
providers:
  - id: http://localhost:8000/chat
    config:
      headers:
        Authorization: 'Bearer {"tenant_id":"t1","user_id":"u1","role":"tier1_support"}'
      transformResponse: 'json.output ?? json.requires_approval'
```

```bash
promptfoo eval -c promptfooconfig.yaml --fail-on-error
```

#### Deployment

Modal eignet sich gut für die FastAPI-Variante, weil ASGI-Apps direkt als
Funktion mountbar sind. Komplettes Snippet in
`examples/tool-agent/deploy/modal_app.py`:

```python
@app.function(
    secrets=[modal.Secret.from_name("anthropic-prod"),
             modal.Secret.from_name("postgres-prod")],
    timeout=120, min_containers=1, max_containers=20,
)
@modal.asgi_app()
def fastapi_app():
    from main import app as fastapi
    return fastapi
```

Die TypeScript-Variante deployt direkt mit `vercel deploy --prod`. Edge
Runtime ist nicht empfohlen, weil `asyncpg` und der Drizzle-Postgres-Pool
Node benötigen.

#### Tracing

Beide Implementierungen folgen den OpenTelemetry GenAI Semantic Conventions.
Python instrumentiert über `AnthropicInstrumentor().instrument()` plus den
Langfuse `@observe`-Dekorator. TypeScript nutzt `experimental_telemetry` aus
dem Vercel AI SDK in Verbindung mit `LangfuseExporter`. Die wichtigsten
Spans im Trace-Tree sind `support_agent.chat` (root, mit `tenant_id`,
`role`, `session_id`), `anthropic.messages.create` (mit `cache_read_tokens`,
`input_tokens`, `output_tokens`), `tool.<name>` (mit `latency_ms`) und
`approval_gate` (mit `decision`).

### F.2 Use-Case 2: RAG-Agent (Hybrid-Suche mit Citations)

#### Anforderungen

- **Hybrid-Suche**: BM25 über Postgres `tsvector` plus dichte
  Vektor-Ähnlichkeit über `pgvector` mit HNSW-Index.
- **Filter-First**: Metadaten-Filter (`product`, `locale`, `dept`) laufen als
  WHERE-Klausel vor BM25 und Vector-Search, damit der HNSW-Index weniger
  Kandidaten verwerfen muss.
- **Reranking**: Cohere `rerank-v3.5` als Cross-Encoder verdichtet die 50
  Treffer aus der RRF-Fusion auf `top_k = 8`.
- **Native Citations**: Anthropic Citations API mit
  `citations.enabled = true`; `cited_text` zählt nicht zu den Output-Tokens.
- **Caching**: System-Prompt und alle Dokument-Blöcke tragen
  `cache_control: { type: "ephemeral", ttl: "1h" }`. Cache-Reads kosten 0.1x
  Input-Preis, Ziel-Hit-Rate über 70 Prozent.

#### Architektur

Eingehende Anfragen werden zuerst gefiltert, dann parallel gegen BM25 und
Vector-Index ausgeführt (je 50 Treffer). Reciprocal-Rank-Fusion mit `k = 60`
fusioniert beide Listen. Cohere Rerank wählt die finalen acht Chunks aus.
Diese gehen als `documents[]`-Blöcke in die Anthropic Messages API; jeder
Block trägt `citations.enabled` und `cache_control`. Die Antwort enthält
neben dem freien Text auch strukturierte `char_location`-Citations, die das
Frontend per Klick auf den Quell-Chunk zurückführen kann.

#### Python-Auszug

Die Pipeline aus `examples/rag-agent/python/main.py`:

```python
async def hybrid_retrieve(req: RagRequest, *, n_each: int = 50) -> list[dict]:
    qvec = (await co.embed(
        texts=[req.query], model=EMBED_MODEL,
        input_type="search_query", embedding_types=["float"],
    )).embeddings.float_[0]

    where, vals = _filter_sql(req.filters)
    async with _pool.acquire() as conn:
        bm25 = await conn.fetch(f"""
            SELECT id, doc_id, doc_title, content,
                   ts_rank_cd(tsv, plainto_tsquery('english', $N)) AS s
            FROM kb_chunks {where}
            {'AND' if where else 'WHERE'} tsv @@ plainto_tsquery('english', $N)
            ORDER BY s DESC LIMIT $M""", *vals, req.query, n_each)
        vec = await conn.fetch(f"""
            SELECT id, doc_id, doc_title, content,
                   1 - (embedding <=> $N::vector) AS s
            FROM kb_chunks {where}
            ORDER BY embedding <=> $N::vector LIMIT $M""", *vals, qvec, n_each)

    # RRF-Fusion mit k=60
    scores, rows = {}, {}
    for rank, r in enumerate(bm25):
        scores[r["id"]] = scores.get(r["id"], 0) + 1 / (60 + rank); rows[r["id"]] = dict(r)
    for rank, r in enumerate(vec):
        scores[r["id"]] = scores.get(r["id"], 0) + 1 / (60 + rank); rows[r["id"]] = dict(r)
    return sorted(rows.values(), key=lambda x: scores[x["id"]], reverse=True)[:n_each]
```

Die Generierung mit Citations und Cache-Control:

```python
documents = [{
    "type": "document",
    "source": {"type": "text", "media_type": "text/plain", "data": c["content"]},
    "title": c["doc_title"],
    "citations": {"enabled": True},
    "cache_control": {"type": "ephemeral", "ttl": "1h"},
} for c in top]

resp = await ant.messages.create(
    model="claude-opus-4-7",
    max_tokens=1024,
    system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral", "ttl": "1h"}}],
    messages=[{"role": "user", "content": [*documents, {"type": "text", "text": req.query}]}],
)
```

#### TypeScript-Auszug

In `examples/rag-agent/typescript/route.ts` reichen `providerOptions` die
Anthropic-spezifischen `citations` und `cacheControl` durch das Vercel AI SDK
hindurch:

```typescript
const result = await generateText({
  model: anthropic("claude-opus-4-7"),
  system: [{
    type: "text",
    text: "You answer ONLY from provided documents. Cite all claims.",
    providerOptions: { anthropic: { cacheControl: { type: "ephemeral", ttl: "1h" } } },
  }],
  messages: [{
    role: "user",
    content: [
      ...top.map((c) => ({
        type: "file" as const,
        data: c.content,
        mediaType: "text/plain",
        filename: c.doc_title,
        providerOptions: {
          anthropic: {
            citations: { enabled: true },
            cacheControl: { type: "ephemeral", ttl: "1h" },
          },
        },
      })),
      { type: "text" as const, text: body.query },
    ],
  }],
});
```

#### Test-Strategie

Die Promptfoo-Goldens in `examples/rag-agent/tests/goldens.yaml` setzen drei
Metriken als Hard-Gates: `factuality` gegen einen Referenz-Claim,
`answer-relevance` (Threshold 0.8), und `context-faithfulness` (Threshold
0.9). Ein Out-of-Scope-Test verlangt explizite Abstinenz, ein Locale-Test
prüft, dass deutsche Anfragen auch deutsche Dokumente zurückbringen, und ein
Citations-Test verifiziert, dass mindestens ein `char_location`-Block
zurückkommt.

#### Tracing

`AnthropicInstrumentor` plus der Langfuse `@observe`-Dekorator erzeugen
einen Trace-Baum mit Spans für `cohere.embed`, `db.bm25`, `db.vector_search`,
`rrf`, `cohere.rerank` und `anthropic.messages.create` (mit
`cache_read_tokens`, `cache_write_tokens` und `citations_count`). Diese
Felder sind die Grundlage für das Cache-Hit-Rate-Monitoring.

### F.3 Vom Beispiel zum Production-Stack

Diese beiden Referenzen sind absichtlich kompakt gehalten und zeigen jeweils
genau einen Archetypen end-to-end. Für einen realen Production-Stack kommen
die Themen aus Kapitel 11 (Operationalisierung) und Kapitel 12 (Compliance
und Sicherheit) dazu: Eval-Pipelines im CI, Observability-Dashboards mit
SLOs, Cost-Budgets pro Tenant, Secrets-Rotation und ein DSGVO-konformes
Logging-Konzept.

Die Variablen, die typischerweise an die eigene Umgebung angepasst werden:

- **LLM-Provider**: Modell-ID und Provider-SDK (im Beispiel
  `claude-opus-4-7`); bei Multi-Model-Setups das Vercel AI Gateway davorschalten.
- **Datenbank**: Connection-String, Pool-Grenzen, RLS-Policies (oder das
  Equivalent in einem hosted Provider wie Neon).
- **Embeddings und Reranker**: Cohere ist nicht zwingend; Voyage `rerank-2`
  oder ein lokales Reranker-Modell sind drop-in-ersetzbar.
- **Tracing-Backend**: Langfuse ist gut integriert, jeder OTel-kompatible
  Collector funktioniert (Honeycomb, Grafana Tempo, Datadog).
- **Approval-Workflow**: das Demo verwendet einen separaten HTTP-Endpoint;
  in der Praxis hängt hier oft Slack, eine Ticketing-Integration oder eine
  Admin-UI dran.

### F.4 Quellen

#### Tool-Agent

- Anthropic Customer-Support Cookbook
  (`platform.claude.com/docs/.../customer-support-chat`)
- Anthropic `tool_use` Customer-Service-Agent
  (`github.com/anthropics/anthropic-cookbook`)
- Vercel AI SDK Human-in-the-Loop Cookbook
  (`ai-sdk.dev/cookbook/next/human-in-the-loop`)
- Vercel AI SDK 6 `needsApproval` Announcement
  (`vercel.com/blog/ai-sdk-6`)
- Anthropic Trustworthy Agents (Approval-Gates)
  (`anthropic.com/research/trustworthy-agents`)

#### RAG-Agent

- Anthropic Citations API
  (`platform.claude.com/docs/en/build-with-claude/citations`)
- Anthropic Contextual Retrieval Cookbook
  (`platform.claude.com/cookbook/capabilities-contextual-embeddings-guide`)
- Tigerdata: PostgreSQL Hybrid Search mit pgvector und Cohere
  (`tigerdata.com/blog/postgresql-hybrid-search-using-pgvector-and-cohere`)
- Cohere Rerank v3.5 / v4
  (`docs.cohere.com/docs/rerank-overview`)
- Anthropic Prompt Caching mit 1h-TTL
  (`platform.claude.com/docs/en/build-with-claude/prompt-caching`)
- Vercel AI SDK Anthropic Provider mit Citations
  (`ai-sdk.dev/providers/ai-sdk-providers/anthropic`)

#### Werkzeuge

- Langfuse Anthropic-Integration
  (`langfuse.com/integrations/model-providers/anthropic`)
- Langfuse Vercel-AI-SDK-Integration
  (`langfuse.com/integrations/frameworks/vercel-ai-sdk`)
- OpenTelemetry GenAI Semantic Conventions
  (`opentelemetry.io/docs/specs/semconv/gen-ai/`)
- Promptfoo RAG Eval Guide
  (`promptfoo.dev/docs/guides/evaluate-rag`)
- Modal Beispiele (`asgi_app`, Secrets)
  (`github.com/modal-labs/modal-examples`)
