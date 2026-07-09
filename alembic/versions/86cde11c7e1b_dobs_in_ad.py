"""dobs in ad"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision = "86cde11c7e1b"
down_revision = "f9f0e44203e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    op.drop_column("child", "child_dob_ad")