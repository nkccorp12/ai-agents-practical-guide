## Appendix F: Reference Implementations

This appendix points to two runnable reference implementations in the
`examples/` directory of the repository. They cover the two archetypes most
teams encounter in practice: a tool-agent with write permissions and an
approval gate, and a RAG agent with hybrid retrieval and native source
citations. Each example ships in parallel as Python (FastAPI + Anthropic SDK)
and TypeScript (Next.js + Vercel AI SDK 6) and runs with minimal setup. The
patterns are verified against official cookbooks from Anthropic, Vercel,
Tigerdata, and Cohere. License: CC BY 4.0, identical to the rest of the
guide.

### F.1 Use-Case 1: Tool-Agent (Customer Support with Approval Gate)

#### Requirements

- **RBAC**: three roles (`tier1_support`, `tier2_support`, `admin`); refunds
  above 100 USD can only be executed directly by `tier2_support`.
- **Tenant isolation**: every database operation filters on the JWT
  `tenant_id` claim, with Postgres row-level security as a second line of
  defence.
- **Approval gate**: refunds above 100 USD pause the agent loop, return an
  `approval_token`, and resume the loop with a `tool_result` block once the
  reviewer signs off.
- **Audit log**: every tool action (success, error, pending) is persisted in
  the `audit_log` table with `actor`, `tool_name`, `args_hash`,
  `result_status`, `latency_ms`, and `trace_id`.
- **Failure handling**: hard tool timeouts (5 s via `asyncio.timeout`),
  per-tenant token-bucket rate limiting, hallucination guard via a
  tool-name allowlist plus Pydantic argument validation.

#### Architecture

The data flow is linear: an HTTP client with a bearer token hits a FastAPI
route that verifies the JWT, enforces RBAC, and applies a rate limit. The
agent orchestrator calls the Anthropic Messages API with the system prompt
and tool definitions. Three tools are available: `get_order` (read-only),
`refund_order` (write, gated), and `escalate_to_human`. Reads and writes go
through Postgres with RLS keyed on `tenant_id`. Refunds above the threshold
write to `pending_approvals` and end the request with a `requires_approval`
payload; a Tier-2 reviewer calls a separate endpoint to consume the token,
after which the original loop continues with a `tool_result`. Spans flow
through OpenTelemetry into Langfuse.

#### Python excerpt

The core loop: one model call per iteration, evaluate the approval condition
on `tool_use`, otherwise dispatch the tool and feed the result back to the
model. Full implementation in `examples/tool-agent/python/main.py`.

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

#### TypeScript excerpt

Vercel AI SDK 6 expresses the approval gate declaratively via `needsApproval`
on the tool definition. Full implementation in
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
    // Transactional: verify order, insert refund, write audit row.
    return await db.transaction(async (tx) => { /* ... */ });
  },
}),
```

#### Test strategy

The goldens in `examples/tool-agent/tests/goldens.yaml` cover four classes:
small refund passes through, large refund triggers the approval gate, tenant
isolation prevents cross-tenant access, and the agent does not hallucinate
tools (test prompt: `Delete the order completely`). CI invocation:

```yaml
# tool-agent/tests/promptfooconfig.yaml (excerpt)
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

Modal is a good fit for the FastAPI variant because ASGI apps mount as a
single function. Full snippet in
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

The TypeScript variant deploys directly with `vercel deploy --prod`. Edge
runtime is not recommended because `asyncpg` and the Drizzle Postgres pool
require Node.

#### Tracing

Both implementations follow the OpenTelemetry GenAI semantic conventions.
Python instruments via `AnthropicInstrumentor().instrument()` plus the
Langfuse `@observe` decorator. TypeScript uses `experimental_telemetry` from
the Vercel AI SDK with `LangfuseExporter`. The key spans in the trace tree
are `support_agent.chat` (root, with `tenant_id`, `role`, `session_id`),
`anthropic.messages.create` (with `cache_read_tokens`, `input_tokens`,
`output_tokens`), `tool.<name>` (with `latency_ms`), and `approval_gate`
(with `decision`).

### F.2 Use-Case 2: RAG-Agent (Hybrid Search with Citations)

#### Requirements

- **Hybrid search**: BM25 over Postgres `tsvector` plus dense vector
  similarity over `pgvector` with an HNSW index.
- **Filter-first**: metadata filters (`product`, `locale`, `dept`) run as a
  WHERE clause before BM25 and vector search, so the HNSW index has fewer
  candidates to reject.
- **Reranking**: Cohere `rerank-v3.5` cross-encoder narrows the 50 fused
  hits to `top_k = 8`.
- **Native citations**: Anthropic Citations API with
  `citations.enabled = true`; `cited_text` does not count toward output
  tokens.
- **Caching**: the system prompt and every document block carry
  `cache_control: { type: "ephemeral", ttl: "1h" }`. Cache reads cost 0.1x
  the input price; target hit rate above 70 percent.

#### Architecture

Incoming requests are filtered first, then run in parallel against the BM25
and vector indexes (50 hits each). Reciprocal-rank fusion with `k = 60`
merges the two lists. Cohere Rerank picks the final eight chunks. These are
passed as `documents[]` blocks to the Anthropic Messages API; each block
carries `citations.enabled` and `cache_control`. The response contains free
text plus structured `char_location` citations, which the frontend can map
back to source chunks on click.

#### Python excerpt

The pipeline from `examples/rag-agent/python/main.py`:

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

    # RRF fusion with k=60
    scores, rows = {}, {}
    for rank, r in enumerate(bm25):
        scores[r["id"]] = scores.get(r["id"], 0) + 1 / (60 + rank); rows[r["id"]] = dict(r)
    for rank, r in enumerate(vec):
        scores[r["id"]] = scores.get(r["id"], 0) + 1 / (60 + rank); rows[r["id"]] = dict(r)
    return sorted(rows.values(), key=lambda x: scores[x["id"]], reverse=True)[:n_each]
```

The generation step with citations and cache control:

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

#### TypeScript excerpt

In `examples/rag-agent/typescript/route.ts`, `providerOptions` pass the
Anthropic-specific `citations` and `cacheControl` through the Vercel AI SDK:

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

#### Test strategy

The Promptfoo goldens in `examples/rag-agent/tests/goldens.yaml` set three
metrics as hard gates: `factuality` against a reference claim,
`answer-relevance` (threshold 0.8), and `context-faithfulness` (threshold
0.9). An out-of-scope test demands explicit abstention, a locale test
verifies that German queries return German-locale documents only, and a
citations test confirms that at least one `char_location` block is
returned.

#### Tracing

`AnthropicInstrumentor` plus the Langfuse `@observe` decorator produce a
trace tree with spans for `cohere.embed`, `db.bm25`, `db.vector_search`,
`rrf`, `cohere.rerank`, and `anthropic.messages.create` (with
`cache_read_tokens`, `cache_write_tokens`, and `citations_count`). These
fields are the basis for cache-hit-rate monitoring.

### F.3 From example to production stack

These two references are intentionally compact and each shows one archetype
end-to-end. A real production stack adds the topics from Chapter 11
(operations) and Chapter 12 (compliance and security): eval pipelines in
CI, observability dashboards with SLOs, per-tenant cost budgets, secret
rotation, and a GDPR-aware logging strategy.

The variables that typically need to be adapted to a given environment:

- **LLM provider**: model id and provider SDK (`claude-opus-4-7` in the
  examples). For multi-model setups put Vercel AI Gateway in front.
- **Database**: connection string, pool limits, RLS policies (or the
  equivalent on a hosted provider such as Neon).
- **Embeddings and reranker**: Cohere is not mandatory; Voyage `rerank-2` or
  a self-hosted reranker drop in cleanly.
- **Tracing backend**: Langfuse integrates well, but any OTel-compatible
  collector works (Honeycomb, Grafana Tempo, Datadog).
- **Approval workflow**: the demo uses a separate HTTP endpoint; in
  production this commonly attaches to Slack, a ticketing integration, or
  an admin UI.

### F.4 Sources

#### Tool-Agent

- Anthropic Customer-Support cookbook
  (`platform.claude.com/docs/.../customer-support-chat`)
- Anthropic `tool_use` customer-service-agent
  (`github.com/anthropics/anthropic-cookbook`)
- Vercel AI SDK Human-in-the-Loop cookbook
  (`ai-sdk.dev/cookbook/next/human-in-the-loop`)
- Vercel AI SDK 6 `needsApproval` announcement
  (`vercel.com/blog/ai-sdk-6`)
- Anthropic Trustworthy Agents (approval gates)
  (`anthropic.com/research/trustworthy-agents`)

#### RAG-Agent

- Anthropic Citations API
  (`platform.claude.com/docs/en/build-with-claude/citations`)
- Anthropic Contextual Retrieval cookbook
  (`platform.claude.com/cookbook/capabilities-contextual-embeddings-guide`)
- Tigerdata: PostgreSQL hybrid search with pgvector and Cohere
  (`tigerdata.com/blog/postgresql-hybrid-search-using-pgvector-and-cohere`)
- Cohere Rerank v3.5 / v4
  (`docs.cohere.com/docs/rerank-overview`)
- Anthropic prompt caching with 1h TTL
  (`platform.claude.com/docs/en/build-with-claude/prompt-caching`)
- Vercel AI SDK Anthropic provider with citations
  (`ai-sdk.dev/providers/ai-sdk-providers/anthropic`)

#### Tooling

- Langfuse Anthropic integration
  (`langfuse.com/integrations/model-providers/anthropic`)
- Langfuse Vercel-AI-SDK integration
  (`langfuse.com/integrations/frameworks/vercel-ai-sdk`)
- OpenTelemetry GenAI semantic conventions
  (`opentelemetry.io/docs/specs/semconv/gen-ai/`)
- Promptfoo RAG eval guide
  (`promptfoo.dev/docs/guides/evaluate-rag`)
- Modal examples (`asgi_app`, secrets)
  (`github.com/modal-labs/modal-examples`)
