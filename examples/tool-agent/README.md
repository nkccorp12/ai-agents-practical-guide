# Tool-Agent Reference

Customer-support agent demonstrating the production patterns described in
Appendix F, Use-Case 1:

- RBAC + tenant isolation (Postgres Row-Level-Security)
- Approval gate for refunds above a configurable threshold
- Audit log for every tool call (success, error, denial)
- Hallucination guard via tool-name allowlist
- Tool timeouts with `asyncio.timeout`
- OpenTelemetry GenAI tracing via Langfuse

## Layout

```
tool-agent/
  python/
    main.py          FastAPI + Anthropic SDK agent loop
    tools.py         Tool implementations + dispatch
    schema.sql       Postgres tables + RLS policies
    requirements.txt
  typescript/
    route.ts         Next.js App Router route, Vercel AI SDK 6 needsApproval
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
uvicorn main:app --reload
```

The agent listens on `POST /chat` with body `{ conversation_id, message, approval_token? }`
and a `Bearer` token containing `tenant_id`, `user_id`, `role` (Demo: JSON,
Production: signed JWT).

## Run (TypeScript)

```bash
cd typescript
pnpm install
pnpm dev
```

POST to `/api/support` with messages in Vercel AI SDK chat format.

## Tests

```bash
cd tests
promptfoo eval -c promptfooconfig.yaml
```

## Tracing

Langfuse via OpenTelemetry GenAI conventions. The Python implementation
wires `AnthropicInstrumentor` + `@observe`, the TypeScript implementation
uses Vercel AI SDK's `experimental_telemetry` with `LangfuseExporter`.
