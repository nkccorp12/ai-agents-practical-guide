// app/api/rag/route.ts
// Hybrid-RAG pipeline on Next.js App Router with Vercel AI SDK 6.
// Filter-first SQL -> BM25 + dense vector -> RRF -> Cohere rerank ->
// Anthropic generation with native citations and 1h prompt cache.
// Pattern adapted from the Vercel AI SDK Anthropic provider docs.

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
const RRF_K = 60;

const Body = z.object({
  query: z.string().min(2),
  filters: z
    .object({
      product: z.string().optional(),
      locale: z.string().optional(),
      dept: z.string().optional(),
    })
    .default({}),
  topK: z.number().int().min(1).max(20).default(8),
});

type Chunk = {
  id: number;
  doc_id: string;
  doc_title: string;
  content: string;
};

async function hybridRetrieve(
  query: string,
  filters: z.infer<typeof Body>["filters"],
) {
  const emb = (
    await cohere.embed({
      texts: [query],
      model: EMBED_MODEL,
      inputType: "search_query",
      embeddingTypes: ["float"],
    })
  ).embeddings.float![0];

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

  const score = new Map<number, number>();
  const row = new Map<number, Chunk>();
  bm25.forEach((r, i) => {
    score.set(r.id, (score.get(r.id) ?? 0) + 1 / (RRF_K + i));
    row.set(r.id, r);
  });
  vec.forEach((r, i) => {
    score.set(r.id, (score.get(r.id) ?? 0) + 1 / (RRF_K + i));
    row.set(r.id, r);
  });
  return [...row.values()]
    .sort((a, b) => score.get(b.id)! - score.get(a.id)!)
    .slice(0, 50);
}

async function rerank(query: string, candidates: Chunk[], topK: number) {
  if (!candidates.length) return [];
  const r = await cohere.rerank({
    model: RERANK_MODEL,
    query,
    documents: candidates.map((c) => c.content),
    topN: topK,
  });
  return r.results.map((x) => candidates[x.index]);
}

export async function POST(req: Request) {
  const body = Body.parse(await req.json());
  const fused = await hybridRetrieve(body.query, body.filters);
  const top = await rerank(body.query, fused, body.topK);
  if (!top.length) {
    return Response.json({ error: "no relevant content" }, { status: 404 });
  }

  const result = await generateText({
    model: anthropic("claude-opus-4-7"),
    system: [
      {
        type: "text",
        text: "You answer ONLY from provided documents. Cite all claims.",
        providerOptions: {
          anthropic: { cacheControl: { type: "ephemeral", ttl: "1h" } },
        },
      },
    ],
    messages: [
      {
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
      },
    ],
    experimental_telemetry: withTracing({ functionId: "rag-agent" }),
  });

  // Anthropic citations surface via providerMetadata on each content block.
  const citations = (result.content ?? []).flatMap(
    (b: any) => b.providerMetadata?.anthropic?.citations ?? [],
  );

  return Response.json({
    answer: result.text,
    citations,
    retrieved_doc_ids: top.map((c) => c.doc_id),
  });
}
