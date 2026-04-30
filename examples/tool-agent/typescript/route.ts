// app/api/support/route.ts
// Customer-support agent on Next.js App Router with Vercel AI SDK 6.
// The `needsApproval` callback declaratively gates refunds above $100.
// Pattern adapted from the Vercel AI SDK human-in-the-loop cookbook.

import { anthropic } from "@ai-sdk/anthropic";
import { streamText, tool, stepCountIs } from "ai";
import { z } from "zod";
import { auth } from "@/lib/auth";
import { db } from "@/lib/db";
import { audit } from "@/lib/audit";
import { withTracing } from "@/lib/langfuse";

export const runtime = "nodejs";
export const maxDuration = 60;

const REFUND_THRESHOLD = 100;

export async function POST(req: Request) {
  const principal = await auth(req);
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
      // Declarative approval gate: pauses the run when amount exceeds threshold
      // and the caller is not already a Tier-2 agent. The client resumes via
      // addToolApprovalResponse once a reviewer signs off.
      needsApproval: async ({ amount }) =>
        amount > REFUND_THRESHOLD && principal.role !== "tier2_support",
      execute: async ({ order_id, amount, reason }) => {
        const result = await db.transaction(async (tx) => {
          const order = await tx.query.orders.findFirst({
            where: (o, { and, eq }) =>
              and(eq(o.id, order_id), eq(o.tenantId, principal.tenantId)),
          });
          if (!order) throw new Error("order not found");
          if (amount > Number(order.totalUsd))
            throw new Error("refund exceeds order total");
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
        const ticket = await db
          .insert(db.schema.escalations)
          .values({
            tenantId: principal.tenantId,
            userId: principal.userId,
            reason,
          })
          .returning({ id: db.schema.escalations.id });
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
    stopWhen: stepCountIs(10),
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
