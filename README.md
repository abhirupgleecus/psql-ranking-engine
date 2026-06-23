# PostgreSQL Ranking POC

A small, practical reference implementation for **application-layer relevance ranking on top of PostgreSQL**.

This repo shows how to:

- store a product catalog in PostgreSQL
- fetch search candidates with async SQLAlchemy
- apply deterministic ranking logic in Python (Stage 1 `/search`)
- compute native relevance ranking inside PostgreSQL using full-text search with wildcard fallback (Stage 2 `/search/v2`)
- validate relevance quality with a repeatable eval harness

It is designed as a **relevance ranking proof-of-concept** that other developers can understand quickly and either:

- run as a standalone search service, or
- embed into an existing backend that needs SQL-backed search ranking

## What This POC Is

This project intentionally keeps ranking logic in the application layer.

Current approach:

- PostgreSQL stores product data
- the app fetches candidate rows
- Python computes a `total_score` and `score_breakdown`
- results are sorted and returned by score

That makes it easy to:

- understand exactly why a product ranked where it did
- tune weights without rewriting SQL
- port the logic into another application
- establish a clean baseline before moving to full-text search or vector search

## Current Scope

Implemented today:

- **Stage 1 (`/search`)**: FastAPI service with deterministic rule-based scorer running in the application layer.
- **Stage 2 (`/search/v2`)**: Native PostgreSQL-scored full-text search (using a stored generated `tsvector` column and `ts_rank_cd`) blended with GIN-indexed trigram similarity matching on `model_number` and `upc` for accurate substring retrieval and ranking.
- **Stage 3 (`/search/v3`)**: Hybrid lexical + semantic search using `pgvector`, Gemini embeddings, and Reciprocal Rank Fusion (RRF).
- **Stage 2.2 prep (`/search/v2.2`, planned)**: Elastic-backed successor to `v2` with a frozen parity contract, versioned index mapping, async client plumbing, and CDC connector templates checked into the repo.
- async PostgreSQL access with SQLAlchemy 2.x and asyncpg.
- parallel read-only database model (`ProductMaster`).
- restored database table (`product_master`) containing realistic enterprise IT assets (printers, laptops, monitors).
- evaluation harness with 12 top-3 relevance cases supporting engine selection (`--engine v1`, `--engine v2`, or `--engine v3`).
- integration testing suite for regression protection.

## How Search Works

Request flow:

1. Validate incoming query params
2. Fetch candidate rows from PostgreSQL with optional prefilters
3. Convert each row to a plain dict
4. Score each candidate in Python using `score_product`
5. Filter out low scores
6. Sort by `total_score DESC`
7. Return top `N`

This is intentionally simple and easy to transplant into another codebase.

## Ranking Signals

The current scorer is additive and deterministic.

Signals include:

- exact name match
- name starts with query
- whole-word name match
- name contains query
- exact brand match
- brand contains query
- exact category match
- category contains query
- type contains query
- sub_category contains query
- model_number contains query
- certification exact match
- hazardous material contains query
- boost for high repairability (`repairability_score >= 0.75`)

The score breakdown is returned in the API response so callers can see why each result ranked where it did.

## Tech Stack

- Python 3.11+
- FastAPI
- PostgreSQL 15+
- Docker Desktop
- SQLAlchemy 2.x async + `asyncpg`
- Alembic
- Pydantic v2
- pytest
- httpx
- `pgvector`
- `google-genai`
- `elasticsearch-py`

## Project Layout

```text
psql-ranking-poc/
├── app/
│   ├── __init__.py
│   ├── database.py          # settings, async engine, session factory
│   ├── embedding_client.py  # Gemini Embedding 2 wrapper
│   ├── main.py              # FastAPI app + router registration
│   ├── models.py            # Product and ProductMaster ORM models
│   ├── rrf.py               # Reciprocal Rank Fusion
│   ├── schemas.py           # Pydantic request/response models
│   ├── scorer.py            # deterministic application-layer scorer (v1)
│   ├── search_engine_v2.py  # PostgreSQL full-text + ILIKE wildcard (v2)
│   ├── search_engine_v3.py  # hybrid lexical + semantic orchestration (v3)
│   └── routers/
│       ├── search.py        # GET /search  (v1)
│       ├── search_v2.py     # GET /search/v2
│       └── search_v3.py     # GET /search/v3
├── migrations/              # Alembic migration history
├── scripts/
│   ├── bootstrap_product_master.sql  # base schema + enum types for fresh DBs
│   ├── embed_products.py    # batch embedding pipeline for product_master
│   ├── eval.py              # relevance eval harness (v1 / v2 / v3)
│   ├── migrate_postgres.sql # SQL: pg_trgm, vector, search_vector, embedding, all indexes
│   ├── migrate_postgres_cdc.sql # SQL: replica identity & publication setup for CDC
│   ├── run_migrate_postgres.py # Python: execute migrate_postgres.sql
│   ├── run_migrate_postgres_cdc.py # Python: execute migrate_postgres.sql
│   └── seed.py              # legacy seed for the older `products` table
├── tests/
│   ├── test_rrf.py
│   ├── test_scorer.py
│   └── test_search_v2.py
├── context.md
├── docker-compose.yml
├── test_cases.json
├── requirements.txt
└── README.md
```

## Quick Start

### 1. Install dependencies

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Configure environment

Copy `.env.example` to `.env`:

```powershell
Copy-Item .env.example .env
```

The `.env` file controls all environment settings:

```env
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5433/psql_ranking_poc
APP_ENV=development
LOG_LEVEL=INFO
GOOGLE_AI_API_KEY=your-gemini-api-key-here
ELASTIC_CLOUD_ID=your-elastic-cloud-id-here
ELASTIC_URL=https://your-deployment.es.us-central1.gcp.cloud.es.io:443
ELASTIC_API_KEY=your-elastic-api-key-here
ELASTIC_USERNAME=
ELASTIC_PASSWORD=
ELASTIC_V2_INDEX_READ_ALIAS=product_master_v2_read
ELASTIC_V2_INDEX_WRITE_ALIAS=product_master_v2_write
ELASTIC_V2_INDEX_NAME=product_master_v2_0001
ELASTIC_V2_TIMEOUT_SECONDS=10
```

> `GOOGLE_AI_API_KEY` is only required for Stage 3 embeddings and `/search/v3`. Leave it blank to run v1 and v2.
>
> The Elastic settings are preparatory for the planned `/search/v2.2` endpoint. They are not required for the current PostgreSQL-backed `/search/v2`.

### 3. Start PostgreSQL with pgvector

This repo ships a Docker Compose service using `pgvector/pgvector:pg17`, exposed on host port `5433`.

```powershell
docker compose up -d postgres
```

Wait for the healthcheck to pass before running any migrations or the API.

### 4. Bootstrap `product_master`

All three search endpoints query `product_master`, not the older `products` table.

**Step 4a — Create the base schema** (idempotent; safe to re-run):

```powershell
$env:PGPASSWORD='password'
& 'C:\Program Files\PostgreSQL\18\bin\psql.exe' `
  -h localhost -p 5433 -U postgres -d psql_ranking_poc `
  -v ON_ERROR_STOP=1 -f scripts\bootstrap_product_master.sql
```

**Step 4b — Load product data** (if you have the restored native PostgreSQL on port 5432):

```powershell
$env:PGPASSWORD='password'
& 'C:\Program Files\PostgreSQL\18\bin\pg_dump.exe' `
  -h localhost -p 5432 -U postgres -d psql_ranking_poc `
  -a -t public.product_master -f "$env:TEMP\product_master_data.sql"

& 'C:\Program Files\PostgreSQL\18\bin\psql.exe' `
  -h localhost -p 5433 -U postgres -d psql_ranking_poc `
  -v ON_ERROR_STOP=1 -f "$env:TEMP\product_master_data.sql"
```

If you see a duplicate key error on import, the data is already present — this is safe to ignore.

### 5. Apply Phase 2, Phase 2v2, and Phase 3 migrations

These are idempotent — safe to re-run against a database that already has the changes.

```powershell
# Apply final consolidated database migration (FTS + Trigrams + Vector Embeddings)
.\.venv\Scripts\python.exe -m scripts.run_migrate_postgres

# Apply logical replication (CDC) preparation migration
.\.venv\Scripts\python.exe -m scripts.run_migrate_postgres_cdc
```

### 6. (Stage 3 only) Build embeddings

Only required for `/search/v3` semantic results. Requires `GOOGLE_AI_API_KEY` set in `.env`.

```powershell
.\.venv\Scripts\python.exe scripts\embed_products.py
```

This is a one-time batch job. Re-run it whenever new rows are added with `embedding IS NULL`.

### 7. Start the API

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 8. Try the endpoints

**Health check:**

```powershell
curl http://127.0.0.1:8000/health
```

Expected: `{"status":"ok"}`

**Stage 1 — Python scorer:**

```powershell
curl "http://127.0.0.1:8000/search?q=HP%20Laptop%2015-dw%20Series&top_n=3"
```

**Stage 2 — PostgreSQL FTS + ILIKE fallback:**

```powershell
curl "http://127.0.0.1:8000/search/v2?q=HP%20Laptop%2015-dw%20Series&top_n=3"
```

**Stage 3 — Hybrid lexical + semantic (requires embeddings):**

```powershell
curl "http://127.0.0.1:8000/search/v3?q=HP%20Laptop%2015-dw%20Series&top_n=3"
```

## Setup Notes

- `docker-compose.yml` uses `pgvector/pgvector:pg17` and publishes the database on host port `5433`.
- `.env` must point to `localhost:5433` (not 5432) for the Dockerized database.
- `scripts/bootstrap_product_master.sql` creates the base `product_master` schema, sequence, enum types, and indexes. It is idempotent and safe to re-run.
- `scripts/seed.py` populates the older `products` table only — the active API endpoints do **not** use `products`.
- `scripts/migrate_postgres.sql` is the final consolidated database migration which sets up FTS vector weights, GIN trigram indexes, and pgvector embeddings.
- `scripts/migrate_postgres_cdc.sql` is the CDC prep migration which configures table replica identity and replication publications.
- The HNSW index is sparse until `scripts/embed_products.py` runs — `/search/v3` will return only lexical results until embeddings are populated.
- The repo now includes the first `v2.2` Elastic artifacts:
  - `docs/search-v2-contract.md` freezes `v2` behavior so `v2.2` can match it.
  - `docs/search-v2-elastic-document.md` defines the target Elastic document model.
  - `scripts/es/product_master_v2_mapping.json` defines the versioned index mapping and aliases.
  - `scripts/create_es_index_v2.py` creates `product_master_v2_0001` and the `product_master_v2_read` / `product_master_v2_write` aliases.
  - `scripts/check_elastic_connection.py` verifies Elastic connectivity from the repo.
  - `infra/cdc/debezium-product-master-v2.json` and `infra/cdc/es-sink-product-master-v2.json` are starter connector configs for the future CDC pipeline.
- `/search/v2.2` does not exist yet; the current API remains PostgreSQL-backed for `v2`.

## API Contract

### `GET /health`

Returns:

```json
{"status":"ok"}
```

### `GET /search`

Query params:

- `q` required search query
- `top_n` optional, default `10`, max `100`
- `min_score` optional, default `1`
- `category` optional category prefilter

```text
GET /search?q=HP+DesignJet+Z9%2B+Pro+64-in+Printer&top_n=3
```

Response shape:

```json
{
  "query": "HP DesignJet Z9+ Pro 64-in Printer",
  "total_candidates": 15,
  "results_returned": 1,
  "results": [
    {
      "uuid": "2f61910e-6656-4bb0-8995-ad10a2d17b25",
      "status": "ACTIVE",
      "type": "Large-format Printer",
      "name": "HP DesignJet Z9+ Pro 64-in Printer",
      "category": "Electronics",
      "sub_category": "Printers & Imaging Equipment",
      "brand": "HP",
      "manufacturer": {
        "name": "HP Inc.",
        "support_url": "https://support.hp.com"
      },
      "upc": "196068222851",
      "variant": "Standard",
      "model_number": "Z9+",
      "serial_number": "MXL9876543",
      "model_year": 2023,
      "weight_lb": 120.0,
      "weight_kg": 54.4,
      "dimensions_inches": "64.0 x 28.0 x 48.0",
      "repairability_score": 8.5,
      "disassembly_complexity": "MEDIUM",
      "average_life_span_years": 8,
      "energy_efficiency_rating": "Energy Star",
      "authorized_needed": false,
      "special_handling_required": false,
      "contains_user_data": true,
      "mandatory_data_wipe_needed": true,
      "required_certifications": ["Energy Star", "EPEAT Gold"],
      "market_value": {
        "currency": "USD",
        "current_market_value": 4999.0
      },
      "market_value_avgs": {
        "avg_refurbished_price": 3999.0
      },
      "hazardous_materials": [],
      "created_at": "2026-06-10T11:23:21Z",
      "updated_at": "2026-06-10T11:23:21Z",
      "goods_type": "SMALL_WHITE_GOODS",
      "total_score": 118,
      "score_breakdown": {
        "exact_name_match": 100,
        "name_starts_with_query": 80,
        "name_whole_word_match": 60,
        "name_contains_query": 40,
        "exact_brand_match": 50,
        "brand_contains_query": 25,
        "exact_category_match": 30,
        "category_contains_query": 15,
        "boost_high_repairability": 8
      }
    }
  ]
}
```

Note:

- `score_breakdown` only includes non-zero signals for v1
- database failures are intentionally not swallowed
- empty queries are rejected with HTTP `422`

### `GET /search/v2`

Query params:

- `q` required search query
- `top_n` optional, default `10`, max `100`
- `category` optional category prefilter
- `fallback_enabled` optional, default `true` (whether to fall back to ILIKE if FTS matches nothing)

```text
GET /search/v2?q=HP+Laptop&top_n=3
```

Response shape:

```json
{
  "query": "HP Laptop",
  "search_mode": "fulltext",
  "results_returned": 3,
  "results": [
    {
      "uuid": "86e72716-2151-47d7-91e9-d0fe73988790",
      "status": "ACTIVE",
      "type": "Laptop",
      "name": "HP Laptop 15-dw Series",
      "category": "Electronics",
      "sub_category": "Laptops & Notebooks",
      "brand": "HP",
      "manufacturer": {
        "name": "HP Inc.",
        "support_url": "https://support.hp.com"
      },
      "upc": "196068222851",
      "variant": "Standard",
      "model_number": "15-dw",
      "serial_number": "MXL9876543",
      "model_year": 2023,
      "weight_lb": 3.75,
      "weight_kg": 1.7,
      "dimensions_inches": "14.1 x 9.5 x 0.78",
      "repairability_score": 7.2,
      "disassembly_complexity": "MEDIUM",
      "average_life_span_years": 5,
      "energy_efficiency_rating": "Energy Star",
      "authorized_needed": false,
      "special_handling_required": false,
      "contains_user_data": true,
      "mandatory_data_wipe_needed": true,
      "required_certifications": ["Energy Star"],
      "market_value": {
        "currency": "USD",
        "current_market_value": 499.0
      },
      "market_value_avgs": {
        "avg_refurbished_price": 349.0
      },
      "hazardous_materials": ["Lithium-ion Battery"],
      "created_at": "2026-06-10T11:23:21Z",
      "updated_at": "2026-06-10T11:23:21Z",
      "goods_type": "SMALL_WHITE_GOODS",
      "search_score": 1.45,
      "search_mode": "fulltext"
    }
  ]
}
```


## Validation

### Unit tests

Run all tests (no running API or database required for scorer/rrf tests):

```powershell
.\.venv\Scripts\pytest
```

Or run individual suites:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_scorer.py
.\.venv\Scripts\python.exe -m pytest tests\test_rrf.py
.\.venv\Scripts\python.exe -m pytest tests\test_search_v2.py
```

### Relevance eval

The API must be running before running the eval harness.

```powershell
# Stage 1 — Python scorer
.\.venv\Scripts\python.exe scripts\eval.py --engine v1

# Stage 2 — PostgreSQL FTS + ILIKE wildcard
.\.venv\Scripts\python.exe scripts\eval.py --engine v2

# Stage 3 — Hybrid lexical + semantic (requires embeddings)
.\.venv\Scripts\python.exe scripts\eval.py --engine v3
```

What the eval does:

- loads `test_cases.json`
- issues live requests to `/search` (v1), `/search/v2` (v2), or `/search/v3` (v3) with `top_n=3`
- checks whether expected product IDs appear in the returned top 3
- prints `PASS` or `FAIL` per case
- for v3, prints hybrid match details such as `matched_in`
- exits non-zero if accuracy is below `90%`

Current verified result:

- `12/12` cases passed on v1 and v2 (100% accuracy)

- `100.0%` top-3 accuracy against the restored product_master benchmark

### Elastic prep checks

Once Elastic credentials are configured in `.env`, you can verify connectivity and create the first versioned index:

```powershell
.\.venv\Scripts\python.exe scripts\check_elastic_connection.py
.\.venv\Scripts\python.exe scripts\create_es_index_v2.py
```

These commands are preparatory for the planned `GET /search/v2.2` endpoint and do not change the current `/search/v2` behavior.

Important interpretation:

- this is a **controlled POC benchmark**
- it proves the scorer behaves well on the defined seeded dataset
- it does **not** by itself prove 90% real-world user relevance in production

## Using This In Another Application

This repo is intentionally easy to lift into a different backend.

### Option 1: Use it as a standalone search service

Best when:

- your main app is in another language
- you want to ship quickly
- you want ranking logic isolated behind HTTP

How:

- run this service separately
- load or sync your own catalog into `product_master`
- call `/search`, `/search/v2`, or `/search/v3` from your main application

### Option 2: Embed the ranking flow into an existing FastAPI app

Best when:

- you already use Python/FastAPI
- you want shared auth, observability, and deployment

How:

- copy or adapt `app/scorer.py`
- reuse the `Product` model or map it to your own table
- move `app/routers/search.py` into your existing router structure
- plug in your own `AsyncSession` dependency

### Option 3: Reuse only the scoring logic

Best when:

- your app already has a SQL query layer
- you only need the ranking piece

How:

1. fetch a candidate set from your own database
2. normalize each row into a dict with the expected fields
3. call `score_product(product_dict, query)`
4. sort by returned score
5. return the top results with optional breakdowns

The scorer expects fields equivalent to:

- `uuid`
- `status` (pre-filtered to ACTIVE in SQL)
- `type`
- `name`
- `category`
- `sub_category`
- `brand`
- `required_certifications`
- `hazardous_materials`
- `repairability_score`

### Integration Checklist

- keep PostgreSQL as the candidate source
- preserve stable product identifiers (`uuid`) and searchable product metadata
- make sure `product_master` contains the fields used by the current scorer and SQL search paths
- return `score_breakdown` if you want explainability
- keep eval-style test cases for regression checks when tuning weights

## Adapting the Data Model

If your application is not a product catalog, you can still use the same pattern.

Examples:

- jobs: title, company, category, skills, description
- courses: name, provider, topic, tags, summary
- documents: title, owner, collection, tags, body
- vendors: name, brand family, segment, tags, notes

The core idea is the same:

- store structured rows in PostgreSQL
- fetch a candidate set
- rank in Python with transparent signal weights

## Design Decisions

Why application-layer scoring first:

- fastest to reason about
- easiest to debug
- zero ambiguity around how scores are computed
- ideal baseline before moving logic into SQL

Why PostgreSQL still matters here:

- durable storage
- structured filtering
- future-ready indexing for later stages

Why fixed seed IDs and eval cases:

- reproducible benchmark
- easy demo for other developers and managers
- safe regression target when refactoring or tuning scores

## Known Limitations

- v1 fetches all filtered candidates into the application layer before scoring (no SQL-level ranking)
- `scripts/seed.py` targets the legacy `products` table; the active search endpoints use `product_master`
- `product_master` cannot yet be seeded from a repo-native source — data must be imported from an existing database or an external source
- Stage 3 (`/search/v3`) requires `GOOGLE_AI_API_KEY` and a completed `embed_products.py` run before semantic results appear
- The embedding pipeline is a manual batch job with no automatic re-embedding trigger when product fields change
- No explicit secondary tie-breaker in v1 beyond descending `total_score`
- v3 RRF fusion may rerank results differently from v2 — this is expected and reflects the semantic component

These are acceptable POC tradeoffs and well-understood follow-up opportunities.

## Recommended Next Step

If you want to evolve this into a more production-like ranking system, the next milestone is:

- complete Elastic Cloud + CDC provisioning for the planned `/search/v2.2` path
- implement `/search/v2.2` against the versioned Elastic index while keeping `/search/v2` unchanged
- add side-by-side parity tests comparing `/search/v2` and `/search/v2.2`

## Developer Notes

- [context.md](./context.md) contains the living project context and implementation nuances
- [docs/elastic-v2-2-migration-plan.md](./docs/elastic-v2-2-migration-plan.md) tracks the two-deliverable Elastic migration plan
- [docs/search-v2-contract.md](./docs/search-v2-contract.md) freezes the current `v2` behavior for parity work
- [scripts/seed.py](./scripts/seed.py) is the quickest way to understand the seeded catalog and benchmark assumptions
- [app/scorer.py](./app/scorer.py) is the most important file if you want to port the ranking behavior elsewhere
