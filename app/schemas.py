from typing import Any
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SearchRequest(BaseModel):
    q: str = Field(..., min_length=1)
    top_n: int = Field(default=10, ge=1, le=100)
    min_score: int = Field(default=1, ge=0)
    category: str | None = None


    @field_validator("q")
    @classmethod
    def validate_query(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Query cannot be empty")

        return value

    @field_validator("category")
    @classmethod
    def validate_category(cls, value: str | None) -> str | None:
        if value is None:
            return None

        value = value.strip()
        return value or None


class ScoreBreakdown(BaseModel):
    exact_name_match: int | None = None
    name_starts_with_query: int | None = None
    name_whole_word_match: int | None = None
    name_contains_query: int | None = None
    exact_brand_match: int | None = None
    brand_contains_query: int | None = None
    exact_category_match: int | None = None
    category_contains_query: int | None = None
    type_contains_query: int | None = None
    sub_category_contains_query: int | None = None
    model_number_contains_query: int | None = None
    certification_exact_match: int | None = None
    hazardous_material_contains_query: int | None = None
    boost_high_repairability: int | None = None



class RankedProductMaster(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uuid: UUID
    status: str
    type: str | None
    name: str
    category: str | None
    sub_category: str | None
    brand: str
    manufacturer: dict[str, Any]
    upc: str | None
    variant: str | None
    model_number: str
    serial_number: str | None
    model_year: int | None
    weight_lb: Decimal | None
    weight_kg: Decimal | None
    dimensions_inches: str | None
    repairability_score: Decimal | None
    disassembly_complexity: str | None
    average_life_span_years: int | None
    energy_efficiency_rating: str | None
    authorized_needed: bool | None
    special_handling_required: bool | None
    contains_user_data: bool | None
    mandatory_data_wipe_needed: bool | None
    required_certifications: list[str]
    market_value: dict[str, Any]
    market_value_avgs: dict[str, Any]
    hazardous_materials: list[str]
    additional_data: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime
    goods_type: str
    master_uuid: str | None
    gtin: str | None
    ean: str | None

    total_score: int
    score_breakdown: ScoreBreakdown


class SearchResponse(BaseModel):
    query: str
    total_candidates: int
    results_returned: int
    results: list[RankedProductMaster]
