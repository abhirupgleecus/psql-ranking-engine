# PostgreSQL Ranking POC

A small, practical reference implementation for **application-layer relevance ranking on top of PostgreSQL**.

This repo shows how to:

- store a product catalog in PostgreSQL
- fetch search candidates with async SQLAlchemy
- apply deterministic ranking logic in Python
- expose ranked results through a FastAPI endpoint
- validate relevance quality with a repeatable eval harness

It is designed as a **Stage 1 ranking system** that other developers can understand quickly and either:

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

- FastAPI service with `/health` and `/search`
- async PostgreSQL access with SQLAlchemy 2.x
- Alembic migrations
- deterministic rule-based scorer
- seed dataset with 50 realistic products
- evaluation harness with 24 top-3 relevance cases

Planned later:

- Stage 2: PostgreSQL full-text search with `tsvector`, `tsquery`, and `pg_trgm`
- Stage 3: semantic search with embeddings and `pgvector`

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
- exact tag match
- tag contains query
- description contains query
- boost for high rating
- boost for high review count
- boost for in-stock items
- penalty for out-of-stock items

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
│   ├── schemas.py
│   └── routers/
│       └── search.py
├── migrations/
├── scripts/
│   ├── eval.py
│   └── seed.py
├── tests/
│   └── test_scorer.py
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

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
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

Search:

```powershell
curl "http://127.0.0.1:8000/search?q=wireless%20headphones&top_n=3"
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
- `in_stock_only` optional boolean prefilter

Example:

```text
GET /search?q=blender&top_n=3&in_stock_only=true
```

Response shape:

```json
{
  "query": "blender",
  "total_candidates": 50,
  "results_returned": 3,
  "results": [
    {
      "id": "00000000-0000-0000-0000-000000000031",
      "name": "Ninja Professional Plus Blender",
      "brand": "Ninja",
      "category": "kitchen",
      "tags": ["blender", "smoothie", "countertop", "ice crushing"],
      "description": "Powerful blender that handles frozen fruit, soups, and quick weekday smoothies.",
      "price": 119.99,
      "rating": 4.70,
      "review_count": 410,
      "in_stock": true,
      "created_at": "2026-06-08T00:00:00Z",
      "total_score": 86,
      "score_breakdown": {
        "name_whole_word_match": 60,
        "name_contains_query": 40,
        "tag_exact_match": 20,
        "tag_contains_query": 10,
        "boost_high_rating": 8,
        "boost_high_review_count": 5,
        "boost_in_stock": 3
      }
    }
  ]
}
```

Note:

- `score_breakdown` only includes non-zero signals
- database failures are intentionally not swallowed
- empty queries are rejected with HTTP `422`

## Validation

### Unit tests

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_scorer.py
```

### Relevance eval

Run the API, then:

```powershell
.\.venv\Scripts\python.exe scripts\eval.py --base-url http://127.0.0.1:8000
```

What the eval does:

- loads `test_cases.json`
- issues live `GET /search?q=...&top_n=3` requests
- checks whether expected product IDs appear in the returned top 3
- prints `PASS` or `FAIL` per case
- exits non-zero if accuracy is below `90%`

Current verified result:

- `24/24` cases passed
- `100.0%` top-3 accuracy against the seeded benchmark

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

- `name`
- `brand`
- `category`
- `tags`
- `description`
- `rating`
- `review_count`
- `in_stock`

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
