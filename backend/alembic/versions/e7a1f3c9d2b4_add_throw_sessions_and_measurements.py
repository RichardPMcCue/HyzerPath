"""add throw sessions and measurements

Revision ID: e7a1f3c9d2b4
Revises: 2ff0fc5dd10a
Create Date: 2026-06-09 14:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e7a1f3c9d2b4'
down_revision: Union[str, Sequence[str], None] = '2ff0fc5dd10a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'throw_sessions',
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('label', sa.String(), nullable=True),
        sa.Column('start_latitude', sa.Float(), nullable=False),
        sa.Column('start_longitude', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id']),
        sa.PrimaryKeyConstraint('session_id'),
    )
    op.create_table(
        'throw_measurements',
        sa.Column('throw_id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('disc_id', sa.Integer(), nullable=True),
        sa.Column('end_latitude', sa.Float(), nullable=False),
        sa.Column('end_longitude', sa.Float(), nullable=False),
        sa.Column('distance_ft', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['throw_sessions.session_id']),
        sa.ForeignKeyConstraint(['disc_id'], ['discs.disc_id']),
        sa.PrimaryKeyConstraint('throw_id'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('throw_measurements')
    op.drop_table('throw_sessions')
