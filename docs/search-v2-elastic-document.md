# Elasticsearch Document Model for `GET /search/v2.2`

## Purpose

This document defines the Elasticsearch document shape for the new
`GET /search/v2.2` endpoint.

The document model is designed to satisfy two goals:

1. preserve the current `/search/v2` response contract
2. support `v2`-equivalent lexical ranking and fallback behavior in Elastic

Each document represents one row from `product_master`.

---

## Source Table

- PostgreSQL table: `public.product_master`
- One row maps to one Elasticsearch document
- Elasticsearch document `_id` should be the row `uuid`

---

## Indexing Strategy

The Elasticsearch index should be treated as a read model derived from
PostgreSQL through CDC.

Rules:

1. PostgreSQL remains the source of truth
2. Elasticsearch stores a search-optimized projection of the row
3. every field needed by `/search/v2.2` should be present in `_source`
4. fields may have additional indexed subfields to support exact, analyzed, and
   substring-style matching

---

## Required Top-Level Document Fields

These fields should exist in `_source` so `v2.2` can return the same result
shape as `v2`.

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

`search_score` and per-result `search_mode` are not stored fields. They are
derived at query time.

---

## Field Classes

### 1. Exact filter fields

These support filtering and exact equality semantics.

- `uuid`
- `status`
- `category`
- `goods_type`

Why:

- `status` must enforce `ACTIVE`-only behavior
- `category` must support exact prefiltering

### 2. High-importance exact and substring fields

These drive the most important ID-style retrieval behavior.

- `model_number`
- `upc`

Why:

- current `v2` strongly favors exact and substring retrieval on both fields
- both need exact matching and partial matching support

### 3. Primary lexical relevance fields

These fields support the main user-facing lexical ranking behavior.

- `brand`
- `name`
- `category`
- `sub_category`
- `type`

Why:

- they correspond to the current `v2` full-text and fallback search surface

### 4. Secondary lexical fields

- `required_certifications`
- `hazardous_materials`

Why:

- current `v2` includes them in fallback behavior
- they should be searchable but lower-weight than core product identity fields

### 5. Response-only or low-search-value fields

These are primarily returned to clients rather than used for ranking.

- `manufacturer`
- `variant`
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
- `market_value`
- `market_value_avgs`
- `additional_data`
- `created_at`
- `updated_at`
- `master_uuid`
- `gtin`
- `ean`

---

## Query-Time Behavior Requirements

The document model must support these observable `v2.2` behaviors:

1. exact filtering on `status = ACTIVE`
2. exact filtering on `category`
3. strong exact retrieval on `model_number`
4. strong exact retrieval on `upc`
5. substring retrieval on `model_number`
6. substring retrieval on `upc`
7. lexical relevance across:
   - `brand`
   - `name`
   - `category`
   - `sub_category`
   - `type`
8. lower-priority lexical matching on:
   - `required_certifications`
   - `hazardous_materials`
9. result reconstruction using `_source` alone

---

## Normalization Requirements

To preserve `v2` response compatibility:

1. `required_certifications` must serialize as an array
2. `hazardous_materials` must serialize as an array
3. nullable fields must remain nullable in `_source`
4. `status`, `disassembly_complexity`, and `goods_type` should remain
   compatible with current string-based API serialization

---

## Recommended Query-Oriented Multi-Field Strategy

### `model_number`

Recommended indexed forms:

1. exact form for exact match boosting
2. normalized text form for lexical matching
3. substring form for mid-string matching

### `upc`

Recommended indexed forms:

1. exact form for exact match boosting
2. substring form for partial UPC retrieval

### Text fields

Recommended indexed forms:

1. analyzed `text` form for lexical ranking
2. `.keyword` exact form where deterministic sorting/filtering helps

---

## Example Document Shape

```json
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
  "additional_data": null,
  "created_at": "2026-06-10T11:23:21Z",
  "updated_at": "2026-06-10T11:23:21Z",
  "goods_type": "SMALL_WHITE_GOODS",
  "master_uuid": null,
  "gtin": null,
  "ean": null
}
```

---

## Non-Negotiable Constraints

1. The document must be sufficient to build the full `RankedProductMasterV2`
   response shape
2. The document must support both primary and fallback search behavior
3. The document must keep `model_number` and `upc` first-class search fields
4. The document must not depend on PostgreSQL at query time once indexed
