-- Schema for the RAG-agent reference (hybrid search + Anthropic citations).
-- Run once: psql "$DATABASE_URL" -f schema.sql

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS kb_chunks (
    id          BIGSERIAL PRIMARY KEY,
    doc_id      TEXT NOT NULL,
    doc_title   TEXT NOT NULL,
    product     TEXT,
    locale      TEXT,
    dept        TEXT,
    content     TEXT NOT NULL,
    tsv         tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
    embedding   vector(1024)
);

-- BM25-style full-text index.
CREATE INDEX IF NOT EXISTS kb_chunks_tsv_idx
    ON kb_chunks USING GIN(tsv);

-- HNSW index for cosine similarity on dense embeddings.
CREATE INDEX IF NOT EXISTS kb_chunks_embedding_hnsw
    ON kb_chunks USING hnsw(embedding vector_cosine_ops);

-- Filter columns. Filter-first: WHERE on these runs before the ANN search.
CREATE INDEX IF NOT EXISTS kb_chunks_filters_idx
    ON kb_chunks (product, locale, dept);
