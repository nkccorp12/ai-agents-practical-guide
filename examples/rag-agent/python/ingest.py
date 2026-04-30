"""Ingest plain-text or Markdown files into the kb_chunks table.

Usage:
    python ingest.py path/to/docs/*.md \
        --product billing --locale en --dept support

Each file is split into ~800-character chunks (~200-token overlap), embedded
via Cohere `embed-english-v3.0` (input_type=search_document), and inserted
with pgvector. The tsvector is generated automatically by the schema.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import pathlib
import re
import uuid

import asyncpg
import cohere

EMBED_MODEL = "embed-english-v3.0"
EMBED_DIM = 1024
CHUNK_SIZE = 800
CHUNK_OVERLAP = 200


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= size:
        return [text]
    chunks: list[str] = []
    step = max(1, size - overlap)
    for start in range(0, len(text), step):
        chunk = text[start : start + size]
        if chunk:
            chunks.append(chunk)
        if start + size >= len(text):
            break
    return chunks


async def ingest(
    paths: list[pathlib.Path],
    *,
    product: str | None,
    locale: str | None,
    dept: str | None,
) -> None:
    co = cohere.AsyncClient(os.environ["COHERE_API_KEY"])
    pool = await asyncpg.create_pool(os.environ["DATABASE_URL"])
    assert pool is not None
    try:
        async with pool.acquire() as conn:
            for path in paths:
                doc_id = str(uuid.uuid5(uuid.NAMESPACE_URL, str(path.resolve())))
                title = path.stem
                content = path.read_text(encoding="utf-8")
                chunks = chunk_text(content)
                if not chunks:
                    continue
                emb = await co.embed(
                    texts=chunks,
                    model=EMBED_MODEL,
                    input_type="search_document",
                    embedding_types=["float"],
                )
                vectors = emb.embeddings.float_
                async with conn.transaction():
                    for chunk, vec in zip(chunks, vectors):
                        await conn.execute(
                            """INSERT INTO kb_chunks
                               (doc_id, doc_title, product, locale, dept, content, embedding)
                               VALUES ($1, $2, $3, $4, $5, $6, $7)""",
                            doc_id,
                            title,
                            product,
                            locale,
                            dept,
                            chunk,
                            vec,
                        )
                print(f"ingested {len(chunks)} chunks from {path}")
    finally:
        await pool.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", type=pathlib.Path)
    parser.add_argument("--product", default=None)
    parser.add_argument("--locale", default=None)
    parser.add_argument("--dept", default=None)
    args = parser.parse_args()
    asyncio.run(
        ingest(args.paths, product=args.product, locale=args.locale, dept=args.dept)
    )


if __name__ == "__main__":
    main()
