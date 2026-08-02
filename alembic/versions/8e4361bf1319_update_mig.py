"""update mig

Revision ID: 8e4361bf1319
Revises: 5915b33b3d46
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '8e4361bf1319'
down_revision = '5915b33b3d46'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        'migration_applicant', 'applicant_dob_bs',
        existing_type=postgresql.TIMESTAMP(),
        type_=sa.String(length=10),
        existing_nullable=False,
        postgresql_using="to_char(applicant_dob_bs, 'YYYY-MM-DD')",
    )
    op.alter_column(
        'migration_detail', 'migration_date_bs',
        existing_type=postgresql.TIMESTAMP(),
        type_=sa.String(length=10),
        existing_nullable=True,
        postgresql_using="to_char(migration_date_bs, 'YYYY-MM-DD')",
    )
    op.alter_column(
        'migration_family_member', 'member_dob_bs',
        existing_type=postgresql.TIMESTAMP(),
        type_=sa.String(length=10),
        existing_nullable=True,
        postgresql_using="to_char(member_dob_bs, 'YYYY-MM-DD')",
    )


def downgrade():
    op.alter_column(
        'migration_applicant', 'applicant_dob_bs',
        existing_type=sa.String(length=10),
        type_=postgresql.TIMESTAMP(),
        existing_nullable=False,
    )
    op.alter_column(
        'migration_detail', 'migration_date_bs',
        existing_type=sa.String(length=10),
        type_=postgresql.TIMESTAMP(),
        existing_nullable=True,
    )
    op.alter_column(
        'migration_family_member', 'member_dob_bs',
        existing_type=sa.String(length=10),
        type_=postgresql.TIMESTAMP(),
        existing_nullable=True,
    )