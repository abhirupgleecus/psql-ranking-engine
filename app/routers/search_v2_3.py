"""GET /search/v2.3 — Elasticsearch-native hybrid search endpoint.

Extends v2.2 (BM25 lexical) with KNN semantic retrieval and native RRF fusion.
Gracefully degrades to lexical-only if GOOGLE_AI_API_KEY is absent.
"""

from fastapi import APIRouter, HTTPException, Query
from starlette.responses import JSONResponse

from app.schemas import RankedProductV2_3, SearchResponseV2_3
from app.search_engine_v2_3 import search_products_v2_3

router = APIRouter(tags=["search_v2_3"])


@router.get(
    "/search/v2.3",
    response_model=SearchResponseV2_3,
    response_model_exclude_none=True,
)
async def search_v2_3(
    q: str = Query(..., min_length=1, description="Search query"),
    top_n: int = Query(default=10, ge=1, le=100, description="Number of results to return"),
    candidate_multiplier: int = Query(
        default=10,
        ge=1,
        le=20,
        description="Multiplier for KNN num_candidates and rrf rank_window_size (top_n × multiplier)",
    ),
    rrf_k: int = Query(
        default=60,
        ge=1,
        description="RRF rank_constant k — higher reduces influence of top ranks",
    ),
    category: str | None = Query(default=None, description="Filter by exact category"),
):
    """Elasticsearch-native hybrid search: BM25 lexical + KNN semantic, fused via native RRF.

    - search_mode = "hybrid"  when both lexical and semantic passes ran.
    - search_mode = "lexical" when semantic was skipped (no GOOGLE_AI_API_KEY or Gemini failure).
    """
    query = q.strip()
    if not query:
        raise HTTPException(status_code=422, detail="Query cannot be empty")

    try:
        results, search_mode = await search_products_v2_3(
            q=query,
            top_n=top_n,
            candidate_multiplier=candidate_multiplier,
            rrf_k=rrf_k,
            category=category,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    ranked_results = [RankedProductV2_3(**res) for res in results]

    return SearchResponseV2_3(
        query=query,
        search_mode=search_mode,
        results_returned=len(ranked_results),
        rrf_k=rrf_k,
        candidate_multiplier=candidate_multiplier,
        results=ranked_results,
    )
