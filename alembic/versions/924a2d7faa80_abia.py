# alembic/versions/924a2d7faa80_abia.py

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '924a2d7faa80'
down_revision = '93cdd777e7c9'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # 1. Create the new ENUM type explicitly in PostgreSQL
    old_enum = postgresql.ENUM('Pending', 'Approved', 'Rejected', name='registrationstatus')
    new_enum = sa.Enum('DRAFT', 'SUBMITTED', 'DOCUMENT_REQUESTED', 'APPROVED', 'CERTIFICATE_ISSUED', 'REJECTED', name='birthregistrationstatus')
    
    new_enum.create(op.get_bind(), checkfirst=True)

    # 2. Alter the column to use the new ENUM type
    # Note: If old values don't map cleanly to the new ones, you might need a USING clause,
    # but let's try the direct type switch first.
    op.alter_column('birth_registration', 'register_status',
               existing_type=old_enum,
               type_=new_enum,
               existing_nullable=False,
               # Adding postgresql_using maps existing values if necessary
               postgresql_using="register_status::text::birthregistrationstatus" 
    )


def downgrade() -> None:
    old_enum = postgresql.ENUM('Pending', 'Approved', 'Rejected', name='registrationstatus')
    new_enum = sa.Enum('DRAFT', 'SUBMITTED', 'DOCUMENT_REQUESTED', 'APPROVED', 'CERTIFICATE_ISSUED', 'REJECTED', name='birthregistrationstatus')

    # 1. Revert the column type back to the old ENUM
    op.alter_column('birth_registration', 'register_status',
               existing_type=new_enum,
               type_=old_enum,
               existing_nullable=False,
               postgresql_using="register_status::text::registrationstatus"
    )

    # 2. Drop the new ENUM type
    new_enum.drop(op.get_bind(), checkfirst=True)