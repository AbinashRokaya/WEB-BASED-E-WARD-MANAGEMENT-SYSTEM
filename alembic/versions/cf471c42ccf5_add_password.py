"""add password

Revision ID: cf471c42ccf5
Revises: d3556f3fccc3
Create Date: 2026-07-06 19:08:13.937674

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cf471c42ccf5'
down_revision: Union[str, Sequence[str], None] = 'd3556f3fccc3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
