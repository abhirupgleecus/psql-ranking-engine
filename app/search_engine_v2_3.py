"""Elasticsearch-native hybrid search engine for the v2.3 endpoint.

Extends v2.2 (BM25 lexical) with a KNN semantic retrieval pass, fused via
Elasticsearch's built-in ``rrf`` retriever (available since ES 8.9).

Search semantics:
  - Lexical pass  → same multi-field BM25 query as v2.2, wrapped in a
                    ``standard`` sub-retriever.
  - Semantic pass → KNN over the ``embedding`` dense_vector field (768-dim
                    Gemini Embedding 2 cosine vectors).
  - Fusion        → ES native RRF (rank_constant=60, same default as our
                    Python rrf.py implementation).
  - search_mode   → "hybrid"  (both passes ran)
                    "lexical" (semantic skipped — no API key or no embeddings)

Graceful degradation:
  If GOOGLE_AI_API_KEY is absent or the Gemini call fails, the engine falls
  back to a plain BM25 query (identical to v2.2) and sets search_mode to
  "lexical".  The endpoint remains fully functional.
"""

from __future__ import annotations

import logging
from typing import Any

from app.database import settings
from app.elastic_client import create_async_elasticsearch_client, is_elastic_configured
from app.embedding_client import embed_query

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Boost weights — mirror v2.2 lexical boosts exactly
# ---------------------------------------------------------------------------
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


def _build_lexical_bool_query(q: str, category: str | None) -> dict[str, Any]:
    """Build the BM25 bool query shared by both the hybrid and fallback paths."""
    must_filters: list[dict[str, Any]] = [{"term": {"status": "ACTIVE"}}]
    if category:
        must_filters.append({"term": {"category.keyword": category}})

    should_clauses: list[dict[str, Any]] = [
        {"term": {"upc": {"value": q, "boost": _BOOST_UPC_EXACT}}},
        {"term": {"model_number": {"value": q, "boost": _BOOST_MODEL_EXACT}}},
        {"match": {"upc.text": {"query": q, "boost": _BOOST_UPC_TEXT}}},
        {"match": {"model_number.text": {"query": q, "boost": _BOOST_MODEL_TEXT}}},
        {"match": {"upc.partial": {"query": q, "boost": _BOOST_UPC_PARTIAL}}},
        {"match": {"model_number.partial": {"query": q, "boost": _BOOST_MODEL_PARTIAL}}},
        {"match": {"brand": {"query": q, "boost": _BOOST_BRAND}}},
        {"match": {"name": {"query": q, "boost": _BOOST_NAME}}},
        {"match": {"category": {"query": q, "boost": _BOOST_CATEGORY}}},
        {"match": {"sub_category": {"query": q, "boost": _BOOST_SUB_CATEGORY}}},
        {"match": {"type": {"query": q, "boost": _BOOST_TYPE}}},
        {"match": {"required_certifications": {"query": q, "boost": _BOOST_CERTS}}},
        {"match": {"hazardous_materials": {"query": q, "boost": _BOOST_HAZMAT}}},
    ]

    return {
        "bool": {
            "filter": must_filters,
            "should": should_clauses,
            "minimum_should_match": 1,
        }
    }


def _build_hybrid_body(
    q: str,
    query_vector: list[float],
    category: str | None,
    top_n: int,
    candidate_pool_size: int,
    rrf_k: int,
) -> dict[str, Any]:
    """Build the native ES rrf retriever body (hybrid path)."""
    knn_filter: list[dict[str, Any]] = [{"term": {"status": "ACTIVE"}}]
    if category:
        knn_filter.append({"term": {"category.keyword": category}})

    return {
        "retriever": {
            "rrf": {
                "retrievers": [
                    {
                        "standard": {
                            "query": _build_lexical_bool_query(q, category),
                        }
                    },
                    {
                        "knn": {
                            "field": "embedding",
                            "query_vector": query_vector,
                            "k": candidate_pool_size,
                            "num_candidates": candidate_pool_size,
                            "filter": knn_filter,
                        }
                    },
                ],
                "rank_window_size": candidate_pool_size,
                "rank_constant": rrf_k,
            }
        },
        "size": top_n,
        "_source": True,
    }


def _build_lexical_only_body(
    q: str,
    category: str | None,
    top_n: int,
) -> dict[str, Any]:
    """Build the plain BM25 query body (lexical-only fallback path)."""
    return {
        "query": _build_lexical_bool_query(q, category),
        "size": top_n,
        "_source": True,
    }


def _hit_to_dict(hit: dict[str, Any], search_mode: str) -> dict[str, Any]:
    """Convert a raw ES hit into the dict shape expected by RankedProductV2_3."""
    import base64
    import json as _json

    source: dict[str, Any] = hit["_source"]
    score: float = float(hit.get("_score") or 0.0)
    doc = dict(source)

    # Deserialize Debezium string-encoded JSONB fields
    for field in ("market_value", "market_value_avgs", "additional_data", "manufacturer"):
        val = doc.get(field)
        if isinstance(val, str):
            try:
                doc[field] = _json.loads(val)
            except (ValueError, TypeError):
                doc[field] = None

    # Decode Debezium base64-encoded numeric fields
    for field in ("weight_lb", "weight_kg", "repairability_score"):
        val = doc.get(field)
        if isinstance(val, str):
            try:
                doc[field] = float(base64.b64decode(val).decode("utf-8").strip())
            except Exception:
                doc[field] = None

    doc["search_score"] = score
    doc["search_mode"] = search_mode
    doc["required_certifications"] = doc.get("required_certifications") or []
    doc["hazardous_materials"] = doc.get("hazardous_materials") or []

    for field in ("status", "disassembly_complexity", "goods_type"):
        if doc.get(field) is None:
            doc[field] = None

    return doc


async def search_products_v2_3(
    q: str,
    top_n: int = 10,
    candidate_multiplier: int = 4,
    rrf_k: int = 60,
    category: str | None = None,
) -> tuple[list[dict[str, Any]], str]:
    """Execute v2.3 hybrid search against Elasticsearch.

    1. Attempts to embed the query via Gemini Embedding 2.
    2. If embedding succeeds, fires the native ES rrf retriever (hybrid mode).
    3. If embedding fails (no API key / Gemini error), falls back to plain
       BM25 query (lexical-only mode — identical to v2.2).
    4. Returns (list of product dicts, search_mode).

    Raises:
        RuntimeError: if Elasticsearch is not configured (no ELASTIC_URL /
                      ELASTIC_CLOUD_ID).  The router converts this to HTTP 503.
    """
    if not is_elastic_configured():
        raise RuntimeError(
            "Elasticsearch is not configured. "
            "Set ELASTIC_CLOUD_ID or ELASTIC_URL in the environment to enable "
            "the v2.3 endpoint."
        )

    index = settings.ELASTIC_V2_INDEX_READ_ALIAS
    candidate_pool_size = top_n * candidate_multiplier
    client = create_async_elasticsearch_client()

    try:
        # ── 1. Attempt query embedding ────────────────────────────────────────
        query_vector: list[float] | None = None
        try:
            query_vector = await embed_query(q)
            logger.debug("Query embedded: dims=%d", len(query_vector))
        except RuntimeError as exc:
            logger.warning(
                "Semantic pass skipped (lexical-only fallback): %s. "
                "Set GOOGLE_AI_API_KEY in .env and run scripts/embed_products.py "
                "to enable hybrid search.",
                exc,
            )

        # ── 2. Build and fire query ───────────────────────────────────────────
        if query_vector is not None:
            body = _build_hybrid_body(
                q=q,
                query_vector=query_vector,
                category=category,
                top_n=top_n,
                candidate_pool_size=candidate_pool_size,
                rrf_k=rrf_k,
            )
            search_mode = "hybrid"
        else:
            body = _build_lexical_only_body(q=q, category=category, top_n=top_n)
            search_mode = "lexical"

        resp = await client.search(index=index, body=body)
        hits: list[dict[str, Any]] = resp["hits"]["hits"]

        results = [_hit_to_dict(h, search_mode) for h in hits]
        return results, search_mode

    finally:
        await client.close()
