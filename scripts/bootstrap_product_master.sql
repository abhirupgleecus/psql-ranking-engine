-- Bootstrap the base product_master table for fresh databases.
--
-- This intentionally creates only the pre-Phase-2 schema so the existing
-- Phase 2 and Phase 3 migration scripts can add search_vector and embedding
-- in the normal repo-supported order.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'product_status') THEN
        CREATE TYPE product_status AS ENUM ('DRAFT', 'ACTIVE', 'INACTIVE', 'ARCHIVED');
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'complexity_level') THEN
        CREATE TYPE complexity_level AS ENUM ('LOW', 'MEDIUM', 'HIGH');
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'product_type') THEN
        CREATE TYPE product_type AS ENUM ('SMALL_WHITE_GOODS', 'LARGE_WHITE_GOODS');
    END IF;
END
$$;

CREATE SEQUENCE IF NOT EXISTS product_master_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

CREATE TABLE IF NOT EXISTS product_master (
    id integer NOT NULL,
    uuid uuid NOT NULL,
    status product_status NOT NULL,
    type character varying(100),
    name character varying(255) NOT NULL,
    category character varying(100),
    sub_category character varying(100),
    brand character varying(100) NOT NULL,
    manufacturer jsonb NOT NULL,
    upc character varying(50),
    variant character varying(100),
    model_number character varying(100) NOT NULL,
    serial_number character varying(100),
    model_year integer,
    weight_lb numeric(10,3),
    weight_kg numeric(10,3),
    dimensions_inches character varying(100),
    repairability_score numeric(5,2),
    disassembly_complexity complexity_level,
    average_life_span_years integer,
    energy_efficiency_rating character varying(50),
    authorized_needed boolean,
    special_handling_required boolean,
    contains_user_data boolean,
    mandatory_data_wipe_needed boolean,
    required_certifications character varying[],
    market_value jsonb NOT NULL,
    market_value_avgs jsonb NOT NULL,
    hazardous_materials character varying[],
    additional_data jsonb DEFAULT '{"source_data": "customer_data"}'::jsonb,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    goods_type product_type DEFAULT 'SMALL_WHITE_GOODS'::product_type NOT NULL,
    master_uuid character varying(100),
    gtin character varying(50),
    ean character varying(50),
    CONSTRAINT product_master_pkey PRIMARY KEY (id)
);

ALTER SEQUENCE product_master_id_seq OWNED BY product_master.id;
ALTER TABLE ONLY product_master
    ALTER COLUMN id SET DEFAULT nextval('product_master_id_seq'::regclass);

CREATE INDEX IF NOT EXISTS ix_product_master_name
    ON product_master USING btree (name);

CREATE INDEX IF NOT EXISTS ix_product_master_upc
    ON product_master USING btree (upc);

CREATE UNIQUE INDEX IF NOT EXISTS ix_product_master_uuid
    ON product_master USING btree (uuid);
