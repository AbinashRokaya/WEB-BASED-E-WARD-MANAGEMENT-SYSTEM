"""describe changes

Revision ID: 59ef755820a8
Revises: 0d69337bf5d6
Create Date: 2026-06-14 12:25:01.001761
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "59ef755820a8"
down_revision: Union[str, Sequence[str], None] = "0d69337bf5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


birth_place_enum = postgresql.ENUM(
    "HOSPITAL",
    "HOME",
    "OUTER",
    name="birthplacetype",
)


def upgrade() -> None:
    # Create enum type first
    birth_place_enum.create(op.get_bind(), checkfirst=True)

    # Add new columns
    op.add_column(
        "child",
        sa.Column("child_first_name", sa.String(100), nullable=True),
    )

    op.add_column(
        "child",
        sa.Column("child_middle_name", sa.String(100), nullable=True),
    )

    op.add_column(
        "child",
        sa.Column("child_last_name", sa.String(100), nullable=True),
    )

    op.add_column(
        "child",
        sa.Column("child_birth_place", birth_place_enum, nullable=True),
    )

    # Drop old columns
    op.drop_column("child", "child_municipality")
    op.drop_column("child", "child_ward_no")
    op.drop_column("child", "child_full_name")
    op.drop_column("child", "child_province")
    op.drop_column("child", "child_district")


def downgrade() -> None:
    # Restore old columns
    op.add_column(
        "child",
        sa.Column("child_district", sa.String(100), nullable=True),
    )

    op.add_column(
        "child",
        sa.Column("child_province", sa.String(100), nullable=True),
    )

    op.add_column(
        "child",
        sa.Column("child_full_name", sa.String(100), nullable=True),
    )

    op.add_column(
        "child",
        sa.Column("child_ward_no", sa.Integer(), nullable=True),
    )

    op.add_column(
        "child",
        sa.Column("child_municipality", sa.String(100), nullable=True),
    )

    # Remove new columns
    op.drop_column("child", "child_birth_place")
    op.drop_column("child", "child_last_name")
    op.drop_column("child", "child_middle_name")
    op.drop_column("child", "child_first_name")

    # Drop enum type
    birth_place_enum.drop(op.get_bind(), checkfirst=True)