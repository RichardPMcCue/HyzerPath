"""add throw style to measurements, round throws, and disc stats

Revision ID: c7f1a3e8d2b5
Revises: b2e6d9f4a7c1
Create Date: 2026-06-10 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7f1a3e8d2b5'
down_revision: Union[str, Sequence[str], None] = 'b2e6d9f4a7c1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('throw_measurements', sa.Column('throw_style', sa.String(), nullable=True))
    op.add_column('round_throws', sa.Column('throw_style', sa.String(), nullable=True))
    op.add_column('user_disc_stats', sa.Column(
        'throw_style', sa.String(), nullable=False, server_default='backhand'
    ))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('user_disc_stats', 'throw_style')
    op.drop_column('round_throws', 'throw_style')
    op.drop_column('throw_measurements', 'throw_style')
