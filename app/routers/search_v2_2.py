from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.schemas import (
    RankedProductMasterV2,
    SearchRequestV2,
    SearchResponseV2,
)
from app.search_engine_v2_2 import search_products_v2_2

router = APIRouter(tags=["search_v2_2"])


@router.get(
    "/search/v2.2",
    response_model=SearchResponseV2,
    response_model_exclude_none=True,
    summary="Search products (v2.2 – Elastic backend)",
    description=(
        "Elastic-backed equivalent of GET /search/v2. "
        "Request parameters, validation, response shape, search_mode values, "
        "ACTIVE filtering, category filtering, and fallback behavior are "
        "identical to v2. Returns HTTP 503 when the Elasticsearch backend is "
        "not yet configured."
    ),
)
async def search_v2_2(
    params: Annotated[SearchRequestV2, Query()],
):
    query = params.q.strip()

    if not query:
        raise HTTPException(
            status_code=422,
            detail="Query cannot be empty",
        )

    try:
        results, search_mode = await search_products_v2_2(
            q=query,
            top_n=params.top_n,
            category=params.category,
            fallback_enabled=params.fallback_enabled,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    ranked_results = [RankedProductMasterV2(**res) for res in results]

    return SearchResponseV2(
        query=query,
        search_mode=search_mode,
        results_returned=len(ranked_results),
        results=ranked_results,
    )
