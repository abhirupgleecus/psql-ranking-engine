-- Phase 2: Full-text + Wildcard Search
-- Idempotent migration script — safe to run multiple times.
--
-- 1. Enable pg_trgm extension (needed for ILIKE index acceleration and Phase 3 trigram similarity)
-- 2. Add a stored generated tsvector column with weighted fields
-- 3. Add a GIN index on the generated column for fast @@ matching

-- Step 1: pg_trgm extension
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Step 1b: Define immutable wrapper for array_to_string
-- Standard array_to_string is STABLE, which cannot be used in GENERATED columns.
CREATE OR REPLACE FUNCTION immutable_array_to_string(arr text[], sep text)
RETURNS text AS $$
BEGIN
    RETURN array_to_string(arr, sep);
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Step 2: Generated tsvector column
-- Uses DO block with IF NOT EXISTS check for idempotency since
-- ALTER TABLE ADD COLUMN does not support IF NOT EXISTS for generated columns
-- in all PostgreSQL versions.
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
            setweight(to_tsvector('english', coalesce(name, '')), 'A') ||
            setweight(to_tsvector('english', coalesce(brand, '')), 'B') ||
            setweight(to_tsvector('english', coalesce(category, '')), 'B') ||
            setweight(to_tsvector('english', coalesce(sub_category, '')), 'C') ||
            setweight(to_tsvector('english', coalesce(type, '')), 'C') ||
            setweight(to_tsvector('english', coalesce(model_number, '')), 'C') ||
            setweight(to_tsvector('english', coalesce(immutable_array_to_string(required_certifications, ' '), '')), 'D') ||
            setweight(to_tsvector('english', coalesce(immutable_array_to_string(hazardous_materials, ' '), '')), 'D')
        ) STORED;
    END IF;
END
$$;

-- Step 3: GIN index on the search_vector column
CREATE INDEX IF NOT EXISTS idx_product_master_search_vector
    ON product_master USING GIN(search_vector);

