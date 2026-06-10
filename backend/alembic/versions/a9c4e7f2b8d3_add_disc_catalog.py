"""add disc catalog cache table

Revision ID: a9c4e7f2b8d3
Revises: f4b8a2c6e9d1
Create Date: 2026-06-10 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a9c4e7f2b8d3'
down_revision: Union[str, Sequence[str], None] = 'f4b8a2c6e9d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'disc_catalog',
        sa.Column('catalog_id', sa.Integer(), nullable=False),
        sa.Column('discit_id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('brand', sa.String(), nullable=True),
        sa.Column('category', sa.String(), nullable=True),
        sa.Column('speed', sa.String(), nullable=True),
        sa.Column('glide', sa.String(), nullable=True),
        sa.Column('turn', sa.String(), nullable=True),
        sa.Column('fade', sa.String(), nullable=True),
        sa.Column('stability', sa.String(), nullable=True),
        sa.Column('link', sa.String(), nullable=True),
        sa.Column('pic', sa.String(), nullable=True),
        sa.Column('color', sa.String(), nullable=True),
        sa.Column('background_color', sa.String(), nullable=True),
        sa.Column('fetched_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('catalog_id'),
        sa.UniqueConstraint('discit_id', name='uq_disc_catalog_discit_id'),
    )
    op.create_index('ix_disc_catalog_name', 'disc_catalog', ['name'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_disc_catalog_name', table_name='disc_catalog')
    op.drop_table('disc_catalog')
