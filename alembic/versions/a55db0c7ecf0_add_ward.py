"""add ward

Revision ID: a55db0c7ecf0
Revises: bcab25d3982d
Create Date: 2026-07-12 01:46:56.655165

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


"""add ward_type to ward

Revision ID: a55db0c7ecf0
Revises: bcab25d3982d
Create Date: ...
"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a55db0c7ecf0"
down_revision = "bcab25d3982d"
branch_labels = None
depends_on = None

ward_type_enum = sa.Enum(
    "METROPOLITAN_CITY",
    "SUB_METROPOLITAN_CITY",
    "MUNICIPALITY",
    "RURAL_MUNICIPALITY",
    name="municipalitytype",
)


def upgrade():
    bind = op.get_bind()
    # Create the Postgres enum type first — this is the step that was missing.
    ward_type_enum.create(bind, checkfirst=True)

    # nullable=True first since existing ward rows have no value yet
    op.add_column(
        "ward",
        sa.Column(
            "ward_type",
            sa.Enum(
                "METROPOLITAN_CITY",
                "SUB_METROPOLITAN_CITY",
                "MUNICIPALITY",
                "RURAL_MUNICIPALITY",
                name="municipalitytype",
                create_type=False,  # type already created above, don't redo it
            ),
            nullable=True,
        ),
    )

    op.execute("UPDATE ward SET ward_type = 'MUNICIPALITY' WHERE ward_type IS NULL")

    op.alter_column("ward", "ward_type", nullable=False)


def downgrade():
    op.drop_column("ward", "ward_type")
    ward_type_enum.drop(op.get_bind(), checkfirst=True)