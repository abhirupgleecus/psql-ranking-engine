-- Phase 2v3: Search by UPC ID & Re-weighting search vector fields
-- Idempotent migration script — safe to run multiple times.
--
-- 1. Create a GIN trigram index on upc for fast arbitrary substring matching.
-- 2. Drop and recreate the search_vector generated column to support the new weights:
--    A: brand, model_number, upc
--    B: name, category
--    C: sub_category, type
--    D: required_certifications, hazardous_materials

-- Step 1: GIN trigram index on upc
-- Requires pg_trgm (already enabled).
CREATE INDEX IF NOT EXISTS idx_product_master_upc_trgm
    ON product_master USING gin (upc gin_trgm_ops);

-- Step 2: Recreate search_vector column with updated weights
-- First drop the GIN index referencing the column, then drop-and-recreate the column,
-- then recreate the GIN index on the column.
DROP INDEX IF EXISTS idx_product_master_search_vector;

ALTER TABLE product_master DROP COLUMN IF EXISTS search_vector;

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

-- Recreate the GIN index on the updated search_vector column
CREATE INDEX IF NOT EXISTS idx_product_master_search_vector
    ON product_master USING GIN(search_vector);
