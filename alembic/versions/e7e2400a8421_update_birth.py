"""update_birth

Revision ID: e7e2400a8421
Revises: ca936109ab72
Create Date: 2026-07-18 08:58:35.383710

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e7e2400a8421'
down_revision: Union[str, Sequence[str], None] = 'ca936109ab72'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 1. Create the Enum type first (Postgres specific requirement)
    # Note: If 'gendertype' already exists in your DB, wrap this in a try/except or omit it if handled elsewhere
    gender_enum = sa.Enum('MALE', 'FEMALE', 'OTHERS', name='gendertype')
    gender_enum.create(op.get_bind(), checkfirst=True)

    # 2. Add the column as nullable=True temporarily
    op.add_column('child', sa.Column('child_gender', gender_enum, nullable=True))

    # 3. Update existing rows with a default value so they aren't null anymore
    # Change 'OTHERS' to whichever default value makes the most sense for your placeholder data
    op.execute("UPDATE child SET child_gender = 'OTHERS' WHERE child_gender IS NULL")

    # 4. Now that no rows are null, safely alter the column to NOT NULL
    op.alter_column('child', 'child_gender', nullable=False)


def downgrade() -> None:
    op.drop_column('child', 'child_gender')
    # Optional: drop enum type if it isn't used anywhere else
    sa.Enum(name='gendertype').drop(op.get_bind(), checkfirst=True)
