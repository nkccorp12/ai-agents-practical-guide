"""Tool implementations for the customer-support agent.

Each tool accepts a Principal (tenant_id, user_id, role) and validated args.
The dispatch layer enforces a tool-name allowlist (hallucination guard) and a
hard timeout. Approvals are handled at the orchestrator level in main.py.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from typing import Any, Literal

import asyncpg
from pydantic import BaseModel

TOOL_TIMEOUT_S = 5.0
REFUND_APPROVAL_THRESHOLD_USD = 100.0


class Principal(BaseModel):
    tenant_id: str
    user_id: str
    role: Literal["tier1_support", "tier2_support", "admin"]


class ToolError(Exception):
    """Raised by tool implementations to surface a tool_result with is_error=true."""


# Anthropic JSON-schema definitions (passed to messages.create as `tools=`).
TOOLS: list[dict[str, Any]] = [
    {
        "name": "get_order",
        "description": "Fetch order details by order_id for the current tenant.",
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string", "description": "UUID of the order"},
            },
            "required": ["order_id"],
        },
    },
    {
        "name": "refund_order",
        "description": (
            "Refund part or full amount of an order. Refunds above $100 require "
            "Tier-2 manual approval. The model MUST still call this tool; the "
            "server pauses the loop and requests approval out-of-band."
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
        "description": "Hand off to a human agent. Use when unsure or for non-policy requests.",
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {"type": "string", "minLength": 5},
            },
            "required": ["reason"],
        },
    },
]
TOOL_NAMES = {t["name"] for t in TOOLS}


async def audit(
    pool: asyncpg.Pool,
    actor: Principal,
    tool: str,
    args: dict,
    status_: str,
    result: Any,
    trace_id: str,
) -> None:
    args_hash = hashlib.sha256(json.dumps(args, sort_keys=True).encode()).hexdigest()
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO audit_log
               (id, ts, tenant_id, user_id, role, tool, args_hash, status, result, trace_id)
               VALUES ($1, now(), $2, $3, $4, $5, $6, $7, $8, $9)""",
            uuid.uuid4(),
            actor.tenant_id,
            actor.user_id,
            actor.role,
            tool,
            args_hash,
            status_,
            json.dumps(result, default=str)[:4000],
            trace_id,
        )


async def tool_get_order(pool: asyncpg.Pool, actor: Principal, args: dict) -> dict:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, total_usd, status, created_at FROM orders "
            "WHERE id = $1 AND tenant_id = $2",
            args["order_id"],
            actor.tenant_id,
        )
    if not row:
        raise ToolError("order not found in your tenant")
    return dict(row)


async def tool_refund_order(
    pool: asyncpg.Pool,
    actor: Principal,
    args: dict,
    *,
    approved: bool,
) -> dict:
    if (
        args["amount"] > REFUND_APPROVAL_THRESHOLD_USD
        and actor.role == "tier1_support"
        and not approved
    ):
        # Defence in depth: orchestrator should already have stashed an approval.
        raise ToolError("refund > $100 requires tier2 approval")
    async with pool.acquire() as conn:
        async with conn.transaction():
            order = await conn.fetchrow(
                "SELECT total_usd FROM orders WHERE id = $1 AND tenant_id = $2 FOR UPDATE",
                args["order_id"],
                actor.tenant_id,
            )
            if not order:
                raise ToolError("order not found")
            if args["amount"] > float(order["total_usd"]):
                raise ToolError("refund exceeds order total")
            await conn.execute(
                """INSERT INTO refunds (id, order_id, tenant_id, amount, reason, approved_by)
                   VALUES ($1, $2, $3, $4, $5, $6)""",
                uuid.uuid4(),
                args["order_id"],
                actor.tenant_id,
                args["amount"],
                args["reason"],
                actor.user_id,
            )
    return {"status": "refunded", "amount": args["amount"]}


async def tool_escalate_to_human(pool: asyncpg.Pool, actor: Principal, args: dict) -> dict:
    async with pool.acquire() as conn:
        ticket_id = await conn.fetchval(
            """INSERT INTO escalations (id, tenant_id, user_id, reason)
               VALUES ($1, $2, $3, $4) RETURNING id""",
            uuid.uuid4(),
            actor.tenant_id,
            actor.user_id,
            args["reason"],
        )
    return {"status": "escalated", "ticket_id": str(ticket_id)}


async def dispatch_tool(
    pool: asyncpg.Pool,
    name: str,
    args: dict,
    actor: Principal,
    *,
    approved: bool,
) -> dict:
    """Hallucination-guarded dispatch with hard timeout."""
    if name not in TOOL_NAMES:
        raise ToolError(f"unknown tool: {name}")
    try:
        async with asyncio.timeout(TOOL_TIMEOUT_S):
            if name == "get_order":
                return await tool_get_order(pool, actor, args)
            if name == "refund_order":
                return await tool_refund_order(pool, actor, args, approved=approved)
            if name == "escalate_to_human":
                return await tool_escalate_to_human(pool, actor, args)
    except asyncio.TimeoutError as exc:
        raise ToolError(f"tool {name} timed out after {TOOL_TIMEOUT_S}s") from exc
    raise ToolError("unreachable")
