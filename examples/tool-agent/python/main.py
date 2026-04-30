"""Customer-support agent with approval gate (FastAPI + Anthropic SDK).

Pattern adapted from the Anthropic customer-service tool-use cookbook.

Endpoints:
    POST /chat        run a turn (and resume after approval if approval_token)
    POST /approve     consume an approval token (Tier-2 only)

Run locally:
    uvicorn main:app --reload
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from contextlib import asynccontextmanager

import anthropic
import asyncpg
from fastapi import Depends, FastAPI, Header, HTTPException, status
from langfuse import get_client, observe, propagate_attributes
from opentelemetry.instrumentation.anthropic import AnthropicInstrumentor
from pydantic import BaseModel, ValidationError

from tools import (
    REFUND_APPROVAL_THRESHOLD_USD,
    TOOLS,
    Principal,
    ToolError,
    audit,
    dispatch_tool,
)

AnthropicInstrumentor().instrument()
langfuse = get_client()

logger = logging.getLogger("support_agent")
logging.basicConfig(level=logging.INFO)

MODEL = "claude-opus-4-7"
MAX_HOPS = 10

SYSTEM_PROMPT = """You are Eva, a customer-support agent for Acme.
You can read orders, issue refunds, and escalate to humans.
Rules:
- Never refund without first calling get_order to verify amount and tenant.
- Always include a clear reason for refunds and escalations.
- If a customer is hostile or requesting non-policy actions, escalate.
- Refunds over $100 require human approval. Call the tool anyway; the system
  will pause and ask the appropriate human. Do not invent that you finished it.
"""

_pool: asyncpg.Pool | None = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    global _pool
    _pool = await asyncpg.create_pool(
        os.environ["DATABASE_URL"], min_size=2, max_size=10
    )
    yield
    await _pool.close()


def parse_principal(authorization: str | None = Header(None)) -> Principal:
    """Demo parser. In production use jwt.decode(token, JWT_PUBKEY, ...)."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    raw = authorization.removeprefix("Bearer ")
    try:
        claims = json.loads(raw)
        return Principal(**claims)
    except (ValidationError, json.JSONDecodeError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"invalid token: {exc}") from exc


class ChatRequest(BaseModel):
    conversation_id: str
    message: str
    approval_token: str | None = None


class ChatResponse(BaseModel):
    conversation_id: str
    output: str | None = None
    requires_approval: dict | None = None
    trace_id: str


client = anthropic.AsyncAnthropic()
app = FastAPI(lifespan=lifespan)


@app.post("/chat", response_model=ChatResponse)
@observe(name="support_agent.chat")
async def chat(
    req: ChatRequest,
    principal: Principal = Depends(parse_principal),
) -> ChatResponse:
    assert _pool is not None
    trace_id = uuid.uuid4().hex
    with propagate_attributes(
        user_id=principal.user_id,
        session_id=req.conversation_id,
        tags=["agent", "customer_support", principal.role],
        metadata={"tenant_id": principal.tenant_id},
    ):
        async with _pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT role, content FROM conversations "
                "WHERE id = $1 AND tenant_id = $2 ORDER BY created_at",
                req.conversation_id,
                principal.tenant_id,
            )
        messages: list[dict] = [json.loads(r["content"]) for r in rows]

        # Resume after approval, otherwise append the new user turn.
        if req.approval_token:
            approval = await _consume_approval(req.approval_token, principal)
            tool_result = await dispatch_tool(
                _pool, approval["tool"], approval["args"], principal, approved=True,
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

        for _ in range(MAX_HOPS):
            try:
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
            except anthropic.RateLimitError as exc:
                raise HTTPException(429, "llm rate-limited, retry") from exc
            except anthropic.APIError as exc:
                logger.exception("llm error")
                raise HTTPException(502, f"llm error: {exc}") from exc

            messages.append({"role": "assistant", "content": resp.content})

            if resp.stop_reason == "end_turn":
                text = "".join(b.text for b in resp.content if b.type == "text")
                await _persist_messages(req.conversation_id, principal, messages)
                return ChatResponse(
                    conversation_id=req.conversation_id,
                    output=text,
                    trace_id=trace_id,
                )

            if resp.stop_reason == "tool_use":
                tool_blocks = [b for b in resp.content if b.type == "tool_use"]
                tool_results: list[dict] = []
                for tb in tool_blocks:
                    if (
                        tb.name == "refund_order"
                        and tb.input.get("amount", 0) > REFUND_APPROVAL_THRESHOLD_USD
                        and principal.role != "tier2_support"
                    ):
                        token = await _stash_approval(
                            req.conversation_id, principal, tb.id, tb.name, tb.input,
                        )
                        await _persist_messages(req.conversation_id, principal, messages)
                        await audit(
                            _pool, principal, tb.name, tb.input,
                            "pending_approval", None, trace_id,
                        )
                        return ChatResponse(
                            conversation_id=req.conversation_id,
                            requires_approval={
                                "tool": tb.name,
                                "args": tb.input,
                                "approval_token": token,
                            },
                            trace_id=trace_id,
                        )
                    try:
                        result = await dispatch_tool(
                            _pool, tb.name, tb.input, principal, approved=False,
                        )
                        await audit(_pool, principal, tb.name, tb.input, "ok", result, trace_id)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tb.id,
                            "content": json.dumps(result, default=str),
                        })
                    except ToolError as exc:
                        await audit(_pool, principal, tb.name, tb.input, "error", str(exc), trace_id)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tb.id,
                            "is_error": True,
                            "content": str(exc),
                        })
                messages.append({"role": "user", "content": tool_results})
                continue

            raise HTTPException(500, f"unexpected stop_reason: {resp.stop_reason}")

        raise HTTPException(500, "agent loop exceeded hop limit")


async def _stash_approval(
    conv_id: str,
    p: Principal,
    tool_use_id: str,
    tool: str,
    args: dict,
) -> str:
    assert _pool is not None
    token = uuid.uuid4().hex
    async with _pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO pending_approvals
               (token, conversation_id, tenant_id, requested_by, tool_use_id, tool, args)
               VALUES ($1, $2, $3, $4, $5, $6, $7)""",
            token, conv_id, p.tenant_id, p.user_id, tool_use_id, tool, json.dumps(args),
        )
    return token


async def _consume_approval(token: str, approver: Principal) -> dict:
    assert _pool is not None
    if approver.role != "tier2_support":
        raise HTTPException(403, "only tier2 may approve")
    async with _pool.acquire() as conn:
        row = await conn.fetchrow(
            "DELETE FROM pending_approvals WHERE token = $1 AND tenant_id = $2 RETURNING *",
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
    assert _pool is not None
    async with _pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "DELETE FROM conversations WHERE id = $1 AND tenant_id = $2",
                conv_id, p.tenant_id,
            )
            for m in messages:
                await conn.execute(
                    """INSERT INTO conversations (id, tenant_id, role, content, created_at)
                       VALUES ($1, $2, $3, $4, now())""",
                    conv_id, p.tenant_id, m["role"], json.dumps(m, default=str),
                )
