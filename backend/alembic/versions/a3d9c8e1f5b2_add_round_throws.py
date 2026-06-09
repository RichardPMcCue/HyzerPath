"""add round throws

Revision ID: a3d9c8e1f5b2
Revises: e7a1f3c9d2b4
Create Date: 2026-06-09 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3d9c8e1f5b2'
down_revision: Union[str, Sequence[str], None] = 'e7a1f3c9d2b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'round_throws',
        sa.Column('round_throw_id', sa.Integer(), nullable=False),
        sa.Column('round_id', sa.Integer(), nullable=False),
        sa.Column('hole_id', sa.Integer(), nullable=False),
        sa.Column('throw_number', sa.Integer(), nullable=False),
        sa.Column('disc_id', sa.Integer(), nullable=True),
        sa.Column('start_latitude', sa.Float(), nullable=True),
        sa.Column('start_longitude', sa.Float(), nullable=True),
        sa.Column('end_latitude', sa.Float(), nullable=True),
        sa.Column('end_longitude', sa.Float(), nullable=True),
        sa.Column('distance_ft', sa.Float(), nullable=True),
        sa.Column('is_holed', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['round_id'], ['rounds.round_id']),
        sa.ForeignKeyConstraint(['hole_id'], ['holes.hole_id']),
        sa.ForeignKeyConstraint(['disc_id'], ['discs.disc_id']),
        sa.PrimaryKeyConstraint('round_throw_id'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('round_throws')
