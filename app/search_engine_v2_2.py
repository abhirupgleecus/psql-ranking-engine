"""Elastic-backed search engine for the v2.2 endpoint.

Mirrors the observable behavior of search_engine_v2.py (PostgreSQL) using
Elasticsearch as the backend.

Search semantics preserved from v2:
  - primary query  → search_mode = "fulltext"
  - fallback query → search_mode = "wildcard" (only when primary hits == 0
                     and fallback_enabled is True)
  - always filter status = ACTIVE
  - exact category filter when category is provided
  - heavy boosts on exact model_number / upc
  - analyzed text matching across brand, name, category, sub_category, type,
    required_certifications, hazardous_materials
  - substring (ngram) matching for model_number and upc

Graceful degradation:
  If ELASTIC_CLOUD_ID / ELASTIC_URL are not set in the environment the
  function raises RuntimeError with a clear message.  The router converts
  this to HTTP 503 so the rest of the API remains unaffected.
"""

from __future__ import annotations

from typing import Any

from app.database import settings
from app.elastic_client import create_async_elasticsearch_client, is_elastic_configured

# ---------------------------------------------------------------------------
# Boost weights – mirrors v2 intent, tuned for Elastic scoring
# ---------------------------------------------------------------------------

# Primary (fulltext) query boosts
_BOOST_UPC_EXACT = 30.0
_BOOST_MODEL_EXACT = 25.0
_BOOST_UPC_TEXT = 12.0
_BOOST_MODEL_TEXT = 10.0
_BOOST_UPC_PARTIAL = 8.0
_BOOST_MODEL_PARTIAL = 7.0
_BOOST_BRAND = 6.0
_BOOST_NAME = 5.0
_BOOST_CATEGORY = 4.0
_BOOST_SUB_CATEGORY = 2.0
_BOOST_TYPE = 2.0
_BOOST_CERTS = 1.0
_BOOST_HAZMAT = 1.0

# Fallback (wildcard) query boosts – intentionally flat
_FALLBACK_BOOST_BRAND = 3.0
_FALLBACK_BOOST_NAME = 3.0
_FALLBACK_BOOST_CATEGORY = 2.0
_FALLBACK_BOOST_SUB_CATEGORY = 1.0
_FALLBACK_BOOST_TYPE = 1.0
_FALLBACK_BOOST_MODEL = 2.0
_FALLBACK_BOOST_UPC = 2.0
_FALLBACK_BOOST_CERTS = 1.0
_FALLBACK_BOOST_HAZMAT = 1.0


def _build_primary_query(
    q: str,
    category: str | None,
    top_n: int,
) -> dict[str, Any]:
    """Build the primary multi-field Elastic query (maps to v2 fulltext mode)."""

    must_filters: list[dict[str, Any]] = [
        {"term": {"status": "ACTIVE"}},
    ]
    if category:
        must_filters.append({"term": {"category.keyword": category}})

    should_clauses: list[dict[str, Any]] = [
        # Exact keyword matches – highest priority
        {"term": {"upc": {"value": q, "boost": _BOOST_UPC_EXACT}}},
        {"term": {"model_number": {"value": q, "boost": _BOOST_MODEL_EXACT}}},
        # Analyzed text matches
        {"match": {"upc.text": {"query": q, "boost": _BOOST_UPC_TEXT}}},
        {"match": {"model_number.text": {"query": q, "boost": _BOOST_MODEL_TEXT}}},
        # Ngram / partial substring matches
        {"match": {"upc.partial": {"query": q, "boost": _BOOST_UPC_PARTIAL}}},
        {"match": {"model_number.partial": {"query": q, "boost": _BOOST_MODEL_PARTIAL}}},
        # Primary text relevance fields
        {"match": {"brand": {"query": q, "boost": _BOOST_BRAND}}},
        {"match": {"name": {"query": q, "boost": _BOOST_NAME}}},
        {"match": {"category": {"query": q, "boost": _BOOST_CATEGORY}}},
        {"match": {"sub_category": {"query": q, "boost": _BOOST_SUB_CATEGORY}}},
        {"match": {"type": {"query": q, "boost": _BOOST_TYPE}}},
        # Secondary lexical fields
        {"match": {"required_certifications": {"query": q, "boost": _BOOST_CERTS}}},
        {"match": {"hazardous_materials": {"query": q, "boost": _BOOST_HAZMAT}}},
    ]

    return {
        "query": {
            "bool": {
                "filter": must_filters,
                "should": should_clauses,
                "minimum_should_match": 1,
            }
        },
        "size": top_n,
        "_source": True,
    }


def _build_fallback_query(
    q: str,
    category: str | None,
    top_n: int,
) -> dict[str, Any]:
    """Build the broader fallback query (maps to v2 wildcard mode).

    Uses match queries with lenient/fuzzy-ish settings across all searchable
    fields.  The intent mirrors the v2 ILIKE fallback: cast a wide net when
    the primary retrieval found nothing.
    """

    must_filters: list[dict[str, Any]] = [
        {"term": {"status": "ACTIVE"}},
    ]
    if category:
        must_filters.append({"term": {"category.keyword": category}})

    # match_phrase_prefix on text fields gives a leading-wildcard-style hit
    # without requiring ngram tokens – suitable for the fallback path.
    should_clauses: list[dict[str, Any]] = [
        {"match": {"brand": {"query": q, "boost": _FALLBACK_BOOST_BRAND, "fuzziness": "AUTO"}}},
        {"match": {"name": {"query": q, "boost": _FALLBACK_BOOST_NAME, "fuzziness": "AUTO"}}},
        {"match": {"category": {"query": q, "boost": _FALLBACK_BOOST_CATEGORY}}},
        {"match": {"sub_category": {"query": q, "boost": _FALLBACK_BOOST_SUB_CATEGORY}}},
        {"match": {"type": {"query": q, "boost": _FALLBACK_BOOST_TYPE}}},
        {"match": {"model_number.partial": {"query": q, "boost": _FALLBACK_BOOST_MODEL}}},
        {"match": {"upc.partial": {"query": q, "boost": _FALLBACK_BOOST_UPC}}},
        {"match": {"required_certifications": {"query": q, "boost": _FALLBACK_BOOST_CERTS}}},
        {"match": {"hazardous_materials": {"query": q, "boost": _FALLBACK_BOOST_HAZMAT}}},
    ]

    return {
        "query": {
            "bool": {
                "filter": must_filters,
                "should": should_clauses,
                "minimum_should_match": 1,
            }
        },
        "size": top_n,
        "_source": True,
    }


def _hit_to_dict(hit: dict[str, Any], search_mode: str) -> dict[str, Any]:
    """Convert a raw Elasticsearch hit into the dict shape expected by
    RankedProductMasterV2."""

    source: dict[str, Any] = hit["_source"]
    score: float = float(hit.get("_score") or 0.0)

    doc = dict(source)

    # Derived fields
    doc["search_score"] = score
    doc["search_mode"] = search_mode

    # Normalize array fields – must never be None
    doc["required_certifications"] = doc.get("required_certifications") or []
    doc["hazardous_materials"] = doc.get("hazardous_materials") or []

    # Normalize enum-like fields to plain strings (Elastic stores them as
    # strings already, but guard against None for safety)
    for field in ("status", "disassembly_complexity", "goods_type"):
        if doc.get(field) is None:
            doc[field] = None

    return doc


async def search_products_v2_2(
    q: str,
    top_n: int = 10,
    category: str | None = None,
    fallback_enabled: bool = True,
) -> tuple[list[dict[str, Any]], str]:
    """Execute v2.2 search against Elasticsearch.

    1. Attempts primary multi-field query (search_mode = "fulltext").
    2. If primary returns 0 hits and fallback_enabled is True, runs the
       broader fallback query (search_mode = "wildcard").
    3. Returns (list of product dicts, search_mode).

    Raises:
        RuntimeError: if Elastic is not configured (no URL / Cloud ID) or if
                      credentials are missing.  The caller (router) converts
                      this to HTTP 503.
    """
    if not is_elastic_configured():
        raise RuntimeError(
            "Elasticsearch is not configured. "
            "Set ELASTIC_CLOUD_ID or ELASTIC_URL in the environment to enable "
            "the v2.2 endpoint."
        )

    index = settings.ELASTIC_V2_INDEX_READ_ALIAS
    client = create_async_elasticsearch_client()

    try:
        # ── 1. Primary query ─────────────────────────────────────────────────
        primary_body = _build_primary_query(q=q, category=category, top_n=top_n)
        primary_resp = await client.search(index=index, body=primary_body)
        primary_hits: list[dict[str, Any]] = primary_resp["hits"]["hits"]

        if primary_hits:
            results = [_hit_to_dict(h, "fulltext") for h in primary_hits]
            return results, "fulltext"

        # ── 2. Fallback query ────────────────────────────────────────────────
        if fallback_enabled:
            fallback_body = _build_fallback_query(q=q, category=category, top_n=top_n)
            fallback_resp = await client.search(index=index, body=fallback_body)
            fallback_hits: list[dict[str, Any]] = fallback_resp["hits"]["hits"]

            results = [_hit_to_dict(h, "wildcard") for h in fallback_hits]
            return results, "wildcard"

        # ── 3. Nothing found, fallback disabled ──────────────────────────────
        return [], "fulltext"

    finally:
        await client.close()
