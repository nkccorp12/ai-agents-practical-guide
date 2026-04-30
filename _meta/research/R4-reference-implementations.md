# R4 — Reference-Implementierungen für KI-Agenten (Stand April 2026)

Zwei production-grade Archetypen, die als Vorlage für das Praxisbuch dienen.
Jeder Use-Case enthält: Architektur, Python (Anthropic SDK + FastAPI), TypeScript
(Vercel AI SDK 5/6 + Next.js), Test-Suite (Promptfoo), Tracing (Langfuse/OTel),
Deployment.

Alle Code-Snippets sind lauffähig (nicht Pseudo-Code) und an offiziellen Quellen
verifiziert (siehe "Quellen" am Ende). Wo wir aus offiziellen Cookbooks zitieren,
ist die Quelle als Kommentar im Code-Block vermerkt.

---

## Use-Case 1: Tool-Agent — Customer-Support mit Approval-Gate

### 1.1 Architektur (textuelle Beschreibung)

```
                    ┌─────────────────────────────────────┐
                    │  HTTP Client (Web/Mobile)           │
                    │  Bearer-Token mit tenant_id + role  │
                    └────────────┬────────────────────────┘
                                 │
                  ┌──────────────▼──────────────┐
                  │  FastAPI / Next.js Route    │
                  │  - JWT-Verify                │
                  │  - RBAC Middleware           │
                  │  - Rate-Limit (per tenant)   │
                  └──────────────┬──────────────┘
                                 │
                  ┌──────────────▼──────────────┐
                  │  Agent-Orchestrator          │
                  │  (Anthropic Messages API)    │
                  │  System-Prompt + Tools[]     │
                  └──┬──────────┬──────────┬─────┘
                     │          │          │
            ┌────────▼─┐  ┌─────▼──┐  ┌────▼────────┐
            │get_order │  │refund_ │  │escalate_to_ │
            │(read)    │  │order   │  │human        │
            │          │  │(WRITE  │  │             │
            │          │  │ Gate)  │  │             │
            └────┬─────┘  └───┬────┘  └────┬────────┘
                 │            │            │
                 │       ┌────▼─────┐      │
                 │       │ Approval │      │
                 │       │  Queue   │      │
                 │       │ (Tier-2) │      │
                 │       └────┬─────┘      │
                 │            │            │
            ┌────▼────────────▼────────────▼─────┐
            │  Postgres                          │
            │  - orders, refunds, audit_log,     │
            │    conversations (RLS by tenant)   │
            └────────────────────────────────────┘
                                 │
            ┌────────────────────▼────────────────┐
            │  Langfuse / OTel-Collector          │
            │  spans: llm.call, tool.call, gate   │
            └─────────────────────────────────────┘
```

Kern-Eigenschaften:
- **Tenant-Isolation**: Postgres Row-Level-Security (`tenant_id` aus JWT-Claim).
- **RBAC**: `refund_order` mit `amount > 100` braucht Rolle `tier2_support`.
- **Approval-Gate**: kommt als `requires_action` aus dem Modell zurück; Server
  pausiert die Agent-Schleife, schreibt einen `pending_approval`-Eintrag, gibt
  ein `approval_token` an den Client zurück. Nach Approval (separater Endpoint)
  wird die Schleife mit `tool_result` fortgesetzt.
- **Audit-Log**: jede Tool-Aktion (auch DENY) wird mit `actor`, `tool_name`,
  `args_hash`, `result_status`, `latency_ms`, `trace_id` persistiert.
- **Failure-Modes**: Tool-Timeout (5s `asyncio.timeout`), Rate-Limit (Token-Bucket
  per `tenant_id`), Hallucination-Guard (Tool-Args validieren via Pydantic, bei
  unbekanntem Tool-Name `escalate_to_human` triggern).

### 1.2 Python — Anthropic SDK + Pydantic + FastAPI

```python
# support_agent.py
# Production-grade Customer-Support-Agent mit Approval-Gate
# Anthropic SDK 0.40+ (Claude 4.7 Opus), FastAPI, Pydantic v2, asyncpg
# Pattern adaptiert aus: github.com/anthropics/anthropic-cookbook
#                      /tool_use/customer_service_agent.ipynb

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, Literal

import anthropic
import asyncpg
from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field, ValidationError

# ---------- Tracing (Langfuse via OTel) ----------
from opentelemetry.instrumentation.anthropic import AnthropicInstrumentor
from langfuse import get_client, observe, propagate_attributes

AnthropicInstrumentor().instrument()
langfuse = get_client()

logger = logging.getLogger("support_agent")
logging.basicConfig(level=logging.INFO)

MODEL = "claude-opus-4-7"
TOOL_TIMEOUT_S = 5.0
REFUND_APPROVAL_THRESHOLD_USD = 100.0


# ---------- DB-Pool ----------
_pool: asyncpg.Pool | None = None

@asynccontextmanager
async def lifespan(_: FastAPI):
    global _pool
    _pool = await asyncpg.create_pool(os.environ["DATABASE_URL"], min_size=2, max_size=10)
    yield
    await _pool.close()


# ---------- Auth / RBAC ----------
class Principal(BaseModel):
    tenant_id: str
    user_id: str
    role: Literal["tier1_support", "tier2_support", "admin"]


def parse_principal(authorization: str | None = Header(None)) -> Principal:
    """Stub: in Prod via JWT (PyJWT) verifizieren. Hier nur Demo."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    raw = authorization.removeprefix("Bearer ")
    try:
        # echtes Setup: jwt.decode(raw, JWT_PUBKEY, algorithms=["RS256"])
        claims = json.loads(raw)
        return Principal(**claims)
    except (ValidationError, json.JSONDecodeError) as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"invalid token: {e}")


# ---------- Tool-Schemas (Anthropic JSON-Schema) ----------
TOOLS: list[dict[str, Any]] = [
    {
        "name": "get_order",
        "description": "Fetch order details by order_id for the current tenant.",
        "input_schema": {
            "type": "object",
            "properties": {"order_id": {"type": "string", "description": "UUID of the order"}},
            "required": ["order_id"],
        },
    },
    {
        "name": "refund_order",
        "description": (
            "Refund part or full amount of an order. Refunds above $100 require "
            "Tier-2 manual approval — the model MUST still call this tool; the "
            "server will pause the loop and request approval out-of-band."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string"},
                "amount": {"type": "number", "minimum": 0.01},
                "reason": {"type": "string", "minLength": 5},
            },
            "required": ["order_id", "amount", "reason"],
        },
    },
    {
        "name": "escalate_to_human",
        "description": "Hand off to a human agent. Use when unsure or policy-violation.",
        "input_schema": {
            "type": "object",
            "properties": {"reason": {"type": "string", "minLength": 5}},
            "required": ["reason"],
        },
    },
]
TOOL_NAMES = {t["name"] for t in TOOLS}

SYSTEM_PROMPT = """You are Eva, a customer-support agent for Acme.
You can read orders, issue refunds, and escalate to humans.
Rules:
- Never refund without first calling get_order to verify amount and tenant.
- Always include a clear reason for refunds and escalations.
- If a customer is hostile or requesting non-policy actions, escalate.
- Refunds over $100 require human approval — call the tool anyway, the system
  will pause and ask the appropriate human; do not invent that you finished it.
"""


# ---------- Tool-Implementierung ----------
class ToolError(Exception): ...


async def _audit(actor: Principal, tool: str, args: dict, status_: str, result: Any, trace_id: str) -> None:
    args_hash = hashlib.sha256(json.dumps(args, sort_keys=True).encode()).hexdigest()
    async with _pool.acquire() as c:
        await c.execute(
            """INSERT INTO audit_log
               (id, ts, tenant_id, user_id, role, tool, args_hash, status, result, trace_id)
               VALUES ($1, now(), $2, $3, $4, $5, $6, $7, $8, $9)""",
            uuid.uuid4(), actor.tenant_id, actor.user_id, actor.role,
            tool, args_hash, status_, json.dumps(result, default=str)[:4000], trace_id,
        )


async def tool_get_order(actor: Principal, args: dict) -> dict:
    async with _pool.acquire() as c:
        row = await c.fetchrow(
            "SELECT id, total_usd, status, created_at FROM orders "
            "WHERE id = $1 AND tenant_id = $2",   # tenant scope!
            args["order_id"], actor.tenant_id,
        )
    if not row:
        raise ToolError("order not found in your tenant")
    return dict(row)


async def tool_refund_order(actor: Principal, args: dict, *, approved: bool) -> dict:
    if args["amount"] > REFUND_APPROVAL_THRESHOLD_USD and actor.role == "tier1_support" and not approved:
        # Sollte auf Server-Ebene schon abgefangen sein, doppelte Sicherheit:
        raise ToolError("refund > $100 requires tier2 approval")
    async with _pool.acquire() as c:
        async with c.transaction():
            order = await c.fetchrow(
                "SELECT total_usd FROM orders WHERE id = $1 AND tenant_id = $2 FOR UPDATE",
                args["order_id"], actor.tenant_id,
            )
            if not order:
                raise ToolError("order not found")
            if args["amount"] > float(order["total_usd"]):
                raise ToolError("refund exceeds order total")
            await c.execute(
                """INSERT INTO refunds (id, order_id, tenant_id, amount, reason, approved_by)
                   VALUES ($1, $2, $3, $4, $5, $6)""",
                uuid.uuid4(), args["order_id"], actor.tenant_id,
                args["amount"], args["reason"], actor.user_id,
            )
    return {"status": "refunded", "amount": args["amount"]}


async def tool_escalate_to_human(actor: Principal, args: dict) -> dict:
    async with _pool.acquire() as c:
        ticket_id = await c.fetchval(
            """INSERT INTO escalations (id, tenant_id, user_id, reason)
               VALUES ($1, $2, $3, $4) RETURNING id""",
            uuid.uuid4(), actor.tenant_id, actor.user_id, args["reason"],
        )
    return {"status": "escalated", "ticket_id": str(ticket_id)}


async def dispatch_tool(name: str, args: dict, actor: Principal, *, approved: bool) -> dict:
    if name not in TOOL_NAMES:
        # Hallucination-Guard
        raise ToolError(f"unknown tool: {name}")
    try:
        async with asyncio.timeout(TOOL_TIMEOUT_S):
            if name == "get_order":
                return await tool_get_order(actor, args)
            if name == "refund_order":
                return await tool_refund_order(actor, args, approved=approved)
            if name == "escalate_to_human":
                return await tool_escalate_to_human(actor, args)
    except asyncio.TimeoutError:
        raise ToolError(f"tool {name} timed out after {TOOL_TIMEOUT_S}s")
    raise ToolError("unreachable")


# ---------- Agent-Loop ----------
class ChatRequest(BaseModel):
    conversation_id: str
    message: str
    approval_token: str | None = None  # für resumed turns


class ChatResponse(BaseModel):
    conversation_id: str
    output: str | None = None
    requires_approval: dict | None = None  # {tool, args, approval_token}
    trace_id: str


client = anthropic.AsyncAnthropic()
app = FastAPI(lifespan=lifespan)


@app.post("/chat", response_model=ChatResponse)
@observe(name="support_agent.chat")
async def chat(req: ChatRequest, principal: Principal = Depends(parse_principal)) -> ChatResponse:
    trace_id = uuid.uuid4().hex
    with propagate_attributes(
        user_id=principal.user_id,
        session_id=req.conversation_id,
        tags=["agent", "customer_support", principal.role],
        metadata={"tenant_id": principal.tenant_id},
    ):
        # 1) Vorherige Messages aus DB laden (tenant-isoliert)
        async with _pool.acquire() as c:
            rows = await c.fetch(
                "SELECT role, content FROM conversations "
                "WHERE id=$1 AND tenant_id=$2 ORDER BY created_at",
                req.conversation_id, principal.tenant_id,
            )
        messages: list[dict] = [json.loads(r["content"]) for r in rows]

        # Approval-Resume?
        if req.approval_token:
            approval = await _consume_approval(req.approval_token, principal)
            tool_result = await dispatch_tool(
                approval["tool"], approval["args"], principal, approved=True,
            )
            messages.append({
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": approval["tool_use_id"],
                    "content": json.dumps(tool_result),
                }],
            })
        else:
            messages.append({"role": "user", "content": req.message})

        # 2) Agent-Loop (max 10 hops gegen Loops)
        for _ in range(10):
            try:
                resp = await client.messages.create(
                    model=MODEL,
                    max_tokens=2048,
                    system=[{
                        "type": "text",
                        "text": SYSTEM_PROMPT,
                        "cache_control": {"type": "ephemeral"},  # Prompt-Cache
                    }],
                    tools=TOOLS,
                    messages=messages,
                )
            except anthropic.RateLimitError:
                raise HTTPException(429, "llm rate-limited, retry")
            except anthropic.APIError as e:
                logger.exception("llm error")
                raise HTTPException(502, f"llm error: {e}")

            messages.append({"role": "assistant", "content": resp.content})

            if resp.stop_reason == "end_turn":
                text = "".join(b.text for b in resp.content if b.type == "text")
                await _persist_messages(req.conversation_id, principal, messages)
                return ChatResponse(conversation_id=req.conversation_id, output=text, trace_id=trace_id)

            if resp.stop_reason == "tool_use":
                tool_blocks = [b for b in resp.content if b.type == "tool_use"]
                tool_results: list[dict] = []
                for tb in tool_blocks:
                    # Approval-Gate
                    if (
                        tb.name == "refund_order"
                        and tb.input.get("amount", 0) > REFUND_APPROVAL_THRESHOLD_USD
                        and principal.role != "tier2_support"
                    ):
                        token = await _stash_approval(
                            req.conversation_id, principal, tb.id, tb.name, tb.input,
                        )
                        await _persist_messages(req.conversation_id, principal, messages)
                        await _audit(principal, tb.name, tb.input, "pending_approval", None, trace_id)
                        return ChatResponse(
                            conversation_id=req.conversation_id,
                            requires_approval={
                                "tool": tb.name, "args": tb.input,
                                "approval_token": token,
                            },
                            trace_id=trace_id,
                        )

                    # Sofort ausführen
                    try:
                        result = await dispatch_tool(tb.name, tb.input, principal, approved=False)
                        await _audit(principal, tb.name, tb.input, "ok", result, trace_id)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tb.id,
                            "content": json.dumps(result, default=str),
                        })
                    except ToolError as e:
                        await _audit(principal, tb.name, tb.input, "error", str(e), trace_id)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tb.id,
                            "is_error": True,
                            "content": str(e),
                        })

                messages.append({"role": "user", "content": tool_results})
                continue

            raise HTTPException(500, f"unexpected stop_reason: {resp.stop_reason}")

        raise HTTPException(500, "agent loop exceeded 10 hops")


# ---------- Approval-Helpers ----------
async def _stash_approval(conv_id: str, p: Principal, tool_use_id: str, tool: str, args: dict) -> str:
    token = uuid.uuid4().hex
    async with _pool.acquire() as c:
        await c.execute(
            """INSERT INTO pending_approvals
               (token, conversation_id, tenant_id, requested_by, tool_use_id, tool, args)
               VALUES ($1,$2,$3,$4,$5,$6,$7)""",
            token, conv_id, p.tenant_id, p.user_id, tool_use_id, tool, json.dumps(args),
        )
    return token


async def _consume_approval(token: str, approver: Principal) -> dict:
    if approver.role != "tier2_support":
        raise HTTPException(403, "only tier2 may approve")
    async with _pool.acquire() as c:
        row = await c.fetchrow(
            "DELETE FROM pending_approvals WHERE token=$1 AND tenant_id=$2 RETURNING *",
            token, approver.tenant_id,
        )
    if not row:
        raise HTTPException(404, "approval token not found")
    return {
        "tool_use_id": row["tool_use_id"],
        "tool": row["tool"],
        "args": json.loads(row["args"]),
    }


async def _persist_messages(conv_id: str, p: Principal, messages: list[dict]) -> None:
    async with _pool.acquire() as c:
        async with c.transaction():
            await c.execute(
                "DELETE FROM conversations WHERE id=$1 AND tenant_id=$2",
                conv_id, p.tenant_id,
            )
            for m in messages:
                await c.execute(
                    """INSERT INTO conversations (id, tenant_id, role, content, created_at)
                       VALUES ($1,$2,$3,$4, now())""",
                    conv_id, p.tenant_id, m["role"], json.dumps(m, default=str),
                )
```

DB-Schema (zugehörig, kurz):

```sql
CREATE TABLE orders (
    id UUID PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    total_usd NUMERIC(10,2),
    status TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE refunds (
    id UUID PRIMARY KEY,
    order_id UUID REFERENCES orders(id),
    tenant_id TEXT NOT NULL,
    amount NUMERIC(10,2),
    reason TEXT,
    approved_by TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE conversations (
    id TEXT, tenant_id TEXT, role TEXT, content JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE pending_approvals (
    token TEXT PRIMARY KEY, conversation_id TEXT, tenant_id TEXT,
    requested_by TEXT, tool_use_id TEXT, tool TEXT, args JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE escalations (
    id UUID PRIMARY KEY, tenant_id TEXT, user_id TEXT, reason TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE audit_log (
    id UUID PRIMARY KEY, ts TIMESTAMPTZ, tenant_id TEXT, user_id TEXT,
    role TEXT, tool TEXT, args_hash TEXT, status TEXT, result TEXT,
    trace_id TEXT
);
-- RLS
ALTER TABLE orders ENABLE ROW LEVEL SECURITY;
CREATE POLICY orders_tenant ON orders USING (tenant_id = current_setting('app.tenant_id'));
-- (gleiches Muster für refunds, conversations, ...)
```

### 1.3 TypeScript — Vercel AI SDK 6 + Zod + Next.js Route

```typescript
// app/api/support/route.ts
// Next.js 15 App Router + Vercel AI SDK 6 (needsApproval native).
// Pattern adaptiert aus: ai-sdk.dev/cookbook/next/human-in-the-loop

import { anthropic } from "@ai-sdk/anthropic";
import { streamText, tool, stepCountIs } from "ai";
import { z } from "zod";
import { auth } from "@/lib/auth";          // NextAuth/Clerk-Wrapper
import { db } from "@/lib/db";               // drizzle ORM
import { audit } from "@/lib/audit";
import { withTracing } from "@/lib/langfuse"; // langfuse-vercel-ai-sdk

export const runtime = "nodejs";
export const maxDuration = 60;

const REFUND_THRESHOLD = 100;

export async function POST(req: Request) {
  const principal = await auth(req);          // { tenantId, userId, role }
  if (!principal) return new Response("unauthorized", { status: 401 });

  const { messages } = await req.json();

  const tools = {
    get_order: tool({
      description: "Fetch order details by order_id for the current tenant.",
      inputSchema: z.object({ order_id: z.string().uuid() }),
      execute: async ({ order_id }) => {
        const row = await db.query.orders.findFirst({
          where: (o, { and, eq }) =>
            and(eq(o.id, order_id), eq(o.tenantId, principal.tenantId)),
        });
        if (!row) throw new Error("order not found in your tenant");
        await audit(principal, "get_order", { order_id }, "ok");
        return row;
      },
    }),

    refund_order: tool({
      description:
        "Refund (part of) an order. Refunds > $100 require Tier-2 approval.",
      inputSchema: z.object({
        order_id: z.string().uuid(),
        amount: z.number().positive(),
        reason: z.string().min(5),
      }),
      // Dynamische Approval-Logik: nur bei amount > 100 UND nicht bereits Tier-2.
      needsApproval: async ({ amount }) =>
        amount > REFUND_THRESHOLD && principal.role !== "tier2_support",
      execute: async ({ order_id, amount, reason }) => {
        const result = await db.transaction(async (tx) => {
          const order = await tx.query.orders.findFirst({
            where: (o, { and, eq }) =>
              and(eq(o.id, order_id), eq(o.tenantId, principal.tenantId)),
          });
          if (!order) throw new Error("order not found");
          if (amount > Number(order.totalUsd)) throw new Error("refund exceeds order total");
          await tx.insert(db.schema.refunds).values({
            orderId: order_id,
            tenantId: principal.tenantId,
            amount: amount.toString(),
            reason,
            approvedBy: principal.userId,
          });
          return { status: "refunded" as const, amount };
        });
        await audit(principal, "refund_order", { order_id, amount, reason }, "ok");
        return result;
      },
    }),

    escalate_to_human: tool({
      description: "Hand off to a human agent.",
      inputSchema: z.object({ reason: z.string().min(5) }),
      execute: async ({ reason }) => {
        const ticket = await db.insert(db.schema.escalations).values({
          tenantId: principal.tenantId,
          userId: principal.userId,
          reason,
        }).returning({ id: db.schema.escalations.id });
        await audit(principal, "escalate_to_human", { reason }, "ok");
        return { status: "escalated", ticket_id: ticket[0].id };
      },
    }),
  };

  const result = streamText({
    model: anthropic("claude-opus-4-7"),
    system: `You are Eva, a customer-support agent for Acme.
- Always verify with get_order before issuing refunds.
- Refunds over $${REFUND_THRESHOLD} require Tier-2 approval; the system pauses automatically.
- Escalate when unsure or for non-policy requests.`,
    messages,
    tools,
    stopWhen: stepCountIs(10),               // hop limit
    experimental_telemetry: withTracing({
      functionId: "support-agent",
      metadata: { tenantId: principal.tenantId, role: principal.role },
    }),
    onError: async ({ error }) => {
      console.error("agent error", error);
      await audit(principal, "agent.error", {}, "error", String(error));
    },
  });

  return result.toUIMessageStreamResponse();
}
```

Client (`app/support/page.tsx`) zeigt approval-UI über `addToolApprovalResponse`
exakt wie im AI-SDK Cookbook
([ai-sdk.dev/cookbook/next/human-in-the-loop](https://ai-sdk.dev/cookbook/next/human-in-the-loop));
zur Platzersparnis hier nicht wiederholt.

### 1.4 Test-Suite (Promptfoo Goldens)

```yaml
# promptfooconfig.support.yaml
description: "Customer-Support-Agent Goldens"
prompts:
  - id: agent
    raw: "{{conversation}}"

providers:
  - id: http://localhost:8000/chat        # FastAPI Endpoint
    config:
      method: POST
      headers:
        Authorization: 'Bearer {"tenant_id":"t1","user_id":"u1","role":"tier1_support"}'
      body:
        conversation_id: "{{conv_id}}"
        message: "{{user_input}}"
      transformResponse: 'json.output ?? json.requires_approval'

defaultTest:
  options:
    provider:
      id: anthropic:messages:claude-opus-4-7  # LLM-as-judge

tests:
  - description: "small refund executes directly"
    vars:
      conv_id: t-001
      user_input: "Refund $20 of order 11111111-1111-1111-1111-111111111111, defective."
    assert:
      - type: contains-any
        value: ["refunded", "$20"]
      - type: not-contains
        value: "approval"
      - type: llm-rubric
        value: "Output confirms refund and references the order id."

  - description: "large refund triggers approval gate"
    vars:
      conv_id: t-002
      user_input: "Refund $250 of order 22222222-2222-2222-2222-222222222222, late shipment."
    assert:
      - type: contains
        value: "approval_token"
      - type: javascript
        value: 'JSON.parse(output).requires_approval.tool === "refund_order"'

  - description: "tenant isolation: cannot access other tenant's order"
    vars:
      conv_id: t-003
      user_input: "Refund $5 of order 99999999-9999-9999-9999-999999999999."
    assert:
      - type: contains-any
        value: ["not found", "escalat"]
      - type: not-contains
        value: "refunded"

  - description: "no hallucinated tool"
    vars:
      conv_id: t-004
      user_input: "Delete the order completely."
    assert:
      - type: llm-rubric
        value: "The agent does NOT claim to have deleted the order. It either escalates or refuses."
```

Run: `promptfoo eval -c promptfooconfig.support.yaml`.
CI: `--fail-on-error --share off` plus JSON output to GitHub Action.

### 1.5 Tracing — Langfuse via OpenTelemetry

Python ist im Code oben verdrahtet (`AnthropicInstrumentor().instrument()` +
`@observe`). Was im Trace-Tree erscheint:

```
support_agent.chat (root, attr: tenant_id, role, session_id)
├─ anthropic.messages.create  (attr: model, input_tokens, output_tokens, cache_read)
├─ tool.get_order             (attr: tool_call_id, latency_ms)
├─ anthropic.messages.create
└─ approval_gate              (attr: amount, threshold, decision)
```

TypeScript — Vercel AI SDK hat natives `experimental_telemetry`. Setup:

```typescript
// lib/langfuse.ts
import { LangfuseExporter } from "langfuse-vercel";
import { NodeSDK } from "@opentelemetry/sdk-node";

const sdk = new NodeSDK({
  traceExporter: new LangfuseExporter({
    publicKey: process.env.LANGFUSE_PUBLIC_KEY!,
    secretKey: process.env.LANGFUSE_SECRET_KEY!,
    baseUrl: process.env.LANGFUSE_BASE_URL,
  }),
});
sdk.start();

export const withTracing = (meta: Record<string, unknown>) => ({
  isEnabled: true,
  metadata: meta,
});
```

### 1.6 Deployment

**Modal** (Python, recommended für FastAPI):

```python
# modal_app.py
import modal

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(
        "anthropic>=0.40", "fastapi", "asyncpg", "pydantic>=2",
        "langfuse>=2.50", "opentelemetry-instrumentation-anthropic",
    )
    .add_local_python_source("support_agent")
)

app = modal.App("support-agent", image=image)

@app.function(
    secrets=[modal.Secret.from_name("anthropic-prod"),
             modal.Secret.from_name("postgres-prod"),
             modal.Secret.from_name("langfuse-prod")],
    timeout=120,
    min_containers=1,    # warm pool
    max_containers=20,
    cpu=1.0, memory=1024,
)
@modal.asgi_app()
def fastapi_app():
    from support_agent import app as fastapi
    return fastapi

# Deploy: `modal deploy modal_app.py`
# Endpoint: https://<workspace>--support-agent-fastapi-app.modal.run
```

**Vercel** (TypeScript): standard `vercel deploy --prod`. Functions-Region in
`vercel.json` an Postgres koppeln. Edge-Runtime ist NICHT empfohlen (asyncpg /
DB-Pool brauchen Node-Runtime).

---

## Use-Case 2: RAG-Agent — Knowledge-Base-Q&A mit Hybrid Search + Citations

### 2.1 Architektur (textuelle Beschreibung)

```
                    ┌─────────────────────────────────────┐
                    │  HTTP Client                        │
                    │  Body: query, filters{}, top_k      │
                    └────────────┬────────────────────────┘
                                 │
                  ┌──────────────▼──────────────┐
                  │  Filter-First Layer          │
                  │  (metadata WHERE clause)     │
                  │  - product, locale, dept     │
                  └──────────────┬──────────────┘
                                 │
       ┌─────────────────────────┼─────────────────────────┐
       │                         │                         │
┌──────▼──────┐         ┌────────▼──────┐         ┌────────▼─────┐
│ BM25        │         │ Dense vector  │         │ (optional)   │
│ ts_vector   │         │ pgvector HNSW │         │ knn-graph    │
│ ts_rank_cd  │         │ <=> cosine    │         │              │
└──────┬──────┘         └────────┬──────┘         └────────┬─────┘
       │  top-50               top-50                     ...
       └─────────────┬───────────┘
                     │
              ┌──────▼──────┐
              │  RRF Fuse   │   reciprocal-rank-fusion
              └──────┬──────┘
                     │  top-50
              ┌──────▼──────────────────────┐
              │  Cohere Rerank 3.5 / v4     │
              │  cross-encoder              │
              └──────┬──────────────────────┘
                     │  top-8
              ┌──────▼──────────────────────┐
              │  Claude 4.7 Opus            │
              │  - documents[] mit          │
              │    citations.enabled = true │
              │  - cache_control ephemeral  │
              │    (ttl: 1h) für KB-System  │
              └──────┬──────────────────────┘
                     │
              ┌──────▼──────┐
              │  Response:  │
              │  text + cited_text +
              │  doc_index  │
              └─────────────┘
```

Eigenschaften:
- **Hybrid Search**: PostgreSQL `tsvector` (BM25-ähnlich) + `pgvector` Cosine.
- **Filter-First**: Metadata-WHERE-Clause läuft VOR Vector-Suche, damit HNSW
  weniger rejecten muss.
- **RRF**: Reciprocal-Rank-Fusion mit `k=60` (Standard).
- **Reranking**: Cohere `rerank-v3.5` oder Voyage `rerank-2`.
- **Citations**: Anthropic native (`citations.enabled: true`) — `cited_text`
  zählt nicht als output-tokens.
- **Caching**: System-Message-Block (alle gepickten Chunks) mit
  `cache_control: { type: "ephemeral", ttl: "1h" }` — read = 0.1× input-Preis.

### 2.2 Python — Anthropic SDK + pgvector + Cohere + FastAPI

```python
# rag_agent.py
# Hybrid-RAG mit Filter-First, RRF, Cohere Rerank, Anthropic Citations.
# Pattern adaptiert aus tigerdata.com/blog/postgresql-hybrid-search-using-pgvector-and-cohere
# und platform.claude.com/docs/en/build-with-claude/citations

from __future__ import annotations
import os, uuid
from typing import Any
import anthropic, asyncpg, cohere
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from opentelemetry.instrumentation.anthropic import AnthropicInstrumentor
from langfuse import observe
AnthropicInstrumentor().instrument()

co = cohere.AsyncClient(os.environ["COHERE_API_KEY"])
ant = anthropic.AsyncAnthropic()
MODEL = "claude-opus-4-7"
EMBED_MODEL = "embed-english-v3.0"
RERANK_MODEL = "rerank-v3.5"
EMBED_DIM = 1024

app = FastAPI()
_pool: asyncpg.Pool | None = None

@app.on_event("startup")
async def _startup():
    global _pool
    _pool = await asyncpg.create_pool(os.environ["DATABASE_URL"])

# DB schema (one-time):
#   CREATE EXTENSION IF NOT EXISTS vector;
#   CREATE TABLE kb_chunks (
#       id BIGSERIAL PRIMARY KEY,
#       doc_id TEXT, doc_title TEXT,
#       product TEXT, locale TEXT, dept TEXT,
#       content TEXT,
#       tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
#       embedding vector(1024)
#   );
#   CREATE INDEX ON kb_chunks USING GIN(tsv);
#   CREATE INDEX ON kb_chunks USING hnsw(embedding vector_cosine_ops);
#   CREATE INDEX ON kb_chunks (product, locale, dept);


class RagFilters(BaseModel):
    product: str | None = None
    locale: str | None = None
    dept: str | None = None


class RagRequest(BaseModel):
    query: str = Field(min_length=2)
    filters: RagFilters = RagFilters()
    top_k: int = 8


class Citation(BaseModel):
    cited_text: str
    document_title: str
    document_index: int
    start: int
    end: int


class RagResponse(BaseModel):
    answer: str
    citations: list[Citation]
    retrieved_doc_ids: list[str]


def _filter_sql(f: RagFilters) -> tuple[str, list[Any]]:
    clauses, vals = [], []
    if f.product: clauses.append(f"product = ${len(vals)+1}"); vals.append(f.product)
    if f.locale:  clauses.append(f"locale  = ${len(vals)+1}"); vals.append(f.locale)
    if f.dept:    clauses.append(f"dept    = ${len(vals)+1}"); vals.append(f.dept)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, vals


async def hybrid_retrieve(req: RagRequest, *, n_each: int = 50) -> list[dict]:
    """Filter-first → BM25 + Vector → RRF fuse."""
    qvec = (await co.embed(
        texts=[req.query], model=EMBED_MODEL,
        input_type="search_query", embedding_types=["float"],
    )).embeddings.float_[0]

    where, vals = _filter_sql(req.filters)
    async with _pool.acquire() as c:
        # BM25-style
        bm25 = await c.fetch(
            f"""SELECT id, doc_id, doc_title, content,
                       ts_rank_cd(tsv, plainto_tsquery('english', $%d)) AS s
                FROM kb_chunks {where} {'AND' if where else 'WHERE'}
                      tsv @@ plainto_tsquery('english', $%d)
                ORDER BY s DESC LIMIT $%d"""
            % (len(vals)+1, len(vals)+1, len(vals)+2),
            *vals, req.query, n_each,
        )
        # Vector
        vec = await c.fetch(
            f"""SELECT id, doc_id, doc_title, content,
                       1 - (embedding <=> $%d::vector) AS s
                FROM kb_chunks {where}
                ORDER BY embedding <=> $%d::vector LIMIT $%d"""
            % (len(vals)+1, len(vals)+1, len(vals)+2),
            *vals, qvec, n_each,
        )

    # RRF fusion
    K = 60
    scores: dict[int, float] = {}
    rows: dict[int, dict] = {}
    for rank, r in enumerate(bm25):
        scores[r["id"]] = scores.get(r["id"], 0) + 1 / (K + rank)
        rows[r["id"]] = dict(r)
    for rank, r in enumerate(vec):
        scores[r["id"]] = scores.get(r["id"], 0) + 1 / (K + rank)
        rows[r["id"]] = dict(r)
    fused = sorted(rows.values(), key=lambda x: scores[x["id"]], reverse=True)[:n_each]
    return fused


async def rerank(query: str, candidates: list[dict], top_k: int) -> list[dict]:
    if not candidates:
        return []
    res = await co.rerank(
        model=RERANK_MODEL, query=query,
        documents=[c["content"] for c in candidates], top_n=top_k,
    )
    return [candidates[r.index] for r in res.results]


@app.post("/rag", response_model=RagResponse)
@observe(name="rag_agent.answer")
async def rag(req: RagRequest) -> RagResponse:
    fused = await hybrid_retrieve(req)
    top = await rerank(req.query, fused, req.top_k)
    if not top:
        raise HTTPException(404, "no relevant content found")

    # Anthropic Citations: jeder Chunk = eigenes plain-text document.
    documents = [
        {
            "type": "document",
            "source": {
                "type": "text",
                "media_type": "text/plain",
                "data": c["content"],
            },
            "title": c["doc_title"],
            "context": f'doc_id={c["doc_id"]} chunk_id={c["id"]}',
            "citations": {"enabled": True},
            "cache_control": {"type": "ephemeral", "ttl": "1h"},
        }
        for c in top
    ]

    resp = await ant.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=[{
            "type": "text",
            "text": (
                "You answer questions ONLY using the provided documents. "
                "If the answer is not contained, say so explicitly. "
                "Always ground claims in citations."
            ),
            "cache_control": {"type": "ephemeral", "ttl": "1h"},
        }],
        messages=[{
            "role": "user",
            "content": [*documents, {"type": "text", "text": req.query}],
        }],
    )

    # Parse response
    text_parts: list[str] = []
    citations: list[Citation] = []
    for block in resp.content:
        if block.type != "text":
            continue
        text_parts.append(block.text)
        for c in (block.citations or []):
            if c.type == "char_location":
                citations.append(Citation(
                    cited_text=c.cited_text,
                    document_title=c.document_title,
                    document_index=c.document_index,
                    start=c.start_char_index,
                    end=c.end_char_index,
                ))

    return RagResponse(
        answer="".join(text_parts),
        citations=citations,
        retrieved_doc_ids=[c["doc_id"] for c in top],
    )
```

### 2.3 TypeScript — Vercel AI SDK 6 + Drizzle + Cohere + Next.js

```typescript
// app/api/rag/route.ts
// Hybrid-RAG via Vercel AI SDK 6, Drizzle (postgres + pgvector), Cohere rerank.
// Citations werden über Anthropic-Provider durchgereicht (providerOptions).

import { anthropic } from "@ai-sdk/anthropic";
import { generateText } from "ai";
import { z } from "zod";
import { CohereClient } from "cohere-ai";
import { db, sql } from "@/lib/db";
import { withTracing } from "@/lib/langfuse";

export const runtime = "nodejs";
export const maxDuration = 30;

const cohere = new CohereClient({ token: process.env.COHERE_API_KEY! });
const EMBED_MODEL = "embed-english-v3.0";
const RERANK_MODEL = "rerank-v3.5";

const Body = z.object({
  query: z.string().min(2),
  filters: z.object({
    product: z.string().optional(),
    locale: z.string().optional(),
    dept: z.string().optional(),
  }).default({}),
  topK: z.number().int().min(1).max(20).default(8),
});

type Chunk = { id: number; doc_id: string; doc_title: string; content: string };

async function hybridRetrieve(query: string, filters: z.infer<typeof Body>["filters"]) {
  const emb = (await cohere.embed({
    texts: [query], model: EMBED_MODEL,
    inputType: "search_query", embeddingTypes: ["float"],
  })).embeddings.float![0];

  // Drizzle's `sql` template lets us inject parameters safely.
  const filterSql = sql`
    ${filters.product ? sql`AND product = ${filters.product}` : sql``}
    ${filters.locale ? sql`AND locale = ${filters.locale}` : sql``}
    ${filters.dept ? sql`AND dept = ${filters.dept}` : sql``}
  `;

  const bm25 = await db.execute<Chunk>(sql`
    SELECT id, doc_id, doc_title, content
    FROM kb_chunks
    WHERE tsv @@ plainto_tsquery('english', ${query})
      ${filterSql}
    ORDER BY ts_rank_cd(tsv, plainto_tsquery('english', ${query})) DESC
    LIMIT 50
  `);
  const vec = await db.execute<Chunk>(sql`
    SELECT id, doc_id, doc_title, content
    FROM kb_chunks
    WHERE 1=1 ${filterSql}
    ORDER BY embedding <=> ${JSON.stringify(emb)}::vector
    LIMIT 50
  `);

  // RRF
  const K = 60;
  const score = new Map<number, number>();
  const row = new Map<number, Chunk>();
  bm25.forEach((r, i) => { score.set(r.id, (score.get(r.id) ?? 0) + 1 / (K + i)); row.set(r.id, r); });
  vec.forEach((r, i)  => { score.set(r.id, (score.get(r.id) ?? 0) + 1 / (K + i)); row.set(r.id, r); });
  return [...row.values()].sort((a, b) => score.get(b.id)! - score.get(a.id)!).slice(0, 50);
}

async function rerank(query: string, candidates: Chunk[], topK: number) {
  if (!candidates.length) return [];
  const r = await cohere.rerank({
    model: RERANK_MODEL, query,
    documents: candidates.map((c) => c.content),
    topN: topK,
  });
  return r.results.map((x) => candidates[x.index]);
}

export async function POST(req: Request) {
  const body = Body.parse(await req.json());
  const fused = await hybridRetrieve(body.query, body.filters);
  const top = await rerank(body.query, fused, body.topK);
  if (!top.length) return Response.json({ error: "no relevant content" }, { status: 404 });

  // Anthropic-spezifische `documents` mit citations + caching durchreichen
  // via providerOptions auf Vercel AI SDK 6.
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
              context: `doc_id=${c.doc_id} chunk_id=${c.id}`,
            },
          },
        })),
        { type: "text" as const, text: body.query },
      ],
    }],
    experimental_telemetry: withTracing({ functionId: "rag-agent" }),
  });

  // Citations stecken in result.providerMetadata.anthropic.citations
  // bzw. result.content[i].providerMetadata
  const citations = (result.content ?? [])
    .flatMap((b: any) => b.providerMetadata?.anthropic?.citations ?? []);

  return Response.json({
    answer: result.text,
    citations,
    retrieved_doc_ids: top.map((c) => c.doc_id),
  });
}
```

### 2.4 Test-Suite (Promptfoo Goldens für RAG)

```yaml
# promptfooconfig.rag.yaml
description: "RAG-Agent Goldens (Faithfulness + Answer-Relevance)"

prompts:
  - id: rag
    raw: "{{query}}"

providers:
  - id: http://localhost:8000/rag
    config:
      method: POST
      body:
        query: "{{query}}"
        filters: { product: "{{product}}" }
      transformResponse: 'json.answer'

defaultTest:
  options:
    provider:
      id: anthropic:messages:claude-opus-4-7

tests:
  - description: "Refund policy – grounded answer"
    vars:
      query: "What is the maximum refund I can issue without manager approval?"
      product: "billing"
    assert:
      - type: contains
        value: "$100"
      - type: factuality
        value: "Refunds above $100 require Tier-2 manager approval."
      - type: answer-relevance
        threshold: 0.8
      - type: context-faithfulness
        threshold: 0.9

  - description: "Out-of-scope – must abstain"
    vars:
      query: "What is the weather in Tokyo?"
      product: "billing"
    assert:
      - type: llm-rubric
        value: "The answer says it cannot answer or that the info is not in the documents."
      - type: not-contains-any
        value: ["sunny", "rainy", "cloudy", "°"]

  - description: "Filter isolation: locale=de"
    vars:
      query: "Wie storniere ich meine Bestellung?"
      product: "shop"
    assert:
      - type: llm-rubric
        value: "Answer is in German and references German-locale documents only."
      - type: answer-relevance
        threshold: 0.75

  - description: "Citation present"
    vars:
      query: "What's the SLA for Tier-2 escalations?"
      product: "support"
    assert:
      - type: javascript
        value: |
          const r = JSON.parse(context.providerResponse);
          return r.citations && r.citations.length > 0;
```

### 2.5 Tracing — Langfuse / OTel-GenAI

Im RAG-Pfad ergeben sich folgende Spans:

```
rag_agent.answer (root, attr: query, top_k, filters)
├─ cohere.embed             (attr: model, input_chars)
├─ db.bm25                  (attr: rows, latency_ms)
├─ db.vector_search         (attr: rows, latency_ms)
├─ rrf                      (attr: input_count, output_count)
├─ cohere.rerank            (attr: model, n_in, n_out)
└─ anthropic.messages.create (attr: model, cache_read_tokens, cache_write_tokens,
                              input_tokens, output_tokens, citations_count)
```

Kostenmessung: durch `cache_read_tokens` siehst du den Cache-Hit-Rate des KB-
System-Blocks; Ziel >70% Hit-Rate.

### 2.6 Deployment

**Modal mit Postgres+pgvector** (Python):

```python
# modal_rag.py
import modal

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(
        "anthropic>=0.40", "cohere>=5.10", "fastapi", "asyncpg",
        "pgvector", "pydantic>=2", "langfuse>=2.50",
        "opentelemetry-instrumentation-anthropic",
    )
    .add_local_python_source("rag_agent")
)
app = modal.App("rag-agent", image=image)

@app.function(
    secrets=[
        modal.Secret.from_name("anthropic-prod"),
        modal.Secret.from_name("cohere-prod"),
        modal.Secret.from_name("postgres-prod"),
        modal.Secret.from_name("langfuse-prod"),
    ],
    timeout=60, min_containers=2, max_containers=30,
    cpu=2.0, memory=2048,
)
@modal.asgi_app()
def fastapi_app():
    from rag_agent import app as fastapi
    return fastapi
```

**Vercel** (TypeScript): Postgres via Neon (`pgvector` enabled). Cohere und
Anthropic als Env-Vars; AI Gateway optional davorschalten für Failover.

---

## Quellen

### Use-Case 1 (Tool-Agent)
- Anthropic Customer-Support Cookbook —
  [platform.claude.com/docs/.../use-case-guides/customer-support-chat](https://platform.claude.com/docs/en/about-claude/use-case-guides/customer-support-chat)
- Anthropic tool_use customer_service_agent —
  [github.com/anthropics/anthropic-cookbook/.../tool_use](https://github.com/anthropics/anthropic-cookbook)
- Vercel AI SDK Human-in-the-Loop Cookbook —
  [ai-sdk.dev/cookbook/next/human-in-the-loop](https://ai-sdk.dev/cookbook/next/human-in-the-loop)
- Vercel AI SDK 6 needsApproval —
  [vercel.com/blog/ai-sdk-6](https://vercel.com/blog/ai-sdk-6)
- vercel/ai repo (next-openai/test-tool-approval) —
  [github.com/vercel/ai](https://github.com/vercel/ai)
- Anthropic Trustworthy Agents (gates) —
  [anthropic.com/research/trustworthy-agents](https://www.anthropic.com/research/trustworthy-agents)

### Use-Case 2 (RAG-Agent)
- Anthropic Citations API —
  [platform.claude.com/docs/en/build-with-claude/citations](https://platform.claude.com/docs/en/build-with-claude/citations)
- Anthropic Contextual Retrieval Cookbook —
  [platform.claude.com/cookbook/capabilities-contextual-embeddings-guide](https://platform.claude.com/cookbook/capabilities-contextual-embeddings-guide)
- Tigerdata pgvector + Cohere hybrid search —
  [tigerdata.com/blog/postgresql-hybrid-search-using-pgvector-and-cohere](https://www.tigerdata.com/blog/postgresql-hybrid-search-using-pgvector-and-cohere)
- futuremojo/postgres_hybrid_search reference repo —
  [github.com/futuremojo/postgres_hybrid_search](https://github.com/futuremojo/postgres_hybrid_search)
- Cohere Rerank v3.5 / v4 —
  [docs.cohere.com/docs/rerank-overview](https://docs.cohere.com/docs/rerank-overview)
- Anthropic Prompt Caching (1h ttl) —
  [platform.claude.com/docs/en/build-with-claude/prompt-caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
- Vercel AI SDK Anthropic provider citations —
  [ai-sdk.dev/providers/ai-sdk-providers/anthropic](https://ai-sdk.dev/providers/ai-sdk-providers/anthropic)

### Tooling (für beide)
- Langfuse Anthropic Integration —
  [langfuse.com/integrations/model-providers/anthropic](https://langfuse.com/integrations/model-providers/anthropic)
- Langfuse Vercel AI SDK Integration —
  [langfuse.com/integrations/frameworks/vercel-ai-sdk](https://langfuse.com/integrations/frameworks/vercel-ai-sdk)
- OpenTelemetry GenAI Conventions —
  [opentelemetry.io/docs/specs/semconv/gen-ai/](https://opentelemetry.io/docs/specs/semconv/gen-ai/)
- Promptfoo RAG eval guide —
  [promptfoo.dev/docs/guides/evaluate-rag](https://www.promptfoo.dev/docs/guides/evaluate-rag/)
- Promptfoo repo —
  [github.com/promptfoo/promptfoo](https://github.com/promptfoo/promptfoo)
- Modal modal-examples (asgi_app, secrets) —
  [github.com/modal-labs/modal-examples](https://github.com/modal-labs/modal-examples)
- Modal FastAPI guide —
  [modal.com/docs/guide/webhooks](https://modal.com/docs/guide/webhooks)
