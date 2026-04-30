# Reference Implementations

Two production-grade archetypes accompanying Appendix F of the practical
guide. Each example is runnable end-to-end with minimal setup and ships in
both Python (FastAPI + Anthropic SDK) and TypeScript (Next.js + Vercel AI
SDK 6) flavours.

## Layout

```
examples/
  tool-agent/   Customer-support agent with RBAC + approval gate
  rag-agent/    Hybrid-search RAG agent with Cohere rerank + Anthropic citations
```

Each sub-directory contains:

- `python/` runnable FastAPI app, schema, requirements
- `typescript/` Next.js App Router route + package manifest
- `tests/` Promptfoo configuration and golden test cases
- `deploy/` Modal deployment snippet (Python) — Vercel deploys directly via `vercel deploy`

## Quickstart

### Python (tool-agent)

```bash
cd tool-agent/python
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
psql "$DATABASE_URL" -f schema.sql
ANTHROPIC_API_KEY=sk-ant-... DATABASE_URL=postgres://... uvicorn main:app --reload
```

### TypeScript (rag-agent)

```bash
cd rag-agent/typescript
pnpm install
ANTHROPIC_API_KEY=... COHERE_API_KEY=... DATABASE_URL=... pnpm dev
```

### Tests

```bash
cd tool-agent/tests
promptfoo eval -c promptfooconfig.yaml
```

## Configuration variables

All examples read configuration from environment variables. The most common ones:

| Variable | Used in | Notes |
|----------|---------|-------|
| `ANTHROPIC_API_KEY` | both | Anthropic Messages API |
| `COHERE_API_KEY` | rag-agent | embeddings + rerank |
| `DATABASE_URL` | both | Postgres (pgvector for rag) |
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` | optional | tracing backend |

## License

Code in this directory is released under CC BY 4.0, matching the rest of the
guide. Patterns are adapted from publicly documented Anthropic, Vercel,
Tigerdata, and Cohere cookbooks (see Appendix F sources).
