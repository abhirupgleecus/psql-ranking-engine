from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import (
    RankedProductMasterV2,
    SearchRequestV2,
    SearchResponseV2,
)
from app.search_engine_v2 import search_products_v2

router = APIRouter(tags=["search_v2"])


@router.get(
    "/search/v2",
    response_model=SearchResponseV2,
    response_model_exclude_none=True,
)
async def search_v2(
    params: Annotated[SearchRequestV2, Query()],
    db: AsyncSession = Depends(get_db),
):
    query = params.q.strip()

    if not query:
        raise HTTPException(
            status_code=422,
            detail="Query cannot be empty",
        )

    results, search_mode = await search_products_v2(
        db=db,
        q=query,
        top_n=params.top_n,
        category=params.category,
        fallback_enabled=params.fallback_enabled,
    )

    ranked_results = [RankedProductMasterV2(**res) for res in results]

    return SearchResponseV2(
        query=query,
        search_mode=search_mode,
        results_returned=len(ranked_results),
        results=ranked_results,
    )
