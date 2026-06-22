# ElasticCloud Migration Plan for `v2.2`

## Goal

Add a new endpoint, `GET /search/v2.2`, that behaves exactly like the current
`GET /search/v2` endpoint in:

- input parameters
- validation behavior
- response shape
- `search_mode` semantics
- `ACTIVE` filtering behavior
- exact `category` filtering behavior
- fallback behavior when primary search returns zero hits

The only intended difference is backend implementation:

- `/search/v2` stays PostgreSQL-backed
- `/search/v2.2` becomes Elastic-backed

This work is split into two deliverables:

1. Deliverable A: build and validate the Elastic + CDC pipeline without changing
   live `v2`
2. Deliverable B: implement `v2.2`, tune for parity, and make it available for
   consumers

---

## Deliverable A

Build the ElasticCloud infrastructure, CDC pipeline, mappings, and validation
workflow before the application starts serving Elastic-backed traffic.

### Phase 1: Freeze the Current `v2` Contract

#### Objective

Create an exact parity target for `v2.2`.

#### Tasks

1. Read the current behavior in:
   - `app/routers/search_v2.py`
   - `app/search_engine_v2.py`
   - `app/schemas.py`
2. Capture the exact query params:
   - `q`
   - `top_n`
   - `category`
   - `fallback_enabled`
3. Capture the exact validation rules:
   - blank or whitespace-only `q` returns `422`
   - `top_n` range remains `1..100`
   - `category` is trimmed and converted to `None` if empty
4. Capture the exact response fields:
   - top-level `query`
   - top-level `search_mode`
   - top-level `results_returned`
   - top-level `results`
   - every field in `RankedProductMasterV2`
5. Capture the exact filtering behavior:
   - only `status = ACTIVE`
   - `category` is exact equality if provided
6. Capture the exact ranking behavior:
   - primary mode returns `search_mode = "fulltext"`
   - fallback returns `search_mode = "wildcard"`
   - fallback executes only when primary returns zero results and
     `fallback_enabled = true`
7. Write the frozen contract in `docs/search-v2-contract.md`

#### Acceptance Criteria

- The parity target for `v2.2` is documented and reviewable in one place
- No application code changes are required to understand expected `v2.2`
  behavior

### Phase 2: Define the Elasticsearch Search Document

#### Objective

Define one stable Elasticsearch document per `product_master` row.

#### Tasks

1. Use one `product_master` row as one Elasticsearch document
2. Use `uuid` as Elasticsearch document `_id`
3. Include all fields needed to reproduce the current `v2` response
4. Classify fields into:
   - searchable text fields
   - exact match fields
   - filter-only fields
   - response-only fields
5. Mark searchable text fields:
   - `name`
   - `brand`
   - `category`
   - `sub_category`
   - `type`
   - `required_certifications`
   - `hazardous_materials`
6. Mark exact and substring-focused fields:
   - `model_number`
   - `upc`
7. Mark filter-only fields:
   - `status`
   - `category`
8. Mark response-only fields:
   - `manufacturer`
   - `market_value`
   - `market_value_avgs`
   - `additional_data`
   - timestamps
   - other metadata returned by `v2`
9. Document the target document structure

#### Acceptance Criteria

- A documented Elastic document model exists
- Every response field from `v2` has a clear source in the Elastic document

### Phase 3: Design the Elasticsearch Mapping

#### Objective

Create a controlled mapping that can mimic the intent of PostgreSQL `v2`
ranking.

#### Tasks

1. Create versioned index naming:
   - `product_master_v2_0001`
2. Create aliases:
   - `product_master_v2_read`
   - `product_master_v2_write`
3. Map exact fields as `keyword`
4. Map full-text fields as `text`
5. Add `.keyword` subfields where exact sorting/filtering helps
6. Add dedicated exact fields for:
   - `model_number`
   - `upc`
7. Add substring-friendly subfields for:
   - `model_number`
   - `upc`
8. Decide analyzer strategy for free text
9. Decide analyzer strategy for substring matching
10. Decide boost strategy aligned with current `v2` intent:
   - highest boosts for exact `upc` and exact `model_number`
   - strong boosts for `brand`, `model_number`, `upc`
   - medium boosts for `name`, `category`
   - lower boosts for `sub_category`, `type`,
     `required_certifications`, `hazardous_materials`
11. Decide tie-break behavior
12. Create version-controlled mapping artifacts

#### Acceptance Criteria

- Index mapping is explicit and version-controlled
- Mapping supports exact, fuzzy-ish text, and substring-style retrieval

### Phase 4: Provision Elastic Cloud Hosted on GCP

#### Objective

Create the hosted Elasticsearch destination cluster.

#### Tasks

1. Create a non-production Elastic Cloud deployment
2. Select `GCP` as provider
3. Select region nearest the PostgreSQL deployment
4. Select a suitable search-oriented hardware profile
5. Save:
   - Elasticsearch endpoint
   - Kibana endpoint
   - Cloud ID if used
   - admin credentials
6. Create an application API key with read-only privileges
7. Create a sink API key with write/manage privileges
8. Store secrets in secret management
9. Confirm network reachability from CDC workers to Elastic

#### Acceptance Criteria

- A non-prod Elastic Cloud deployment exists and is reachable
- Distinct app and sink credentials exist

### Phase 5: Prepare PostgreSQL for CDC

#### Objective

Enable safe logical replication from the source database.

#### Tasks

1. Confirm logical replication is supported
2. Verify `wal_level = logical`
3. Verify `max_replication_slots`
4. Verify `max_wal_senders`
5. Increase settings if needed
6. Create a dedicated CDC user
7. Grant:
   - `LOGIN`
   - `REPLICATION`
   - `SELECT` on `public.product_master`
8. Create a dedicated publication:
   - `dbz_pub_product_master_v2`
9. Reserve a slot name:
   - `dbz_product_master_v2`
10. Review WAL retention and lag implications
11. Open network paths from CDC workers to PostgreSQL

#### Acceptance Criteria

- PostgreSQL is ready for Debezium logical replication
- The CDC user, publication, and slot naming are defined

### Phase 6: Stand Up CDC Infrastructure

#### Objective

Create the transport path between PostgreSQL and Elastic.

#### Tasks

1. Choose the CDC runtime platform
2. Choose managed or self-managed Kafka
3. Provision Kafka brokers if needed
4. Provision Kafka Connect workers
5. Install Debezium PostgreSQL connector plugin
6. Install Elasticsearch sink connector plugin
7. Configure TLS and certificates if needed
8. Configure secret injection
9. Configure logs and metrics
10. Configure dead-letter queues
11. Add infrastructure manifests/configs under `infra/cdc/`

#### Acceptance Criteria

- CDC worker environment exists and can connect to both PostgreSQL and Elastic

### Phase 7: Configure the Debezium Source Connector

#### Objective

Capture an initial snapshot plus ongoing row changes from `product_master`.

#### Tasks

1. Create Debezium connector config
2. Set database connection properties
3. Set `plugin.name = pgoutput`
4. Set publication name
5. Set slot name
6. Limit capture to `public.product_master`
7. Set `snapshot.mode = initial`
8. Define topic naming
9. Add SMT to flatten Debezium envelopes
10. Preserve record keys
11. Configure delete/tombstone handling
12. Start connector in non-prod
13. Verify snapshot records flow into Kafka
14. Verify inserts, updates, and deletes appear

#### Acceptance Criteria

- The connector snapshots and streams `product_master` reliably

### Phase 8: Configure the Elasticsearch Sink Connector

#### Objective

Write CDC events into the versioned Elastic index.

#### Tasks

1. Pre-create the Elastic index and aliases
2. Create sink connector config
3. Subscribe to the correct Kafka topic(s)
4. Configure HTTPS and API-key authentication
5. Use record keys as document IDs
6. Write into `product_master_v2_write`
7. Configure delete propagation
8. Configure tombstone handling
9. Configure a dead-letter queue
10. Start the sink connector
11. Verify snapshot indexing
12. Verify update-overwrite behavior
13. Verify delete behavior

#### Acceptance Criteria

- A full snapshot lands in Elastic
- Ongoing row changes continue updating the same documents

### Phase 9: Add Repo Support for Elastic and CDC Operations

#### Objective

Prepare the codebase for Elastic-backed application work and reproducible ops.

#### Tasks

1. Add the Elasticsearch Python client dependency
2. Extend `.env.example` with Elastic settings
3. Add application settings for:
   - Elastic URL or Cloud ID
   - Elastic API key
   - index/alias names
   - request timeout
4. Create `app/elastic_client.py`
5. Add a connectivity script
6. Add an index creation script
7. Add version-controlled mapping files
8. Add Debezium and sink connector config artifacts
9. Update `README.md`
10. Update `context.md`

#### Acceptance Criteria

- The repo contains enough code and config to connect to Elastic and manage the
  index in a repeatable way

### Phase 10: Validate Data Sync Before Endpoint Work

#### Objective

Prove the Elastic index is trustworthy before app reads depend on it.

#### Tasks

1. Compare PostgreSQL row count to Elastic document count
2. Investigate and resolve mismatches
3. Compare sample UUIDs field by field
4. Test insert propagation
5. Test update propagation
6. Test delete propagation
7. Measure write-to-search lag
8. Define an acceptable lag threshold
9. Document validation results

#### Acceptance Criteria

- CDC correctness is demonstrated before application reads use Elastic

---

## Deliverable B

Implement the new `v2.2` endpoint, tune it for behavioral parity, and make it
available for adoption while leaving `/search/v2` untouched.

### Phase 11: Implement `GET /search/v2.2`

#### Objective

Create the new Elastic-backed endpoint using the same request and response
models as `v2`.

#### Tasks

1. Add `app/routers/search_v2_2.py`
2. Mirror the structure of `app/routers/search_v2.py`
3. Reuse `SearchRequestV2`
4. Reuse `SearchResponseV2`
5. Preserve blank-query handling
6. Add `app/search_engine_v2_2.py`
7. Implement an Elastic-backed `search_products_v2_2(...)`
8. Return the same tuple shape as `search_products_v2(...)`
9. Register the router in `app/main.py`
10. Expose `GET /search/v2.2`
11. Keep `/search/v2` unchanged

#### Acceptance Criteria

- A new endpoint exists without changing existing `v2`
- Input and output contracts match `v2`

### Phase 12: Recreate `v2` Search Semantics in Elastic

#### Objective

Make `v2.2` behave like `v2`, not merely query Elastic successfully.

#### Tasks

1. Build a primary Elastic query corresponding to `fulltext`
2. Always filter to `status = ACTIVE`
3. Apply exact `category` filter when provided
4. Heavily boost exact `model_number`
5. Heavily boost exact `upc`
6. Query analyzed text fields:
   - `brand`
   - `name`
   - `category`
   - `sub_category`
   - `type`
   - `required_certifications`
   - `hazardous_materials`
7. Add substring-capable matching for `model_number` and `upc`
8. Return `search_mode = "fulltext"` if the primary query has hits
9. Build a broader fallback Elastic query
10. Execute fallback only when:
   - primary returns zero hits
   - `fallback_enabled = true`
11. Return `search_mode = "wildcard"` for fallback hits
12. Use `_score` as `search_score`
13. Normalize array fields to `[]`
14. Normalize output field types to match existing `v2`

#### Acceptance Criteria

- `v2.2` produces results close enough to `v2` to satisfy parity tests

### Phase 13: Test, Compare, Tune, and Roll Out

#### Objective

Prove `v2.2` matches `v2` closely enough for consumers to adopt it safely.

#### Tasks

1. Add unit tests for the Elastic query builder
2. Add integration tests for `/search/v2.2`
3. Reuse current `v2` tests where possible
4. Add side-by-side comparison tests for `v2` vs `v2.2`
5. Reuse `test_cases.json`
6. Add a comparison script
7. Run targeted query classes:
   - exact brand queries
   - general text queries
   - `model_number` substring queries
   - `upc` exact queries
   - `upc` substring queries
   - category-filtered queries
   - empty/fallback cases
8. Tune analyzers and boosts
9. Measure latency
10. Document residual differences if any remain
11. Announce `/search/v2.2` for controlled adoption
12. Keep `/search/v2` as the reference and rollback option

#### Acceptance Criteria

- `v2.2` passes contract tests
- Result quality is acceptable against `v2`
- Consumers can adopt `v2.2` without disturbing `v2`

---

## Planned Repo Changes

### New docs

- `docs/search-v2-contract.md`
- `docs/elastic-v2-2-migration-plan.md`
- `docs/search-v2-elastic-document.md`
- `docs/elastic-v2-environment.md`
- `docs/postgres-cdc-prereqs.md`
- `docs/cdc-elastic-pipeline.md`
- `docs/v2-cdc-validation.md`

### New app files

- `app/elastic_client.py`
- `app/search_engine_v2_2.py`
- `app/routers/search_v2_2.py`

### New scripts and artifacts

- `scripts/create_es_index_v2.py`
- `scripts/check_elastic_connection.py`
- `scripts/compare_v2_vs_v2_2.py`
- `scripts/es/product_master_v2_mapping.json`
- `infra/cdc/debezium-product-master-v2.json`
- `infra/cdc/es-sink-product-master-v2.json`

### Updated files

- `requirements.txt`
- `.env.example`
- `app/main.py`
- `README.md`
- `context.md`
- tests

---

## Recommended Execution Order

1. Freeze the contract
2. Design the document model
3. Design the Elastic mapping
4. Provision Elastic Cloud on GCP
5. Prepare PostgreSQL for CDC
6. Stand up CDC infrastructure
7. Configure Debezium
8. Configure Elastic sink
9. Validate data sync
10. Add repo Elastic plumbing
11. Implement `v2.2`
12. Add parity tests
13. Tune ranking and publish `v2.2`

---

## Guardrails

- Do not modify the runtime behavior of `/search/v2`
- Do not use app-side dual writes
- Do not let Elasticsearch auto-create this index
- Do not skip delete propagation testing
- Do not treat response-shape parity as sufficient without ranking parity
