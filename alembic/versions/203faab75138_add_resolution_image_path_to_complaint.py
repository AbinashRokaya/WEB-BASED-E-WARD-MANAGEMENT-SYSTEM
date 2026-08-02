"""add resolution_image_path to complaint

Revision ID: 203faab75138
Revises: f739b63885c0
Create Date: 2026-07-27 07:41:23.730106

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '203faab75138'
down_revision: Union[str, Sequence[str], None] = 'f739b63885c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('complaint', sa.Column('resolution_image_path', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('complaint', 'resolution_image_path')