"""add address

Revision ID: a64741184769
Revises: 4ff2a9df6c2a
Create Date: 2026-06-15 00:45:53.107286

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a64741184769'
down_revision: Union[str, Sequence[str], None] = '4ff2a9df6c2a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Define the enum helper globally so both upgrade and downgrade can reference it cleanly
relationship_type = sa.Enum(
    'FATHER',
    'MOTHER',
    'GRANDFATHER',
    'GRANDMOTHER',
    'GUARDIAN',
    'OTHER',
    name='relatioshiptype'
)

def upgrade() -> None:
    """Upgrade schema."""
    # 1. Create the custom Enum type in PostgreSQL BEFORE adding it to any columns
    relationship_type.create(op.get_bind(), checkfirst=True)

    # 2. Create the address table
    op.create_table('address',
        sa.Column('address_id', sa.UUID(), nullable=False),
        sa.Column('child_provience', sa.String(), nullable=True),
        sa.Column('child_district', sa.String(), nullable=True),
        sa.Column('child_municipality', sa.String(), nullable=True),
        sa.Column('child_ward_number', sa.Integer(), nullable=True),
        sa.Column('child_tole', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('address_id')
    )
    
    # 3. Modify nominee table columns
    op.add_column('nominee', sa.Column('nominee_first_name', sa.String(length=100), nullable=True))
    op.add_column('nominee', sa.Column('nominee_middle_name', sa.String(length=100), nullable=True))
    op.add_column('nominee', sa.Column('nominee_last_name', sa.String(length=100), nullable=True))
    
    # Now this will safely run because 'relatioshiptype' exists in the database
    op.add_column('nominee', sa.Column('nominee_relationship', relationship_type, nullable=True))
    
    op.drop_column('nominee', 'nominee_full_name')


def downgrade() -> None:
    """Downgrade schema."""
    # 1. Revert changes to nominee table columns
    op.add_column('nominee', sa.Column('nominee_full_name', sa.VARCHAR(length=100), autoincrement=False, nullable=True))
    op.drop_column('nominee', 'nominee_relationship')
    op.drop_column('nominee', 'nominee_last_name')
    op.drop_column('nominee', 'nominee_middle_name')
    op.drop_column('nominee', 'nominee_first_name')
    
    # 2. Drop the address table
    op.drop_table('address')

    # 3. Finally, drop the custom enum type safely
    relationship_type.drop(op.get_bind(), checkfirst=True)