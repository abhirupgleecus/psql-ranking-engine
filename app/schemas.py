from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SearchRequest(BaseModel):
    q: str = Field(..., min_length=1)
    top_n: int = Field(default=10, ge=1, le=100)
    min_score: int = Field(default=1, ge=0)
    category: str | None = None
    in_stock_only: bool = False

    @field_validator("q")
    @classmethod
    def validate_query(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Query cannot be empty")

        return value


class RankedProduct(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    brand: str
    category: str
    tags: list[str]
    description: str

    price: Decimal | None
    rating: Decimal | None

    review_count: int
    in_stock: bool
    created_at: datetime

    total_score: int
    score_breakdown: dict[str, int]


class SearchResponse(BaseModel):
    query: str
    total_candidates: int
    results_returned: int
    results: list[RankedProduct]