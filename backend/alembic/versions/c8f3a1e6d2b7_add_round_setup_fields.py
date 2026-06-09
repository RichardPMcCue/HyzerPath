"""add round setup fields

Revision ID: c8f3a1e6d2b7
Revises: b7e2d4f8c1a9
Create Date: 2026-06-09 17:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c8f3a1e6d2b7'
down_revision: Union[str, Sequence[str], None] = 'b7e2d4f8c1a9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('rounds', sa.Column('tracking_mode', sa.String(), nullable=False, server_default='lies'))
    op.add_column('rounds', sa.Column('layout', sa.String(), nullable=False, server_default='full'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('rounds', 'layout')
    op.drop_column('rounds', 'tracking_mode')
