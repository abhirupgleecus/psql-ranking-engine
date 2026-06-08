"""create_products_table

Revision ID: e884a7c1b51e
Revises:
Create Date: 2026-06-05 17:40:28.841058

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "e884a7c1b51e"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "products",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "name",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "brand",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "category",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "tags",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column(
            "description",
            sa.Text(),
            server_default=sa.text("''"),
            nullable=False,
        ),
        sa.Column(
            "price",
            sa.Numeric(precision=10, scale=2),
            nullable=True,
        ),
        sa.Column(
            "rating",
            sa.Numeric(precision=3, scale=2),
            nullable=True,
        ),
        sa.Column(
            "review_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "in_stock",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "rating >= 0.00 AND rating <= 5.00",
            name="ck_products_rating_range",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_products_brand",
        "products",
        ["brand"],
        unique=False,
    )

    op.create_index(
        "ix_products_category",
        "products",
        ["category"],
        unique=False,
    )

    op.create_index(
        "ix_products_tags_gin",
        "products",
        ["tags"],
        unique=False,
        postgresql_using="gin",
    )

    op.execute(
        "CREATE INDEX ix_products_name_tsv "
        "ON products USING gin (to_tsvector('english', name))"
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.execute("DROP INDEX IF EXISTS ix_products_name_tsv")

    op.drop_index(
        "ix_products_tags_gin",
        table_name="products",
        postgresql_using="gin",
    )

    op.drop_index(
        "ix_products_category",
        table_name="products",
    )

    op.drop_index(
        "ix_products_brand",
        table_name="products",
    )

    op.drop_table("products")