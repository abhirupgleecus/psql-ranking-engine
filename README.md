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
- **Stage 2 (`/search/v2`)**: Native PostgreSQL-scored full-text search (using a stored generated `tsvector` column and `ts_rank_cd`) with an automatic `ILIKE` wildcard search fallback.
- async PostgreSQL access with SQLAlchemy 2.x and asyncpg.
- parallel read-only database model (`ProductMaster`).
- restored database table (`product_master`) containing realistic enterprise IT assets (printers, laptops, monitors).
- evaluation harness with 12 top-3 relevance cases supporting engine selection (`--engine v1` or `--engine v2`).
- integration testing suite for regression protection.

Planned later:

- Stage 3: Fuzzy search with trigram matching (`pg_trgm`) and semantic search with embeddings (`pgvector`).

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
- SQLAlchemy 2.x async + `asyncpg`
- Alembic
- Pydantic v2
- pytest
- httpx

## Project Layout

```text
psql-ranking-poc/
├── app/
│   ├── database.py
│   ├── main.py
│   ├── models.py
│   ├── scorer.py
│   ├── search_engine_v2.py
│   ├── schemas.py
│   └── routers/
│       ├── search.py
│       └── search_v2.py
├── migrations/
├── scripts/
│   ├── eval.py
│   ├── migrate_phase2.sql
│   ├── run_migrate_phase2.py
│   └── seed.py
├── tests/
│   ├── test_scorer.py
│   └── test_search_v2.py
├── context.md
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

Copy `.env.example` to `.env` and set your PostgreSQL connection string.

Example:

```env
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/psql_ranking_poc
APP_ENV=development
LOG_LEVEL=INFO
```

### 3. Apply migrations

Run the standard Alembic migration first:
```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
```

Then run the Phase 2 Full-Text Search migration:
```powershell
.\.venv\Scripts\python.exe -m scripts.run_migrate_phase2
```

### 4. Seed sample data

```powershell
.\.venv\Scripts\python.exe scripts\seed.py
```

The seed script is idempotent. Running it twice will not create duplicates.

### 5. Start the API

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 6. Try the API

Health check:

```powershell
curl http://127.0.0.1:8000/health
```

Search v1 (Python Scorer):

```powershell
curl "http://127.0.0.1:8000/search?q=wireless%20headphones&top_n=3"
```

Search v2 (PostgreSQL Native Full-Text + Wildcard):

```powershell
curl "http://127.0.0.1:8000/search/v2?q=wireless%20headphones&top_n=3"
```

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

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_scorer.py
```

### Relevance eval

Run the API, then:

```powershell
# Evaluate Stage 1 (Python Scorer)
.\.venv\Scripts\python.exe scripts\eval.py --engine v1

# Evaluate Stage 2 (PostgreSQL Native Full-Text + Wildcard)
.\.venv\Scripts\python.exe scripts\eval.py --engine v2
```

What the eval does:

- loads `test_cases.json`
- issues live requests to `/search` (v1) or `/search/v2` (v2) with `top_n=3`
- checks whether expected product IDs appear in the returned top 3
- prints `PASS` or `FAIL` per case
- exits non-zero if accuracy is below `90%`

Current verified result:

- `12/12` cases passed on both engines (100% accuracy)

- `100.0%` top-3 accuracy against the restored product_master benchmark

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
- seed or sync your own catalog into the `products` table
- call `/search` from your main application

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
- preserve the `(name, brand)` uniqueness rule if you want idempotent upserts
- keep tags as an array if you want the same tag-matching behavior
- make sure rating and review count are available for boost signals
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

- all filtered candidates are fetched into the app before scoring
- no SQL-native ranking yet
- no semantic search yet
- no explicit secondary tie-breaker beyond descending score
- exact-match queries can still have unrelated but highly boosted items in ranks 2-3

These are acceptable tradeoffs for a Stage 1 POC and are useful teaching points for the next evolution of the system.

## Recommended Next Step

If you want to evolve this into a more production-like ranking system, the next milestone is:

- move lexical scoring into PostgreSQL
- add `tsvector` / `tsquery`
- add `pg_trgm`
- compare Stage 2 results against the current eval harness

## Developer Notes

- [context.md](./context.md) contains the living project context and implementation nuances
- [scripts/seed.py](./scripts/seed.py) is the quickest way to understand the seeded catalog and benchmark assumptions
- [app/scorer.py](./app/scorer.py) is the most important file if you want to port the ranking behavior elsewhere
