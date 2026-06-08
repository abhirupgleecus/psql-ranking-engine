"""add_products_name_brand_unique_constraint

Revision ID: eb7a3f8d6c2a
Revises: e884a7c1b51e
Create Date: 2026-06-08 14:25:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "eb7a3f8d6c2a"
down_revision: Union[str, Sequence[str], None] = "e884a7c1b51e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    op.create_unique_constraint(
        "uq_products_name_brand",
        "products",
        ["name", "brand"],
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_constraint(
        "uq_products_name_brand",
        "products",
        type_="unique",
    )
