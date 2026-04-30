"""Hybrid-RAG agent with filter-first retrieval, RRF fusion, Cohere rerank,
and Anthropic native citations.

Pattern adapted from the Tigerdata pgvector + Cohere hybrid-search blog and
the Anthropic Citations API documentation.

Run locally:
    uvicorn main:app --reload
"""
from __future__ import annotations

import os
from typing import Any

import anthropic
import asyncpg
import cohere
from fastapi import FastAPI, HTTPException
from langfuse import observe
from opentelemetry.instrumentation.anthropic import AnthropicInstrumentor
from pydantic import BaseModel, Field

AnthropicInstrumentor().instrument()

co = cohere.AsyncClient(os.environ["COHERE_API_KEY"])
ant = anthropic.AsyncAnthropic()

MODEL = "claude-opus-4-7"
EMBED_MODEL = "embed-english-v3.0"
RERANK_MODEL = "rerank-v3.5"
EMBED_DIM = 1024
RRF_K = 60
N_EACH = 50

app = FastAPI()
_pool: asyncpg.Pool | None = None


@app.on_event("startup")
async def _startup() -> None:
    global _pool
    _pool = await asyncpg.create_pool(os.environ["DATABASE_URL"])


@app.on_event("shutdown")
async def _shutdown() -> None:
    if _pool is not None:
        await _pool.close()


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
    clauses: list[str] = []
    vals: list[Any] = []
    if f.product:
        clauses.append(f"product = ${len(vals) + 1}")
        vals.append(f.product)
    if f.locale:
        clauses.append(f"locale = ${len(vals) + 1}")
        vals.append(f.locale)
    if f.dept:
        clauses.append(f"dept = ${len(vals) + 1}")
        vals.append(f.dept)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, vals


async def hybrid_retrieve(req: RagRequest, *, n_each: int = N_EACH) -> list[dict]:
    """Filter-first then BM25 + dense vector then RRF fuse."""
    assert _pool is not None
    qvec = (
        await co.embed(
            texts=[req.query],
            model=EMBED_MODEL,
            input_type="search_query",
            embedding_types=["float"],
        )
    ).embeddings.float_[0]

    where, vals = _filter_sql(req.filters)
    bm25_join = "AND" if where else "WHERE"
    bm25_query_idx = len(vals) + 1
    bm25_limit_idx = len(vals) + 2
    vec_query_idx = len(vals) + 1
    vec_limit_idx = len(vals) + 2

    async with _pool.acquire() as conn:
        bm25 = await conn.fetch(
            f"""SELECT id, doc_id, doc_title, content,
                       ts_rank_cd(tsv, plainto_tsquery('english', ${bm25_query_idx})) AS s
                FROM kb_chunks
                {where}
                {bm25_join} tsv @@ plainto_tsquery('english', ${bm25_query_idx})
                ORDER BY s DESC
                LIMIT ${bm25_limit_idx}""",
            *vals,
            req.query,
            n_each,
        )
        vec = await conn.fetch(
            f"""SELECT id, doc_id, doc_title, content,
                       1 - (embedding <=> ${vec_query_idx}::vector) AS s
                FROM kb_chunks
                {where}
                ORDER BY embedding <=> ${vec_query_idx}::vector
                LIMIT ${vec_limit_idx}""",
            *vals,
            qvec,
            n_each,
        )

    scores: dict[int, float] = {}
    rows: dict[int, dict] = {}
    for rank, row in enumerate(bm25):
        scores[row["id"]] = scores.get(row["id"], 0) + 1 / (RRF_K + rank)
        rows[row["id"]] = dict(row)
    for rank, row in enumerate(vec):
        scores[row["id"]] = scores.get(row["id"], 0) + 1 / (RRF_K + rank)
        rows[row["id"]] = dict(row)
    return sorted(rows.values(), key=lambda x: scores[x["id"]], reverse=True)[:n_each]


async def rerank(query: str, candidates: list[dict], top_k: int) -> list[dict]:
    if not candidates:
        return []
    res = await co.rerank(
        model=RERANK_MODEL,
        query=query,
        documents=[c["content"] for c in candidates],
        top_n=top_k,
    )
    return [candidates[r.index] for r in res.results]


@app.post("/rag", response_model=RagResponse)
@observe(name="rag_agent.answer")
async def rag(req: RagRequest) -> RagResponse:
    fused = await hybrid_retrieve(req)
    top = await rerank(req.query, fused, req.top_k)
    if not top:
        raise HTTPException(404, "no relevant content found")

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
        system=[
            {
                "type": "text",
                "text": (
                    "You answer questions ONLY using the provided documents. "
                    "If the answer is not contained, say so explicitly. "
                    "Always ground claims in citations."
                ),
                "cache_control": {"type": "ephemeral", "ttl": "1h"},
            }
        ],
        messages=[
            {
                "role": "user",
                "content": [*documents, {"type": "text", "text": req.query}],
            }
        ],
    )

    text_parts: list[str] = []
    citations: list[Citation] = []
    for block in resp.content:
        if block.type != "text":
            continue
        text_parts.append(block.text)
        for c in block.citations or []:
            if c.type == "char_location":
                citations.append(
                    Citation(
                        cited_text=c.cited_text,
                        document_title=c.document_title,
                        document_index=c.document_index,
                        start=c.start_char_index,
                        end=c.end_char_index,
                    )
                )

    return RagResponse(
        answer="".join(text_parts),
        citations=citations,
        retrieved_doc_ids=[c["doc_id"] for c in top],
    )
