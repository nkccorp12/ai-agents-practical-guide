# RAG-Agent Reference

Hybrid-search RAG agent demonstrating the production patterns described in
Appendix F, Use-Case 2:

- Filter-first retrieval (metadata WHERE clause runs before vector search)
- Hybrid search: BM25 (`tsvector`) + dense vector (`pgvector` HNSW)
- Reciprocal-rank-fusion with `k=60`
- Cross-encoder reranking via Cohere `rerank-v3.5`
- Anthropic native citations (`citations.enabled: true`)
- Prompt caching with 1h TTL on the system message and document blocks
- OpenTelemetry GenAI tracing via Langfuse

## Layout

```
rag-agent/
  python/
    main.py          FastAPI app: hybrid retrieve -> rerank -> generate
    ingest.py        Embed + insert chunks; build tsvector + HNSW indexes
    schema.sql       pgvector table + GIN/HNSW indexes
    requirements.txt
  typescript/
    route.ts         Next.js App Router route, Vercel AI SDK 6 + citations
    package.json
  tests/
    promptfooconfig.yaml
    goldens.yaml
  deploy/
    modal_app.py     Modal ASGI deployment snippet
```

## Run (Python)

```bash
cd python
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
psql "$DATABASE_URL" -f schema.sql
python ingest.py path/to/docs/*.md
uvicorn main:app --reload
```

POST `{"query": "...", "filters": {"product": "billing"}, "top_k": 8}`
to `/rag`.

## Run (TypeScript)

```bash
cd typescript
pnpm install
pnpm dev
```

POST to `/api/rag`.

## Tests

```bash
cd tests
promptfoo eval -c promptfooconfig.yaml
```

The golden suite measures `factuality`, `answer-relevance`, and
`context-faithfulness` thresholds.

## Tracing

The Python implementation wires `AnthropicInstrumentor` plus `@observe`,
producing spans for `cohere.embed`, `db.bm25`, `db.vector_search`, `rrf`,
`cohere.rerank`, and `anthropic.messages.create`. Watch
`cache_read_tokens` to verify the knowledge-base cache hit rate (target
above 70%).
