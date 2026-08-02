"""fix complaintstatus enum values

Revision ID: 751665bdb53c
Revises: 203faab75138
Create Date: ...

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '751665bdb53c'
down_revision: Union[str, Sequence[str], None] = '203faab75138'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Rename the old enum type out of the way
    op.execute("ALTER TYPE complaintstatus RENAME TO complaintstatus_old")

    # 2. Create the new type with the correct values
    op.execute("""
        CREATE TYPE complaintstatus AS ENUM (
            'DRAFT', 'SUBMITTED', 'APPROVED', 'VERIFIED', 'RESOLVED', 'REJECTED'
        )
    """)

    # 3. Change the column to the new type, remapping old values to new
    #    ones inside the same USING expression — this is the step that
    #    actually needs to happen atomically, since you can't write a
    #    new-type value into an old-type column beforehand.
    op.execute("""
        ALTER TABLE complaint
        ALTER COLUMN complaint_status
        TYPE complaintstatus
        USING (
            CASE complaint_status::text
                WHEN 'UNDER_REVIEW' THEN 'APPROVED'
                WHEN 'FORWARDED'    THEN 'VERIFIED'
                WHEN 'ESCALATED'    THEN 'VERIFIED'
                ELSE complaint_status::text
            END
        )::complaintstatus
    """)

    # 4. Fix the column default, since it still references the old type
    op.execute("""
        ALTER TABLE complaint
        ALTER COLUMN complaint_status
        SET DEFAULT 'SUBMITTED'::complaintstatus
    """)

    # 5. Drop the old type
    op.execute("DROP TYPE complaintstatus_old")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("ALTER TYPE complaintstatus RENAME TO complaintstatus_new")

    op.execute("""
        CREATE TYPE complaintstatus AS ENUM (
            'SUBMITTED', 'UNDER_REVIEW', 'FORWARDED', 'RESOLVED', 'REJECTED', 'ESCALATED'
        )
    """)

    op.execute("""
        ALTER TABLE complaint
        ALTER COLUMN complaint_status
        TYPE complaintstatus
        USING (
            CASE complaint_status::text
                WHEN 'DRAFT'    THEN 'SUBMITTED'
                WHEN 'APPROVED' THEN 'UNDER_REVIEW'
                WHEN 'VERIFIED' THEN 'FORWARDED'
                ELSE complaint_status::text
            END
        )::complaintstatus
    """)

    op.execute("""
        ALTER TABLE complaint
        ALTER COLUMN complaint_status
        SET DEFAULT 'SUBMITTED'::complaintstatus
    """)

    op.execute("DROP TYPE complaintstatus_new")