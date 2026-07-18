"""rename notice_image_path to notice_attachment_path

Revision ID: bf982a77e568
Revises: 6234feb5ae40
Create Date: 2026-07-13 00:35:57.459908

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bf982a77e568'
down_revision: Union[str, Sequence[str], None] = '6234feb5ae40'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
