"""add polygon to hole hazards

Revision ID: b2e6d9f4a7c1
Revises: a9c4e7f2b8d3
Create Date: 2026-06-10 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2e6d9f4a7c1'
down_revision: Union[str, Sequence[str], None] = 'a9c4e7f2b8d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('hole_hazards', sa.Column('polygon', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('hole_hazards', 'polygon')
