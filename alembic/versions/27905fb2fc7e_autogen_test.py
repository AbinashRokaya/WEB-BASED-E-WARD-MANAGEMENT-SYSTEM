"""autogen-test

Revision ID: 27905fb2fc7e
Revises: fe843bea651b
Create Date: 2026-06-11 21:45:11.778133

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
# Import the explicit PostgreSQL ENUM type helper
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = '27905fb2fc7e'
down_revision: Union[str, Sequence[str], None] = 'fe843bea651b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# -----------------------------
# ENUM DEFINITIONS (SAFE)
# -----------------------------
roleschema_enum = sa.Enum(
    'SuperAdmin',
    'Citizen',
    'WardChairperson',
    'WardSecretary',
    'DataValidationOfficer',
    name='roleschema'
)

registrationstatus_enum = sa.Enum(
    'Pending',
    'Approved',
    'Rejected',
    name='registrationstatus'
)


def upgrade() -> None:
    """Upgrade schema."""

    bind = op.get_bind()

    # -----------------------------
    # CREATE ENUMS SAFELY
    # -----------------------------
    roleschema_enum.create(bind, checkfirst=True)
    registrationstatus_enum.create(bind, checkfirst=True)

    # -----------------------------
    # CREATE TABLE
    # -----------------------------
    op.create_table(
        'users_verify',
        sa.Column('user_id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('user_name', sa.String(), nullable=True),
        sa.Column('user_phone_number', sa.String(), nullable=True),
        sa.Column('user_citizenship_number', sa.String(), nullable=True),
        sa.Column('user_provience', sa.String(), nullable=True),
        sa.Column('user_district', sa.String(), nullable=True),
        sa.Column('user_municipality', sa.String(), nullable=True),
        sa.Column('user_ward_number', sa.Integer(), nullable=True),

        # Force SQLAlchemy to skip generating CREATE TYPE via create_type=False
        sa.Column(
            'user_role',
            postgresql.ENUM('SuperAdmin', 'Citizen', 'WardChairperson', 'WardSecretary', 'DataValidationOfficer', name='roleschema', create_type=False),
            nullable=True
        ),

        sa.Column(
            'user_status',
            postgresql.ENUM('Pending', 'Approved', 'Rejected', name='registrationstatus', create_type=False),
            nullable=True
        ),

        sa.Column(
            'reated_at',
            sa.DateTime(),
            server_default=sa.text('now()'),
            nullable=True
        ),

        sa.Column(
            'updated_at',
            sa.DateTime(),
            server_default=sa.text('now()'),
            nullable=True
        ),
    )

    # -----------------------------
    # INDEXES
    # -----------------------------
    op.create_index(
        'ix_users_verify_user_citizenship_number',
        'users_verify',
        ['user_citizenship_number'],
        unique=True
    )

    op.create_index(
        'ix_users_verify_user_id',
        'users_verify',
        ['user_id'],
        unique=False
    )

    op.create_index(
        'ix_users_verify_user_name',
        'users_verify',
        ['user_name'],
        unique=True
    )

    op.create_index(
        'ix_users_verify_user_phone_number',
        'users_verify',
        ['user_phone_number'],
        unique=True
    )


def downgrade() -> None:
    """Downgrade schema."""

    # -----------------------------
    # DROP TABLE
    # -----------------------------
    op.drop_table('users_verify')

    bind = op.get_bind()

    # -----------------------------
    # DROP ENUMS SAFELY
    # -----------------------------
    registrationstatus_enum.drop(bind, checkfirst=True)
    roleschema_enum.drop(bind, checkfirst=True)