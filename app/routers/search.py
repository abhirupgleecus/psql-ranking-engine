from enum import Enum
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import ProductMaster, ProductStatus
from app.schemas import (
    RankedProductMaster,
    ScoreBreakdown,
    SearchRequest,
    SearchResponse,
)
from app.scorer import score_product

router = APIRouter(tags=["search"])


def enum_value(value: Enum | None) -> str | None:
    if value is None:
        return None

    return value.value


@router.get(
    "/search",
    response_model=SearchResponse,
    response_model_exclude_none=True,
)
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

    stmt = select(ProductMaster).where(ProductMaster.status == ProductStatus.ACTIVE)

    if params.category is not None:
        stmt = stmt.where(ProductMaster.category == params.category)

    result = await db.execute(stmt)

    products = result.scalars().all()

    total_candidates = len(products)

    ranked_products = []

    for product in products:
        product_dict = {
            "uuid": product.uuid,
            "status": enum_value(product.status),
            "type": product.type,
            "name": product.name,
            "category": product.category,
            "sub_category": product.sub_category,
            "brand": product.brand,
            "manufacturer": product.manufacturer,
            "upc": product.upc,
            "variant": product.variant,
            "model_number": product.model_number,
            "serial_number": product.serial_number,
            "model_year": product.model_year,
            "weight_lb": product.weight_lb,
            "weight_kg": product.weight_kg,
            "dimensions_inches": product.dimensions_inches,
            "repairability_score": product.repairability_score,
            "disassembly_complexity": enum_value(product.disassembly_complexity),
            "average_life_span_years": product.average_life_span_years,
            "energy_efficiency_rating": product.energy_efficiency_rating,
            "authorized_needed": product.authorized_needed,
            "special_handling_required": product.special_handling_required,
            "contains_user_data": product.contains_user_data,
            "mandatory_data_wipe_needed": product.mandatory_data_wipe_needed,
            "required_certifications": product.required_certifications or [],
            "market_value": product.market_value,
            "market_value_avgs": product.market_value_avgs,
            "hazardous_materials": product.hazardous_materials or [],
            "additional_data": product.additional_data,
            "created_at": product.created_at,
            "updated_at": product.updated_at,
            "goods_type": enum_value(product.goods_type),
            "master_uuid": product.master_uuid,
            "gtin": product.gtin,
            "ean": product.ean,
        }

        total_score, score_breakdown = score_product(
            product_dict,
            query,
        )

        if total_score < params.min_score:
            continue

        ranked_products.append(
            RankedProductMaster(
                **product_dict,
                total_score=total_score,
                score_breakdown=ScoreBreakdown(**score_breakdown),
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
