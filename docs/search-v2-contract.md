# Frozen Contract for `GET /search/v2`

## Purpose

This document defines the current behavior of `GET /search/v2` and the parity
requirements for the new `GET /search/v2.2` endpoint.

`/search/v2.2` must behave exactly like `/search/v2` from a caller's point of
view. The backend implementation may change, but the request and response
contract must not.

---

## Current Source of Truth

The current contract is defined by:

- `app/routers/search_v2.py`
- `app/search_engine_v2.py`
- `app/schemas.py`

---

## Endpoint

- Method: `GET`
- Path: `/search/v2`

Parity target:

- Method: `GET`
- Path: `/search/v2.2`

---

## Query Parameters

### `q`

- required
- type: string
- min length: 1 at validation layer
- server trims whitespace before use
- whitespace-only values are rejected with HTTP `422`

Examples:

- valid: `HP Laptop`
- valid: `  HP Laptop  `
- invalid: `   `

### `top_n`

- optional
- type: integer
- default: `10`
- minimum: `1`
- maximum: `100`

### `category`

- optional
- type: string or null
- trimmed before use
- if empty after trimming, treated as `None`
- when present, used as an exact equality filter

### `fallback_enabled`

- optional
- type: boolean
- default: `true`
- controls whether fallback search runs if primary search returns zero results

---

## Validation Behavior

### Validations enforced

1. `q` must be provided
2. `q.strip()` must not be empty
3. `top_n` must be between `1` and `100`
4. `category` is optional and normalized to `None` when blank

### Error behavior

- whitespace-only `q` returns HTTP `422`
- invalid `top_n` returns HTTP `422`
- database/search backend errors are not intentionally swallowed

Parity requirement for `/search/v2.2`:

- identical validation semantics
- identical HTTP `422` behavior for invalid inputs

---

## Filtering Behavior

The endpoint only returns rows/documents that satisfy:

1. `status = ACTIVE`
2. `category = :category` when `category` is provided

Important parity notes:

- `category` filtering is exact, not fuzzy
- inactive rows must not appear
- category filtering applies to both primary and fallback search

---

## Search Modes

The current endpoint exposes two user-visible search modes:

### `fulltext`

Returned when the primary search path finds one or more results.

Current PostgreSQL implementation uses:

- `search_vector @@ to_tsquery(...)`
- `model_number ILIKE :wildcard`
- `upc ILIKE :wildcard`
- ranking blend using:
  - `ts_rank_cd(...)`
  - `similarity(model_number, :raw_query) * 2.0`
  - `similarity(upc, :raw_query) * 2.0`

### `wildcard`

Returned only when:

1. primary search returned zero rows
2. `fallback_enabled = true`

Current PostgreSQL fallback searches with `ILIKE` across:

- `name`
- `brand`
- `category`
- `sub_category`
- `type`
- `model_number`
- `upc`
- `required_certifications`
- `hazardous_materials`

Parity requirement for `/search/v2.2`:

- preserve the same two `search_mode` values
- preserve the same fallback triggering behavior

---

## Response Shape

Top-level response fields:

- `query: str`
- `search_mode: str`
- `results_returned: int`
- `results: list[RankedProductMasterV2]`

Each result currently contains:

- `uuid`
- `status`
- `type`
- `name`
- `category`
- `sub_category`
- `brand`
- `manufacturer`
- `upc`
- `variant`
- `model_number`
- `serial_number`
- `model_year`
- `weight_lb`
- `weight_kg`
- `dimensions_inches`
- `repairability_score`
- `disassembly_complexity`
- `average_life_span_years`
- `energy_efficiency_rating`
- `authorized_needed`
- `special_handling_required`
- `contains_user_data`
- `mandatory_data_wipe_needed`
- `required_certifications`
- `market_value`
- `market_value_avgs`
- `hazardous_materials`
- `additional_data`
- `created_at`
- `updated_at`
- `goods_type`
- `master_uuid`
- `gtin`
- `ean`
- `search_score`
- `search_mode`

Parity requirement for `/search/v2.2`:

- same top-level response fields
- same per-result fields
- same field types as serialized today
- same array normalization behavior for:
  - `required_certifications`
  - `hazardous_materials`

---

## Ranking Expectations

This document freezes observable behavior, not exact internal scoring math.

That means `/search/v2.2` must preserve:

1. exact and substring retrieval for `model_number`
2. exact and substring retrieval for `upc`
3. strong relevance for brand/name/category style lexical matches
4. exact category prefiltering
5. fallback behavior when primary lexical retrieval returns zero hits
6. stable top-N semantics

This document does not require:

- identical numeric scores to PostgreSQL

This document does require:

- comparable ordering quality for benchmark queries
- preservation of `search_mode`
- preservation of result field contents and shapes

---

## Behavioral Examples to Preserve

### Example 1: blank query

Input:

- `q=   `

Expected:

- HTTP `422`

### Example 2: category-filtered search

Input:

- `q=HP`
- `category=Electronics`

Expected:

- HTTP `200`
- every result has `category == "Electronics"`

### Example 3: no fallback when disabled

Input:

- `q=xyzrandomgibberish123`
- `fallback_enabled=false`

Expected:

- HTTP `200`
- `results` is empty
- `search_mode == "fulltext"`

### Example 4: model number substring

Input:

- query matches a mid-string `model_number` fragment

Expected:

- the correct product is retrievable
- search behaves as primary search, not only broad fallback

### Example 5: UPC exact and substring search

Input:

- exact `upc`
- partial `upc`

Expected:

- exact UPC queries strongly retrieve the matching product
- substring UPC queries still retrieve matching products

---

## Non-Negotiable Requirements for `v2.2`

1. `/search/v2` remains untouched during implementation
2. `/search/v2.2` reuses the same request and response models unless a strong
   reason is documented
3. `/search/v2.2` returns `search_mode` values compatible with `v2`
4. `/search/v2.2` preserves `ACTIVE`-only filtering
5. `/search/v2.2` preserves exact category filtering
6. `/search/v2.2` preserves fallback semantics
7. `/search/v2.2` preserves result field shape and normalization behavior

---

## Validation Strategy

`/search/v2.2` will be considered parity-ready only after it passes:

1. request/response contract tests
2. current `v2`-style endpoint tests adapted for `v2.2`
3. side-by-side comparisons against `/search/v2`
4. `test_cases.json` benchmark comparisons

---

## Future Updates

If the current `/search/v2` behavior changes, this document must be updated
before `v2.2` parity work continues. This file is intended to prevent silent
behavior drift while the backend implementation changes.
