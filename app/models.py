import enum
from decimal import Decimal
from typing import Any, List
from uuid import UUID
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Enum as SAEnum,
    CheckConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR, UUID as PG_UUID
from pgvector.sqlalchemy import Vector
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ProductStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    ARCHIVED = "ARCHIVED"


class ComplexityLevel(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ProductType(str, enum.Enum):
    SMALL_WHITE_GOODS = "SMALL_WHITE_GOODS"
    LARGE_WHITE_GOODS = "LARGE_WHITE_GOODS"


class Product(Base):
    __tablename__ = "products"

    __table_args__ = (
        CheckConstraint(
            "rating >= 0.00 AND rating <= 5.00",
            name="ck_products_rating_range",
        ),
        UniqueConstraint(
            "name",
            "brand",
            name="uq_products_name_brand",
        ),
        Index(
            "ix_products_tags_gin",
            "tags",
            postgresql_using="gin",
        ),
        Index("ix_products_brand", "brand"),
        Index("ix_products_category", "category"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    name: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    brand: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    category: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    tags: Mapped[List[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        server_default=text("'{}'"),
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("''"),
    )

    price: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )

    rating: Mapped[Decimal | None] = mapped_column(
        Numeric(3, 2),
        nullable=True,
    )

    review_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )

    in_stock: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )

    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
    )


class ProductMaster(Base):
    __tablename__ = "product_master"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    uuid: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
    )

    status: Mapped[ProductStatus] = mapped_column(
        SAEnum(
            ProductStatus,
            name="product_status",
            create_type=False,
        ),
        nullable=False,
    )

    type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    category: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    sub_category: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    brand: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    manufacturer: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
    )

    upc: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    variant: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    model_number: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    serial_number: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    model_year: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    weight_lb: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 3),
        nullable=True,
    )

    weight_kg: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 3),
        nullable=True,
    )

    dimensions_inches: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    repairability_score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )

    disassembly_complexity: Mapped[ComplexityLevel | None] = mapped_column(
        SAEnum(
            ComplexityLevel,
            name="complexity_level",
            create_type=False,
        ),
        nullable=True,
    )

    average_life_span_years: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    energy_efficiency_rating: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    authorized_needed: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
    )

    special_handling_required: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
    )

    contains_user_data: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
    )

    mandatory_data_wipe_needed: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
    )

    required_certifications: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(255)),
        nullable=True,
    )

    market_value: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
    )

    market_value_avgs: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
    )

    hazardous_materials: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(255)),
        nullable=True,
    )

    additional_data: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
    )

    goods_type: Mapped[ProductType] = mapped_column(
        SAEnum(
            ProductType,
            name="product_type",
            create_type=False,
        ),
        nullable=False,
    )

    master_uuid: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    gtin: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    ean: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    search_vector: Mapped[Any | None] = mapped_column(
        TSVECTOR,
        nullable=True,
    )

    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(768),
        nullable=True,
    )

