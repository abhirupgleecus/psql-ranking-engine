"""Phase 3 Hybrid Search Engine — Lexical + Semantic + RRF Fusion.

Orchestrates two retrieval passes:
1. Lexical: reuses v2's FTS + ILIKE fallback pipeline
2. Semantic: pgvector cosine similarity against Gemini Embedding 2 vectors

Results are fused via Reciprocal Rank Fusion (RRF), then sliced to top_n
with a post-fusion repairability boost.
"""

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.embedding_client import embed_query
from app.rrf import merge_rrf
from app.search_engine_v2 import search_products_v2, enum_value

logger = logging.getLogger(__name__)


def _build_hydration_query(uuids: list[UUID], category: str | None) -> tuple[str, dict]:
    """Build a query to hydrate full product fields for a set of UUIDs.

    Returns the SQL string and parameter dict.
    """
    # Build UUID placeholders for the IN clause
    uuid_placeholders = ", ".join(f":uuid_{i}" for i in range(len(uuids)))
    params: dict[str, Any] = {f"uuid_{i}": str(u) for i, u in enumerate(uuids)}

    sql = f"""
        SELECT
            uuid, status, type, name, category, sub_category, brand, manufacturer,
            upc, variant, model_number, serial_number, model_year, weight_lb, weight_kg,
            dimensions_inches, repairability_score, disassembly_complexity,
            average_life_span_years, energy_efficiency_rating, authorized_needed,
            special_handling_required, contains_user_data, mandatory_data_wipe_needed,
            required_certifications, market_value, market_value_avgs,
            hazardous_materials, additional_data, created_at, updated_at, goods_type,
            master_uuid, gtin, ean
        FROM product_master
        WHERE uuid IN ({uuid_placeholders})
    """

    return sql, params


async def search_products_v3(
    db: AsyncSession,
    q: str,
    top_n: int = 10,
    candidate_multiplier: int = 4,
    rrf_k: int = 60,
    category: str | None = None,
) -> tuple[list[dict[str, Any]], str]:
    """Execute Phase 3 hybrid search.

    Returns a tuple of (results, search_mode) where search_mode is:
    - "hybrid"  — both lexical and semantic passes ran
    - "lexical" — semantic pass was skipped (no API key or no embeddings)

    1. Run lexical retrieval (v2's FTS + ILIKE) with enlarged candidate pool
    2. Embed the query via Gemini Embedding 2
    3. Run semantic retrieval (pgvector cosine similarity)
    4. Fuse both ranked lists via RRF
    5. Slice to top_n, hydrate full product fields
    6. Apply post-fusion repairability boost (+0.001 for score >= 0.75)

    Args:
        db: Async database session
        q: Search query string
        top_n: Number of final results to return
        candidate_multiplier: Multiplier for candidate pool size per retrieval pass
        rrf_k: RRF constant k (default 60)
        category: Optional category filter

    Returns:
        Tuple of (list of product dicts with RRF metadata, search_mode string)
    """
    candidate_pool_size = top_n * candidate_multiplier

    # ── Step 1: Lexical retrieval (reuse v2 pipeline) ──────────────────────
    lexical_products, search_mode = await search_products_v2(
        db=db,
        q=q,
        top_n=candidate_pool_size,
        category=category,
        fallback_enabled=True,
    )

    # Extract (uuid, score) tuples for RRF — rank order is preserved from v2
    lexical_pairs: list[tuple[UUID, float]] = [
        (UUID(str(p["uuid"])), float(p["search_score"]))
        for p in lexical_products
    ]

    logger.debug(
        "Lexical pass (%s): %d candidates", search_mode, len(lexical_pairs)
    )

    # ── Step 2: Embed the query (skip semantic pass if key missing) ────────
    semantic_pairs: list[tuple[UUID, float]] = []
    _semantic_skipped = False

    try:
        query_embedding = await embed_query(q)

        # ── Step 3: Semantic retrieval ─────────────────────────────────────
        semantic_sql = text("""
            SELECT
                uuid,
                embedding <=> :query_embedding AS distance
            FROM product_master
            WHERE embedding IS NOT NULL
              AND status = 'ACTIVE'
              AND (cast(:category as varchar) IS NULL OR category = :category)
            ORDER BY embedding <=> :query_embedding
            LIMIT :candidate_pool_size;
        """)

        sem_result = await db.execute(
            semantic_sql,
            {
                "query_embedding": str(query_embedding),
                "category": category,
                "candidate_pool_size": candidate_pool_size,
            },
        )
        sem_rows = sem_result.mappings().all()

        semantic_pairs = [
            (UUID(str(row["uuid"])), float(row["distance"]))
            for row in sem_rows
        ]

        logger.debug("Semantic pass: %d candidates", len(semantic_pairs))

    except RuntimeError as exc:
        # API key not configured or Gemini call failed — degrade gracefully
        _semantic_skipped = True
        logger.warning(
            "Semantic pass skipped (lexical-only fallback): %s. "
            "Set GOOGLE_AI_API_KEY in .env and run scripts/embed_products.py "
            "to enable hybrid search.",
            exc,
        )

    # ── Step 4: RRF Fusion ─────────────────────────────────────────────────
    fused = merge_rrf(lexical_pairs, semantic_pairs, k=rrf_k)

    # ── Step 5: Slice to top_n and hydrate ─────────────────────────────────
    top_fused = fused[:top_n]

    if not top_fused:
        return [], "lexical" if _semantic_skipped else "hybrid"

    # Fetch full product data for the final set in a single query
    final_uuids = [item["uuid"] for item in top_fused]
    hydration_sql, hydration_params = _build_hydration_query(final_uuids, category)

    hydration_result = await db.execute(text(hydration_sql), hydration_params)
    hydration_rows = hydration_result.mappings().all()

    # Build a lookup by UUID for O(1) access
    product_lookup: dict[UUID, dict[str, Any]] = {}
    for row in hydration_rows:
        p_dict = dict(row)
        p_dict["status"] = enum_value(p_dict["status"])
        p_dict["disassembly_complexity"] = enum_value(p_dict["disassembly_complexity"])
        p_dict["goods_type"] = enum_value(p_dict["goods_type"])
        p_dict["required_certifications"] = p_dict["required_certifications"] or []
        p_dict["hazardous_materials"] = p_dict["hazardous_materials"] or []
        product_lookup[UUID(str(p_dict["uuid"]))] = p_dict

    # ── Step 6: Post-fusion repairability boost ────────────────────────────
    # Small additive bump to rrf_score for products with repairability_score >= 0.75.
    # This is consistent in spirit with v2's +0.1 on ts_rank_cd, but scaled down
    # because RRF scores are in the 0.001–0.03 range. The +0.001 bump can shuffle
    # a high-repairability product up by 1–2 positions among items with very
    # similar RRF scores, without dominating the fusion ranking.
    REPAIRABILITY_BOOST = 0.001
    REPAIRABILITY_THRESHOLD = 0.75

    results: list[dict[str, Any]] = []
    for item in top_fused:
        uuid = item["uuid"]
        product = product_lookup.get(uuid)

        if product is None:
            # This shouldn't happen, but skip gracefully if it does
            logger.warning("Product %s not found during hydration, skipping", uuid)
            continue

        rrf_score = item["rrf_score"]

        # Apply repairability boost
        repairability = product.get("repairability_score")
        if repairability is not None and float(repairability) >= REPAIRABILITY_THRESHOLD:
            rrf_score += REPAIRABILITY_BOOST

        # Merge RRF metadata into the product dict
        product["rrf_score"] = rrf_score
        product["matched_in"] = item["matched_in"]
        product["lexical_rank"] = item["lexical_rank"]
        product["lexical_score"] = item["lexical_score"]
        product["semantic_rank"] = item["semantic_rank"]
        product["semantic_distance"] = item["semantic_distance"]

        results.append(product)

    # ── Step 7: Final sort by adjusted rrf_score descending ────────────────
    results.sort(key=lambda x: -x["rrf_score"])

    search_mode = "lexical" if _semantic_skipped else "hybrid"
    return results, search_mode
