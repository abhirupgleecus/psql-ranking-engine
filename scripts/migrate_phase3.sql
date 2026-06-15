-- Phase 3: Hybrid Search — pgvector setup
-- Idempotent migration script — safe to run multiple times.
--
-- 1. Enable pgvector extension
-- 2. Add a nullable vector(768) column for Gemini Embedding 2 embeddings
-- 3. Create an HNSW index for fast cosine similarity search

-- Step 1: pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Step 2: Embedding column
-- Uses DO block with IF NOT EXISTS check for idempotency.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'product_master'
          AND column_name = 'embedding'
    ) THEN
        ALTER TABLE product_master ADD COLUMN embedding vector(768);
    END IF;
END
$$;

-- Step 3: HNSW index for cosine similarity
-- HNSW chosen over IVFFlat: no `lists` tuning needed, supports incremental
-- inserts without rebuild — better fit for a POC dataset.
CREATE INDEX IF NOT EXISTS idx_product_master_embedding
    ON product_master USING hnsw (embedding vector_cosine_ops);
