"""ensure notice_attachment_path column exists

Revision ID: <new_id>
Revises: bf982a77e568
"""
from alembic import op

revision ="f613e726ea8e"
down_revision = "bf982a77e568"
branch_labels = None
depends_on = None


def upgrade():
    # Rename old column if it's still there under the old name
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='notices' AND column_name='notice_image_path'
            ) AND NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='notices' AND column_name='notice_attachment_path'
            ) THEN
                ALTER TABLE notices RENAME COLUMN notice_image_path TO notice_attachment_path;
            END IF;
        END $$;
    """)

    # If neither old nor new column exists, just add it fresh
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='notices' AND column_name='notice_attachment_path'
            ) THEN
                ALTER TABLE notices ADD COLUMN notice_attachment_path VARCHAR;
            END IF;
        END $$;
    """)


def downgrade():
    op.execute("ALTER TABLE notices DROP COLUMN IF EXISTS notice_attachment_path;")