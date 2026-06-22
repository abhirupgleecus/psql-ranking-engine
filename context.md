# psql-ranking-poc Context

## Overview

`psql-ranking-poc` is a multi-stage relevance-ranking proof of concept built with FastAPI, PostgreSQL, SQLAlchemy async, Alembic, and Pydantic.

- Stage 1 (v1): Application-scored deterministic ranking in Python.
- Stage 2 (v2): PostgreSQL-native full-text search with ILIKE wildcard fallback.
- Stage 3 (v3): Hybrid search combining lexical (v2) and semantic (pgvector) retrieval via Reciprocal Rank Fusion (RRF).

As of June 17, 2026, Phase 1, Phase 2, Phase 2v2, Phase 2v3, and Phase 3 are completed.
As of June 22, 2026, planning and repo-prep work for a new Elastic-backed `/search/v2.2` path has started.

## Current Status

### Completed Phases

#### Phase 1: ProductMaster Migration
1. Added a read-only `ProductMaster` ORM model backed by `product_master`.
2. Updated schemas and the v1 scorer flow to query `ProductMaster`.
3. Restricted active search results to `ProductStatus.ACTIVE`.
4. Updated `eval.py` and `test_cases.json` to target the restored `product_master` dataset.

#### Phase 2: Full-text + Wildcard Search (`/search/v2`)
1. `scripts/migrate_phase2.sql` enables `pg_trgm`, creates `immutable_array_to_string`, adds the generated `search_vector` column, and creates the GIN index.
2. `app/search_engine_v2.py` normalizes the query into prefix tsquery tokens and falls back to wildcard `ILIKE` search when needed.
3. `app/routers/search_v2.py` exposes `GET /search/v2`.
4. `scripts/eval.py` supports `--engine v2`.

#### Phase 2v2: Model Number Search Improvements (`/search/v2`)
1. `scripts/migrate_phase2_v2.sql` adds a GIN trigram index on `model_number` and reconstructs the `search_vector` generated column with `model_number` promoted from Weight C → B.
2. `app/search_engine_v2.py` modifies the primary FTS path to match on both `search_vector @@ to_tsquery` and `model_number ILIKE :wildcard` (using GIN trigram index), blending `similarity(model_number, :raw_query)` into the FTS ranking.
3. `scripts/run_migrate_phase2_v2.py` is the python migration runner.

#### Phase 2v3: UPC ID Search & Search Vector Re-weighting (`/search/v2` & `/search/v3`)
1. `scripts/migrate_phase2_v3.sql` creates a GIN trigram index on `upc` (`idx_product_master_upc_trgm`) and reconstructs the `search_vector` generated column to apply new weights (Weight A: brand, model_number, upc; Weight B: name, category; Weight C: sub_category, type; Weight D: required_certifications, hazardous_materials).
2. `app/search_engine_v2.py` incorporates `upc ILIKE :wildcard` into FTS and fallback queries, and blends `coalesce(similarity(upc, :raw_query), 0.0) * 2.0` into the FTS ranking formula.
3. `scripts/run_migrate_phase2_v3.py` is the python migration runner.

#### Phase 3: Hybrid Search (`/search/v3`)
1. `scripts/migrate_phase3.sql` enables `vector`, adds `embedding vector(768)`, and creates the HNSW index.
2. `app/embedding_client.py` wraps Gemini Embedding 2 via `google-genai`.
3. `scripts/embed_products.py` batch-embeds rows where `embedding IS NULL`.
4. `app/rrf.py` implements Reciprocal Rank Fusion.
5. `app/search_engine_v3.py` combines lexical and semantic retrieval, then fuses results with RRF.
6. `app/routers/search_v3.py` exposes `GET /search/v3`.
7. `scripts/eval.py` supports `--engine v3`.

### Verified State

- `tests/test_scorer.py` passes.
- `tests/test_rrf.py` passes.
- `tests/test_search_v2.py` passes.
- Docker Compose PostgreSQL (`pgvector/pgvector:pg17`) is the active local database and runs on `localhost:5433`.
- `.env` points to `postgresql+asyncpg://postgres:password@localhost:5433/psql_ranking_poc`.
- `scripts/bootstrap_product_master.sql` creates the base `product_master` schema, sequence, enum types, and indexes. It is idempotent.
- The Dockerized `product_master` has been bootstrapped, imported from the native PostgreSQL dataset (port 5432), and migrated through Phase 3.
- `product_master` currently contains **30,492 rows**.
- A duplicate key error during `pg_dump` import is expected and safe to ignore if rows already exist.
- `vector` extension is enabled; the `embedding vector(768)` column and `idx_product_master_embedding` HNSW index exist.
- Phase 2 and Phase 3 migrations are idempotent and have completed successfully against the Dockerized database.
- Eval harness verified for v1 and v2:
  - `eval.py --engine v1`: `12/12 cases passed = 100.0%`
  - `eval.py --engine v2`: `12/12 cases passed = 100.0%`
- v3 (`/search/v3`) requires `GOOGLE_AI_API_KEY` in `.env` plus a completed `scripts/embed_products.py` run before semantic results are populated. If `GOOGLE_AI_API_KEY` is not set, it degrades gracefully to lexical-only RRF search (`search_mode: lexical`).
- Embeddings are currently empty (0 rows embedded); the HNSW index exists but will only serve lexical fallback until embedding pipeline runs.

### Elastic `v2.2` Repo Prep Status

- The future `GET /search/v2.2` endpoint is planned to be behaviorally identical to `GET /search/v2`, but backed by Elastic instead of PostgreSQL.
- `docs/elastic-v2-2-migration-plan.md` contains the two-deliverable migration plan across all 13 phases.
- `docs/search-v2-contract.md` freezes the current `v2` input/output and fallback behavior so `v2.2` can target strict parity.
- `docs/search-v2-elastic-document.md` defines the target Elastic document model derived from `product_master`.
- `scripts/es/product_master_v2_mapping.json` contains the initial versioned Elastic mapping and alias plan:
  - read alias: `product_master_v2_read`
  - write alias: `product_master_v2_write`
  - first concrete index: `product_master_v2_0001`
- `scripts/create_es_index_v2.py` creates the versioned Elastic index using the checked-in mapping.
- `app/elastic_client.py` provides a lazy async Elastic client helper driven by environment settings in `app/database.py`.
- `scripts/check_elastic_connection.py` validates repo-to-Elastic connectivity.
- `infra/cdc/debezium-product-master-v2.json` and `infra/cdc/es-sink-product-master-v2.json` are starter connector templates for the future CDC pipeline.
- No runtime application endpoint behavior has changed yet:
  - `/search/v2` is still PostgreSQL-backed
  - `/search/v2.2` has not been implemented yet

## Stack

- Python 3.12 in the local virtualenv
- FastAPI
- SQLAlchemy 2.x async with `asyncpg`
- PostgreSQL
- Docker Desktop
- Alembic
- Pydantic v2
- pytest
- httpx
- `pgvector`
- `google-genai`
- `elasticsearch-py`

## Important Files

- `app/main.py`
  - FastAPI app setup and router registration for `/search`, `/search/v2`, and `/search/v3`
- `app/database.py`
  - settings loading, async engine, async session factory
- `app/models.py`
  - `Product` and `ProductMaster` ORM models
- `app/search_engine_v2.py`
  - PostgreSQL full-text + wildcard search logic
- `app/search_engine_v3.py`
  - hybrid lexical + semantic orchestration
- `app/embedding_client.py`
  - Gemini Embedding 2 client wrapper
- `app/elastic_client.py`
  - lazy async Elastic client helper for the planned `v2.2` backend
- `app/rrf.py`
  - Reciprocal Rank Fusion implementation
- `docs/elastic-v2-2-migration-plan.md`
  - end-to-end plan for the Elastic-backed `v2.2` migration
- `docs/search-v2-contract.md`
  - frozen contract for `v2` parity work
- `docs/search-v2-elastic-document.md`
  - target search document model for Elastic
- `scripts/bootstrap_product_master.sql`
  - base `product_master` bootstrap SQL for fresh databases
- `scripts/check_elastic_connection.py`
  - verifies Elastic connection using repo configuration
- `scripts/create_es_index_v2.py`
  - creates the versioned Elastic index and aliases for future `v2.2`
- `scripts/es/product_master_v2_mapping.json`
  - first checked-in Elastic mapping for the future `v2.2` index
- `scripts/migrate_phase2.sql`
  - Phase 2 SQL migration
- `scripts/migrate_phase2_v2.sql`
  - Phase 2v2 SQL migration (trigram index + Weight B promotion)
- `scripts/migrate_phase2_v3.sql`
  - Phase 2v3 SQL migration (UPC trigram index + field re-weighting)
- `scripts/migrate_phase3.sql`
  - Phase 3 SQL migration
- `scripts/run_migrate_phase2.py`
  - Python runner for Phase 2
- `scripts/run_migrate_phase2_v2.py`
  - Python runner for Phase 2v2
- `scripts/run_migrate_phase2_v3.py`
  - Python runner for Phase 2v3
- `scripts/run_migrate_phase3.py`
  - Python runner for Phase 3
- `scripts/embed_products.py`
  - batch embedding pipeline for `product_master`
- `scripts/seed.py`
  - legacy seed for the separate `products` table
- `scripts/eval.py`
  - eval harness supporting v1, v2, and v3
- `infra/cdc/debezium-product-master-v2.json`
  - starter Debezium source connector config for `product_master`
- `infra/cdc/es-sink-product-master-v2.json`
  - starter Elastic sink connector config targeting the write alias
- `test_cases.json`
  - expected top-3 benchmark cases

## Database Notes

### `products`

`products` is the older table used by the legacy seed path.

- `scripts/seed.py` populates `products`.
- The active API endpoints do not search `products`.

### `product_master`

`product_master` is the active catalog table used by `/search`, `/search/v2`, and `/search/v3`.

Key characteristics:
- Base schema can be created with `scripts/bootstrap_product_master.sql`.
- `search_vector` is generated and indexed by the Phase 2 migration.
- `embedding vector(768)` plus the HNSW index are added by the Phase 3 migration.
- `pg_trgm` and `vector` extensions are required for the full v2/v3 flow.

## Search Flow

### v2

1. Validate request params.
2. Normalize query text into prefix-based tsquery tokens.
3. Run PostgreSQL search: matches rows using either FTS (tsquery), model_number substring, or upc substring (ILIKE wildcard matching accelerated by the GIN trigram indexes on model_number and upc).
4. Rank results by blending `ts_rank_cd`, `similarity(model_number, :raw_query) * 2.0`, and `similarity(upc, :raw_query) * 2.0`.
5. If there are no primary matches and fallback is enabled, run wildcard `ILIKE` search across name, brand, category, model_number, upc, etc.

### v3

1. Validate request params.
2. Run the lexical v2 pass with an enlarged candidate pool.
3. Embed the query with Gemini Embedding 2.
4. Run pgvector cosine-distance retrieval over active rows with non-null embeddings.
5. Fuse lexical and semantic rankings with RRF.
6. Hydrate final product rows and return debug metadata such as `matched_in`, `lexical_rank`, and `semantic_rank`.

## Commands

From the project root on Windows:

1. Install dependencies

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. Start the Dockerized PostgreSQL database

```powershell
docker compose up -d postgres
```

3. Bootstrap the base `product_master` schema in Docker

```powershell
$env:PGPASSWORD='password'
& 'C:\Program Files\PostgreSQL\18\bin\psql.exe' -h localhost -p 5433 -U postgres -d psql_ranking_poc -v ON_ERROR_STOP=1 -f scripts\bootstrap_product_master.sql
```

4. Import the restored native `product_master` dataset into Docker

```powershell
$env:PGPASSWORD='password'
& 'C:\Program Files\PostgreSQL\18\bin\pg_dump.exe' -h localhost -p 5432 -U postgres -d psql_ranking_poc -a -t public.product_master -f "$env:TEMP\product_master_data.sql"
& 'C:\Program Files\PostgreSQL\18\bin\psql.exe' -h localhost -p 5433 -U postgres -d psql_ranking_poc -v ON_ERROR_STOP=1 -f "$env:TEMP\product_master_data.sql"
```

5. Apply Phase 2, Phase 2v2, Phase 2v3, and Phase 3 migrations

```powershell
.\.venv\Scripts\python.exe -m scripts.run_migrate_phase2
.\.venv\Scripts\python.exe -m scripts.run_migrate_phase2_v2
.\.venv\Scripts\python.exe -m scripts.run_migrate_phase2_v3
.\.venv\Scripts\python.exe -m scripts.run_migrate_phase3
```

6. Run the embedding pipeline for v3

```powershell
.\.venv\Scripts\python.exe scripts\embed_products.py
```

7. Start the API

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

8. Run the eval harness

```powershell
.\.venv\Scripts\python.exe scripts\eval.py --engine v1
.\.venv\Scripts\python.exe scripts\eval.py --engine v2
.\.venv\Scripts\python.exe scripts\eval.py --engine v3
```

9. Run tests

```powershell
.\.venv\Scripts\pytest
```

## Known Limitations

- v1 fetches all filtered candidates into the application layer before scoring (no SQL-level ranking).
- `scripts/seed.py` targets the legacy `products` table; all active API endpoints use `product_master`.
- `product_master` cannot yet be seeded from a repo-native source — data must be imported from an existing database or external source.
- Stage 3 (`/search/v3`) degrades gracefully to lexical-only RRF search if `GOOGLE_AI_API_KEY` is not set. Full hybrid mode requires a valid key and running `scripts/embed_products.py` to populate embeddings.
- The embedding pipeline is a manual batch job with no automatic re-embedding trigger when product fields change.
- No explicit secondary tie-breaker in v1 beyond descending `total_score`.
- v3 RRF fusion may rerank results differently from v2 — this is expected and reflects the semantic component.

## Good Next Steps

- Complete Elastic Cloud deployment and PostgreSQL CDC prerequisites for the planned `/search/v2.2` path.
- Deploy and validate the Debezium + Elastic sink pipeline against the checked-in index mapping and aliases.
- Implement `/search/v2.2` against Elastic while preserving strict parity with `/search/v2`.
- Add side-by-side parity tests for `/search/v2` vs `/search/v2.2`.
