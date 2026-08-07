"""add is_valid and revoked_reason to recommendation_certificate

Revision ID: 83b34cbbed85
Revises: 62ecf65fd7be
Create Date: 2026-08-08 00:38:04.327747

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '83b34cbbed85'
down_revision: Union[str, Sequence[str], None] = '62ecf65fd7be'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.add_column(
        'recommendation_certificate',
        sa.Column('is_valid', sa.Boolean(), nullable=False, server_default=sa.true())
    )
    op.add_column(
        'recommendation_certificate',
        sa.Column('revoked_reason', sa.Text(), nullable=True)
    )
    # Optional: drop the server default now that existing rows are backfilled,
    # so future inserts rely on the ORM-level default instead
    op.alter_column('recommendation_certificate', 'is_valid', server_default=None)


def downgrade():
    op.drop_column('recommendation_certificate', 'revoked_reason')
    op.drop_column('recommendation_certificate', 'is_valid')