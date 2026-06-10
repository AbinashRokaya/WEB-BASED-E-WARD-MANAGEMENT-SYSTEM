"""add new table otpcode

Revision ID: 6c89a4fd4cd2
Revises: 37a96f117e36
Create Date: 2026-06-10 18:57:21.259559

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6c89a4fd4cd2'
down_revision: Union[str, Sequence[str], None] = '37a96f117e36'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Declare the enum properties at the top of the file or inside the function
role_enum = sa.Enum('SuperAdmin', 'Citizen', 'WardChairperson', 'WardSecretary', 'DataValidationOfficer', name='roleschema')

def upgrade() -> None:
    # 1. Create the custom ENUM type in PostgreSQL first
    role_enum.create(op.get_bind(), checkfirst=True)
    
    # 2. Your existing logic to add the column (and any other operations)
    op.add_column('users', sa.Column('user_role', role_enum, nullable=True))
    # ... rest of your upgrade code ...


def downgrade() -> None:
    # 1. Drop the column first
    op.drop_column('users', 'user_role')
    
    # 2. Drop the custom ENUM type from PostgreSQL
    role_enum.drop(op.get_bind(), checkfirst=True)
    # ... rest of your downgrade code ...
