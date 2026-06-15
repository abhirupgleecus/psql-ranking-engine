"""GET /search/v3 — Hybrid search endpoint (lexical + semantic + RRF)."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import RankedProductV3, SearchResponseV3
from app.search_engine_v3 import search_products_v3

router = APIRouter(tags=["search_v3"])


@router.get(
    "/search/v3",
    response_model=SearchResponseV3,
    response_model_exclude_none=True,
)
async def search_v3(
    q: str = Query(..., min_length=1, description="Search query"),
    top_n: int = Query(default=10, ge=1, le=100, description="Number of results to return"),
    candidate_multiplier: int = Query(
        default=4,
        ge=1,
        le=20,
        description="Multiplier for candidate pool size per retrieval pass",
    ),
    rrf_k: int = Query(
        default=60,
        ge=1,
        description="RRF constant k (higher = less influence from top ranks)",
    ),
    category: str | None = Query(default=None, description="Filter by category"),
    db: AsyncSession = Depends(get_db),
):
    """Hybrid search combining lexical (FTS + ILIKE) and semantic (pgvector) retrieval.

    Results are fused via Reciprocal Rank Fusion (RRF) and include full
    debug visibility: rrf_score, matched_in, lexical_rank/score,
    semantic_rank/distance.
    """
    query = q.strip()

    if not query:
        raise HTTPException(
            status_code=422,
            detail="Query cannot be empty",
        )

    results, search_mode = await search_products_v3(
        db=db,
        q=query,
        top_n=top_n,
        candidate_multiplier=candidate_multiplier,
        rrf_k=rrf_k,
        category=category,
    )

    ranked_results = [RankedProductV3(**res) for res in results]

    return SearchResponseV3(
        query=query,
        search_mode=search_mode,
        results_returned=len(ranked_results),
        rrf_k=rrf_k,
        candidate_multiplier=candidate_multiplier,
        results=ranked_results,
    )
