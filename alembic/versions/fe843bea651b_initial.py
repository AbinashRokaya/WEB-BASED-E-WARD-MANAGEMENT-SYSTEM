"""initial (re-created missing revision)

Revision ID: fe843bea651b
Revises: 
Create Date: 2026-06-11 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fe843bea651b'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # this migration was created to match an existing DB state; no operations
    pass


def downgrade() -> None:
    pass


