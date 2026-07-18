"""migration certificate 1

Revision ID: 64fbb90c56bb
Revises: 5e46ba75914e
Create Date: 2026-07-18 12:42:01.478946

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '64fbb90c56bb'
down_revision: Union[str, Sequence[str], None] = '5e46ba75914e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    """Upgrade schema."""
    
    # ─── 1. SAFE POSTGRESQL ENUM CREATION ───
    # This creates the types ONLY if they don't already exist in the database catalog.
    bind = op.get_bind()
    
    bind.execute(sa.text("""
        DO $$ 
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'migrationregistrationstatus') THEN
                CREATE TYPE migrationregistrationstatus AS ENUM ('DRAFT', 'SUBMITTED', 'APPROVED', 'REJECTED');
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'migrationaddresstype') THEN
                CREATE TYPE migrationaddresstype AS ENUM ('PERMANENT', 'CURRENT', 'NEW');
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'migrationreasontype') THEN
                CREATE TYPE migrationreasontype AS ENUM ('EMPLOYMENT', 'STUDY', 'BUSINESS', 'MARRIAGE', 'SETTLEMENT', 'OTHER');
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'gendertype') THEN
                CREATE TYPE gendertype AS ENUM ('MALE', 'FEMALE', 'OTHERS');
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'relatioshiptype') THEN
                CREATE TYPE relatioshiptype AS ENUM ('FATHER', 'MOTHER', 'GRANDFATHER', 'GRANDMOTHER', 'GUARDIAN', 'OTHER');
            END IF;
        END $$;
    """))

    # ─── 2. CREATE TABLES (USING EXISTING POSTGRES TYPES) ───
    # We replace sa.Enum with postgresql.ENUM and set create_type=False to tell SQLAlchemy 
    # "Don't touch the type system, just use the name strings we already set up above."
    
    op.create_table('migration_registration',
    sa.Column('migration_id', sa.UUID(), nullable=False),
    sa.Column('register_ward_id', sa.UUID(), nullable=False),
    sa.Column('register_submitted_by', sa.Integer(), nullable=False),
    sa.Column('register_status', postgresql.ENUM('DRAFT', 'SUBMITTED', 'APPROVED', 'REJECTED', name='migrationregistrationstatus', create_type=False), nullable=False),
    sa.Column('enclosure_citizenship_copy', sa.Boolean(), nullable=False),
    sa.Column('enclosure_address_proof', sa.Boolean(), nullable=False),
    sa.Column('enclosure_destination_proof', sa.Boolean(), nullable=False),
    sa.Column('enclosure_photo_count', sa.Integer(), nullable=True),
    sa.Column('enclosure_other', sa.String(length=200), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['register_submitted_by'], ['users.user_id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['register_ward_id'], ['ward.ward_id'], ),
    sa.PrimaryKeyConstraint('migration_id')
    )
    
    op.create_table('migration_address',
    sa.Column('address_id', sa.UUID(), nullable=False),
    sa.Column('migration_id', sa.UUID(), nullable=False),
    sa.Column('address_type', postgresql.ENUM('PERMANENT', 'CURRENT', 'NEW', name='migrationaddresstype', create_type=False), nullable=False),
    sa.Column('province', sa.String(length=100), nullable=True),
    sa.Column('district', sa.String(length=100), nullable=True),
    sa.Column('municipality', sa.String(length=100), nullable=True),
    sa.Column('ward_number', sa.Integer(), nullable=True),
    sa.Column('tole', sa.String(length=200), nullable=True),
    sa.ForeignKeyConstraint(['migration_id'], ['migration_registration.migration_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('address_id')
    )
    
    op.create_table('migration_applicant',
    sa.Column('applicant_id', sa.UUID(), nullable=False),
    sa.Column('migration_id', sa.UUID(), nullable=False),
    sa.Column('applicant_full_name_np', sa.String(length=200), nullable=False),
    sa.Column('applicant_full_name_en', sa.String(length=200), nullable=False),
    sa.Column('applicant_gender', postgresql.ENUM('MALE', 'FEMALE', 'OTHERS', name='gendertype', create_type=False), nullable=False),
    sa.Column('applicant_dob_bs', sa.DateTime(), nullable=False),
    sa.Column('applicant_dob_ad', sa.DateTime(), nullable=True),
    sa.Column('applicant_citizenship_no', sa.String(length=50), nullable=False),
    sa.Column('applicant_nationality', sa.String(length=100), nullable=False),
    sa.Column('applicant_occupation', sa.String(length=100), nullable=True),
    sa.Column('applicant_contact_no', sa.String(length=50), nullable=True),
    sa.ForeignKeyConstraint(['migration_id'], ['migration_registration.migration_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('applicant_id')
    )
    
    op.create_table('migration_certificate',
    sa.Column('cert_id', sa.UUID(), nullable=False),
    sa.Column('migration_id', sa.UUID(), nullable=False),
    sa.Column('certificate_no', sa.String(length=100), nullable=False),
    sa.Column('data_hash', sa.String(length=64), nullable=False),
    sa.Column('qr_path', sa.String(), nullable=True),
    sa.Column('pdf_path', sa.String(), nullable=True),
    sa.Column('issued_by', sa.Integer(), nullable=True),
    sa.Column('is_valid', sa.Boolean(), nullable=False),
    sa.Column('revoked_reason', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['issued_by'], ['users.user_id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['migration_id'], ['migration_registration.migration_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('cert_id'),
    sa.UniqueConstraint('certificate_no'),
    sa.UniqueConstraint('migration_id')
    )
    
    op.create_table('migration_detail',
    sa.Column('migration_detail_id', sa.UUID(), nullable=False),
    sa.Column('migration_id', sa.UUID(), nullable=False),
    sa.Column('migration_date_bs', sa.DateTime(), nullable=True),
    sa.Column('migration_date_ad', sa.DateTime(), nullable=True),
    sa.Column('migration_reason', postgresql.ENUM('EMPLOYMENT', 'STUDY', 'BUSINESS', 'MARRIAGE', 'SETTLEMENT', 'OTHER', name='migrationreasontype', create_type=False), nullable=False),
    sa.Column('migration_reason_other', sa.String(length=200), nullable=True),
    sa.ForeignKeyConstraint(['migration_id'], ['migration_registration.migration_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('migration_detail_id'),
    sa.UniqueConstraint('migration_id')
    )
    
    op.create_table('migration_family_member',
    sa.Column('family_member_id', sa.UUID(), nullable=False),
    sa.Column('migration_id', sa.UUID(), nullable=False),
    sa.Column('member_name_np', sa.String(length=200), nullable=True),
    sa.Column('member_name_en', sa.String(length=200), nullable=True),
    sa.Column('member_relationship', postgresql.ENUM('FATHER', 'MOTHER', 'GRANDFATHER', 'GRANDMOTHER', 'GUARDIAN', 'OTHER', name='relatioshiptype', create_type=False), nullable=True),
    sa.Column('member_gender', postgresql.ENUM('MALE', 'FEMALE', 'OTHERS', name='gendertype', create_type=False), nullable=True),
    sa.Column('member_dob_bs', sa.DateTime(), nullable=True),
    sa.Column('member_dob_ad', sa.DateTime(), nullable=True),
    sa.Column('member_citizenship_no', sa.String(length=50), nullable=True),
    sa.Column('member_remarks', sa.String(length=200), nullable=True),
    sa.ForeignKeyConstraint(['migration_id'], ['migration_registration.migration_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('family_member_id')
    )
    
    op.create_table('migration_reject',
    sa.Column('reject_id', sa.UUID(), nullable=False),
    sa.Column('reject_text', sa.Text(), nullable=True),
    sa.Column('migration_id', sa.UUID(), nullable=False),
    sa.ForeignKeyConstraint(['migration_id'], ['migration_registration.migration_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('reject_id')
    )