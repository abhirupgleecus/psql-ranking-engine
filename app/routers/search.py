from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Product
from app.schemas import RankedProduct, SearchRequest, SearchResponse
from app.scorer import score_product

router = APIRouter(tags=["search"])


@router.get("/search", response_model=SearchResponse)
async def search(
    params: Annotated[SearchRequest, Query()],
    db: AsyncSession = Depends(get_db),
):
    query = params.q.strip()

    if not query:
        raise HTTPException(
            status_code=422,
            detail="Query cannot be empty",
        )

    stmt = select(Product)

    if params.category is not None:
        stmt = stmt.where(Product.category == params.category)

    if params.in_stock_only:
        stmt = stmt.where(Product.in_stock.is_(True))

    result = await db.execute(stmt)

    products = result.scalars().all()

    total_candidates = len(products)

    ranked_products = []

    for product in products:
        product_dict = {
            "id": product.id,
            "name": product.name,
            "brand": product.brand,
            "category": product.category,
            "tags": product.tags,
            "description": product.description,
            "price": product.price,
            "rating": product.rating,
            "review_count": product.review_count,
            "in_stock": product.in_stock,
            "created_at": product.created_at,
        }

        total_score, score_breakdown = score_product(
            product_dict,
            query,
        )

        if total_score < params.min_score:
            continue

        ranked_products.append(
            RankedProduct(
                **product_dict,
                total_score=total_score,
                score_breakdown=score_breakdown,
            )
        )

    ranked_products.sort(
        key=lambda product: product.total_score,
        reverse=True,
    )

    ranked_products = ranked_products[: params.top_n]

    return SearchResponse(
        query=query,
        total_candidates=total_candidates,
        results_returned=len(ranked_products),
        results=ranked_products,
    )