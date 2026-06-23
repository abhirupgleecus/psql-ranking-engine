-- PostgreSQL CDC Prep Migration Script
-- Idempotent migration script — safe to run multiple times.
--
-- 1. Sets replica identity on product_master (required for Debezium CDC deletes/updates)
-- 2. Creates logical replication publication for product_master if not exists

-- Step 1: Set Replica Identity on product_master to DEFAULT
-- (Uses the primary key 'uuid' to identify rows in CDC events)
ALTER TABLE public.product_master REPLICA IDENTITY DEFAULT;

-- Step 2: Create publication 'dbz_pub_product_master_v2' for the table
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM pg_publication 
        WHERE pubname = 'dbz_pub_product_master_v2'
    ) THEN
        CREATE PUBLICATION dbz_pub_product_master_v2 FOR TABLE public.product_master;
    END IF;
END
$$;
