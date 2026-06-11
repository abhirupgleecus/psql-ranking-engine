# psql-ranking-poc Context

## Overview

`psql-ranking-poc` is a Stage 1 relevance-ranking proof of concept built with FastAPI, PostgreSQL, SQLAlchemy async, Alembic, and Pydantic.

- Stage 1 is intentionally application-scored.
- PostgreSQL is currently the system of record and candidate fetch layer.
- Ranking is performed in Python by `app/scorer.py`.
- The schema already includes a few future-facing indexes for later Stage 2 and Stage 3 work.

As of June 10, 2026, Phase 1 and Phase 2 (full-text + wildcard search) are completed. Phase 3 (trigram and vector search) comes later.

## Current Status

### Completed Phases

#### Phase 1: ProductMaster Migration
1. **Parallel database model**: Added read-only `ProductMaster` ORM model backed by `product_master` table.
2. **Schema reshaping**: Created `RankedProductMaster` response and `ScoreBreakdown` models; simplified `SearchRequest` to remove status parameters/filters.
3. **Scorer rewrite**: Retuned scoring signals around `ProductMaster` properties and removed status signals (only `ACTIVE` products are displayed/searched).
4. **Search path migration**: Modified `/search` endpoint to query from `ProductMaster` and restrict results to `ProductStatus.ACTIVE`.
5. **Evaluation harness alignment**: Updated `eval.py` and `test_cases.json` to target real `uuid` and product data.

#### Phase 2: Full-text + Wildcard Search (/search/v2)
1. **Database Migration (`scripts/migrate_phase2.sql`)**: 
   - Enabled the `pg_trgm` extension.
   - Defined `immutable_array_to_string` to convert array columns immutably.
   - Added a stored generated `search_vector` column to `product_master` indexing `name` (A), `brand` (B), `category` (B), `sub_category` (C), `type` (C), `model_number` (C), and stringified array fields (`required_certifications`, `hazardous_materials`) (D).
   - Created a GIN index on the `search_vector` column.
2. **Reshaped Schemas**:
   - Added `SearchRequestV2` containing a `fallback_enabled` toggle.
   - Added `RankedProductMasterV2` returning `search_score` and `search_mode` ("fulltext" or "wildcard").
   - Added `SearchResponseV2` returning overall `search_mode` for the query.
3. **SQL Search Engine (`app/search_engine_v2.py`)**:
   - Created a query normalizer converting natural language to a prefix-matching tsquery (`word:*`).
   - Implemented a dual-path logic: runs full-text search with `ts_rank_cd` and, if zero results are returned and `fallback_enabled` is active, falls back to a multi-field `ILIKE` wildcard query.
4. **Endpoint (`app/routers/search_v2.py`)**:
   - Exposed `GET /search/v2` calling the database search engine.
5. **Testing & Eval Harness**:
   - Updated `scripts/eval.py` to support target engine selection via `--engine v1` or `--engine v2`.
   - Created `tests/test_search_v2.py` integration tests verifying the API behavior.
   - Configured `app/database.py` to use `NullPool` during testing to prevent asyncpg connection collision errors.

### Verified state

- `tests/test_scorer.py` and `tests/test_search_v2.py` pass cleanly in the virtualenv.
- Alembic upgrades cleanly through the latest revision.
- `scripts/seed.py` inserts 50 realistic products and is idempotent.
- `scripts/eval.py` passes against the running API for both v1 and v2 engines:
  - `eval.py --engine v1`: `12/12 cases passed = 100.0%`
  - `eval.py --engine v2`: `12/12 cases passed = 100.0%` (using fulltext with automatic wildcard fallback where needed).

## Stack

- Python 3.12 in the local virtualenv
- FastAPI
- SQLAlchemy 2.x async with `asyncpg`
- PostgreSQL
- Alembic
- Pydantic v2
- pytest
- httpx

## Important Files

- `app/main.py`
  - FastAPI app setup
  - lifespan DB connectivity check
  - registers search router (`/search`) and search_v2 router (`/search/v2`)
- `app/database.py`
  - environment-backed settings
  - async engine with `NullPool` detection for testing
  - async session factory
  - `get_db`
- `app/models.py`
  - `Product` and `ProductMaster` ORM models
- `app/schemas.py`
  - search request and response models for both v1 and v2
- `app/scorer.py`
  - additive deterministic ranking logic in Python (v1)
- `app/search_engine_v2.py`
  - PostgreSQL-driven FTS and wildcard search logic (v2)
- `app/routers/search.py`
  - `/search` endpoint (v1)
- `app/routers/search_v2.py`
  - `/search/v2` endpoint (v2)
- `scripts/migrate_phase2.sql`
  - SQL script to migrate database schema for full-text capabilities
- `scripts/run_migrate_phase2.py`
  - Python runner for Phase 2 migration
- `scripts/seed.py`
  - deterministic dataset for seeding
- `scripts/eval.py`
  - top-3 evaluation harness supporting `--engine` selection
- `test_cases.json`
  - 12 eval cases derived from seeded fixed product IDs

## Database State

### Products table

The initial table is `products`.

### Product Master table

The main table for the migrated catalog is `product_master`.

Key characteristics:
- Stored generated `search_vector` column using weighting (A through D).
- GIN index `idx_product_master_search_vector` on `search_vector`.
- pg_trgm extension enabled.

## Search Flow (v2)

The Stage 2 `/search/v2` flow is:

1. Validate query params with `SearchRequestV2`
2. If query tokens exist, build prefix-based tsquery and fetch using FTS (@@) sorted by `ts_rank_cd DESC`
3. If FTS returns results, return immediately with `search_mode: "fulltext"` and the FTS rank scores
4. If FTS returns 0 results and `fallback_enabled` is True, execute fallback query using `ILIKE` on name, brand, category, sub_category, type, model_number, and array columns (via `immutable_array_to_string`). Returns results with `search_mode: "wildcard"` and a score of `0.0`.

## Seed Dataset

`scripts/seed.py` inserts a deterministic catalog of 50 products across exactly 5 categories:

- `electronics`
- `footwear`
- `clothing`
- `kitchen`
- `fitness`

Dataset properties:
- 10 products per category
- fixed UUIDs for repeatable evaluation
- realistic name, brand, tag, description, price, rating, and stock state

## Evaluation Harness

`scripts/eval.py`:
- loads `test_cases.json`
- calls `GET /search` (for v1) or `GET /search/v2` (for v2) with `top_n=3`
- checks whether each case's expected IDs appear in the returned top 3
- prints per-case `PASS` or `FAIL`
- exits with code `1` if accuracy is below `90.0`

## Commands

From the project root on Windows:

1. Apply Phase 2 DB Migration

```powershell
.\.venv\Scripts\python.exe -m scripts.run_migrate_phase2
```

2. Seed the database

```powershell
.\.venv\Scripts\python.exe scripts\seed.py
```

3. Start the API

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

4. Run the eval harness (v1 or v2)

```powershell
.\.venv\Scripts\python.exe scripts\eval.py --engine v1
.\.venv\Scripts\python.exe scripts\eval.py --engine v2
```

5. Run unit/integration tests

```powershell
.\.venv\Scripts\pytest
```

## Known Limitations

- Wildcard search scores are hardcoded to `0.0`.
- We do not have trigram/fuzzy text matching yet (reserved for Phase 3).
- Vector/semantic search is not implemented (reserved for Phase 3).

## Good Next Steps

- **Phase 3**: Introduce fuzzy search using `pg_trgm` (`%` operator) and explore vector search capabilities.
- Add performance telemetry to compare the execution speed of Phase 1 vs Phase 2 search paths.
