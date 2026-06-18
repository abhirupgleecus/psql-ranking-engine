-- Phase 2v2: Model Number Search Improvements
-- Idempotent migration script — safe to run multiple times.
--
-- 1. Add a GIN trigram index on model_number for fast arbitrary substring matching
-- 2. Promote model_number from Weight C to Weight B in the generated search_vector column
--    NOTE: GENERATED ALWAYS AS ... STORED columns cannot have their expression altered
--    in-place. The column must be dropped and re-added with the updated expression.
--    PostgreSQL will automatically repopulate the column from live row data.

-- Step 1: GIN trigram index on model_number
-- Requires pg_trgm (already enabled by migrate_phase2.sql).
-- CREATE INDEX IF NOT EXISTS is fully idempotent.
CREATE INDEX IF NOT EXISTS idx_product_master_model_number_trgm
    ON product_master USING gin (model_number gin_trgm_ops);

-- Step 2: Recreate search_vector with model_number at Weight B
-- First drop the GIN index that references the column, then drop-and-recreate the column,
-- then recreate the GIN index.
DROP INDEX IF EXISTS idx_product_master_search_vector;

ALTER TABLE product_master DROP COLUMN IF EXISTS search_vector;

ALTER TABLE product_master
ADD COLUMN search_vector tsvector
GENERATED ALWAYS AS (
    setweight(to_tsvector('english', coalesce(name, '')), 'A') ||
    setweight(to_tsvector('english', coalesce(brand, '')), 'B') ||
    setweight(to_tsvector('english', coalesce(category, '')), 'B') ||
    setweight(to_tsvector('english', coalesce(model_number, '')), 'B') ||
    setweight(to_tsvector('english', coalesce(sub_category, '')), 'C') ||
    setweight(to_tsvector('english', coalesce(type, '')), 'C') ||
    setweight(to_tsvector('english', coalesce(immutable_array_to_string(required_certifications, ' '), '')), 'D') ||
    setweight(to_tsvector('english', coalesce(immutable_array_to_string(hazardous_materials, ' '), '')), 'D')
) STORED;

-- Recreate the GIN index on the updated search_vector column
CREATE INDEX IF NOT EXISTS idx_product_master_search_vector
    ON product_master USING GIN(search_vector);
