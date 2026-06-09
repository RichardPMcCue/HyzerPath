"""add landing zones to round throws

Revision ID: b7e2d4f8c1a9
Revises: a3d9c8e1f5b2
Create Date: 2026-06-09 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7e2d4f8c1a9'
down_revision: Union[str, Sequence[str], None] = 'a3d9c8e1f5b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('round_throws', sa.Column('landing_zone', sa.String(), nullable=True))
    op.add_column('round_throws', sa.Column('drop_zone', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('round_throws', 'drop_zone')
    op.drop_column('round_throws', 'landing_zone')
