-- Consolidated Migration Script for Stage 2 (v2) and Stage 3 (v3)
-- Idempotent migration script — safe to run multiple times.
--
-- 1. Enable pg_trgm and vector extensions
-- 2. Define immutable wrapper for array_to_string
-- 3. Add generated tsvector column search_vector with final v2.2/v3 weights
-- 4. Add nullable embedding vector(768) column for semantic search
-- 5. Create all required GIN (trigram and tsvector) and HNSW (vector) indexes

-- Step 1: Enable required extensions
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS vector;

-- Step 2: Define immutable wrapper for array_to_string (needed for GENERATED column)
CREATE OR REPLACE FUNCTION immutable_array_to_string(arr text[], sep text)
RETURNS text AS $$
BEGIN
    RETURN array_to_string(arr, sep);
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Step 3: Add generated tsvector column for full-text search
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'product_master'
          AND column_name = 'search_vector'
    ) THEN
        ALTER TABLE product_master
        ADD COLUMN search_vector tsvector
        GENERATED ALWAYS AS (
            setweight(to_tsvector('english', coalesce(brand, '')), 'A') ||
            setweight(to_tsvector('english', coalesce(model_number, '')), 'A') ||
            setweight(to_tsvector('english', coalesce(upc, '')), 'A') ||
            setweight(to_tsvector('english', coalesce(name, '')), 'B') ||
            setweight(to_tsvector('english', coalesce(category, '')), 'B') ||
            setweight(to_tsvector('english', coalesce(sub_category, '')), 'C') ||
            setweight(to_tsvector('english', coalesce(type, '')), 'C') ||
            setweight(to_tsvector('english', coalesce(immutable_array_to_string(required_certifications, ' '), '')), 'D') ||
            setweight(to_tsvector('english', coalesce(immutable_array_to_string(hazardous_materials, ' '), '')), 'D')
        ) STORED;
    END IF;
END
$$;

-- Step 4: Add embedding vector column for semantic search
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

-- Step 5: Create indexes
-- 5a. GIN index on tsvector for FTS
CREATE INDEX IF NOT EXISTS idx_product_master_search_vector
    ON product_master USING GIN(search_vector);

-- 5b. GIN trigram index on model_number for fast substring matches
CREATE INDEX IF NOT EXISTS idx_product_master_model_number_trgm
    ON product_master USING gin (model_number gin_trgm_ops);

-- 5c. GIN trigram index on upc for fast substring matches
CREATE INDEX IF NOT EXISTS idx_product_master_upc_trgm
    ON product_master USING gin (upc gin_trgm_ops);

-- 5d. HNSW index for fast cosine similarity search on embeddings
CREATE INDEX IF NOT EXISTS idx_product_master_embedding
    ON product_master USING hnsw (embedding vector_cosine_ops);
