# psql-ranking-poc Context

## Overview

`psql-ranking-poc` is a Stage 1 relevance-ranking proof of concept built with FastAPI, PostgreSQL, SQLAlchemy async, Alembic, and Pydantic.

- Stage 1 is intentionally application-scored.
- PostgreSQL is currently the system of record and candidate fetch layer.
- Ranking is performed in Python by `app/scorer.py`.
- The schema already includes a few future-facing indexes for later Stage 2 and Stage 3 work.

As of June 10, 2026, Phase 1 of the ProductMaster search migration is completed. Phase 2 (full-text + wildcard search) comes later.

## Current Status

### Completed Phases (Phase 1)

1. **Parallel database model**: Added read-only `ProductMaster` ORM model backed by `product_master` table.
2. **Schema reshaping**: Created `RankedProductMaster` response and `ScoreBreakdown` models; simplified `SearchRequest` to remove status parameters/filters.
3. **Scorer rewrite**: Retuned scoring signals around `ProductMaster` properties and removed status signals (only `ACTIVE` products are displayed/searched).
4. **Search path migration**: Modified `/search` endpoint to query from `ProductMaster` and restrict results to `ProductStatus.ACTIVE`.
5. **Evaluation harness alignment**: Updated `eval.py` and `test_cases.json` to target real `uuid` and product data.

### Verified state

- `tests/test_scorer.py` passes in the project virtualenv.
- Alembic upgrades cleanly through the latest revision.
- `scripts/seed.py` inserts 50 realistic products and is idempotent.
- `scripts/eval.py` passes against a running local API.
- Latest observed eval result on June 8, 2026: `24/24 cases passed = 100.0%`

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
  - `/health`
- `app/database.py`
  - environment-backed settings
  - async engine
  - async session factory
  - `get_db`
- `app/models.py`
  - `Product` ORM model
  - unique constraint on `(name, brand)`
- `app/schemas.py`
  - search request and response models
- `app/scorer.py`
  - additive deterministic ranking logic
- `app/routers/search.py`
  - `/search` endpoint
- `scripts/seed.py`
  - deterministic dataset for Phase 7
  - PostgreSQL upsert-based idempotent seeding
- `scripts/eval.py`
  - top-3 evaluation harness
- `test_cases.json`
  - 24 eval cases derived from seeded fixed product IDs

## Database State

### Products table

The main table is `products`.

Key characteristics:

- UUID primary key with `gen_random_uuid()`
- future-facing GIN index on `to_tsvector('english', name)`
- GIN index on `tags`
- B-tree indexes on `brand` and `category`
- unique constraint on `(name, brand)`

### Migration history

- `e884a7c1b51e`
  - creates the initial `products` table and indexes
- `eb7a3f8d6c2a`
  - adds `uq_products_name_brand`

The second migration was added to support Phase 7 idempotent inserts using PostgreSQL conflict handling.

## Search Flow

The Stage 1 `/search` flow is:

1. Validate query params with `SearchRequest`
2. Fetch candidates from PostgreSQL with optional `category` prefilter, filtering for `status == "ACTIVE"`
3. Convert ORM rows to plain dicts
4. Score each product in Python via `score_product`
5. Drop results below `min_score`
6. Sort by `total_score DESC`
7. Return top `N`

## Scoring Behavior

The scorer is additive and operates on `ProductMaster` fields.

Signals currently include:

- exact, startswith, whole-word, and contains matching on `name`
- exact and contains matching on `brand`
- exact and contains matching on `category`
- contains matching on `type`, `sub_category`, and `model_number`
- exact matching on `required_certifications`
- contains matching on `hazardous_materials`
- boost for high repairability (`repairability_score >= 0.75`)

### Nuances

- All returned products are active, so status boosts and penalties have been removed.
- Because ranking is additive and there is no second-pass semantic filter yet, exact query matches often occupy rank 1 while highly boosted unrelated products can still appear in ranks 2-3.
- Sort order is only `total_score DESC`. There is no explicit secondary tie-breaker yet.

That last point matters for evaluation: the test suite was intentionally written to avoid depending on ambiguous tie ordering.

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
- realistic names, brands, tags, descriptions, prices, ratings, and stock state
- overlapping brands and terms such as:
  - multiple Nike products across footwear, clothing, and fitness
  - multiple wireless audio products in electronics
  - multiple blender SKUs in kitchen
  - multiple recovery/yoga items in fitness
- at least 10 products with `rating >= 4.5` and `review_count >= 100`
- at least 5 out-of-stock products

### Idempotency

The seed script uses PostgreSQL `ON CONFLICT DO NOTHING` against `(name, brand)`.

Observed verification:

- first run inserted 50 rows
- second run inserted 0 rows

## Evaluation Harness

`scripts/eval.py`:

- loads `test_cases.json`
- calls `GET /search?q=<query>&top_n=3`
- checks whether each case's expected IDs appear in the returned top 3
- prints per-case `PASS` or `FAIL`
- prints a final accuracy line
- exits with code `1` if accuracy is below `90.0`

### Current eval suite

- 24 cases total
- mixture of:
  - exact product-name queries
  - case-insensitive queries
  - whitespace-normalization queries
  - multi-hit queries such as `wireless headphones`, `blender`, `massage gun`, `yoga mat`, and `cuisinart`

Latest verified output:

`Accuracy: 24/24 cases passed = 100.0%`

## Commands

From the project root on Windows:

1. Apply migrations

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
```

2. Seed the database

```powershell
.\.venv\Scripts\python.exe scripts\seed.py
```

3. Start the API

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

4. Run the eval harness

```powershell
.\.venv\Scripts\python.exe scripts\eval.py --base-url http://127.0.0.1:8000
```

5. Run scorer unit tests

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_scorer.py
```

## Known Limitations

- Stage 1 still fetches all filtered candidates into the app and scores them in Python.
- There is no SQL-native ranking yet.
- There is no vector search yet.
- Tie-breaking is not explicit beyond descending score.
- `score_breakdown` is currently represented in the response model as `dict[str, int]` rather than a dedicated `ScoreBreakdown` schema type.

Those are acceptable for the current Stage 1 POC, but they are worth keeping in mind before future ranking work.

## Good Next Steps

When work resumes, the most natural next direction is Phase 2 / Stage 2:

- **Phase 2**: Introduce full-text search with PG `tsvector`/`tsquery` and wildcard matching.
- **Stage 2**: Push lexical scoring into PostgreSQL.
- Keep the current seed dataset and eval harness as a regression baseline.
