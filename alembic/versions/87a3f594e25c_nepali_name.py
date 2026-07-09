"""nepali name

Revision ID: 87a3f594e25c
Revises: cf471c42ccf5
Create Date: 2026-07-07 19:14:39.699723

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '87a3f594e25c'
down_revision: Union[str, Sequence[str], None] = 'cf471c42ccf5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
