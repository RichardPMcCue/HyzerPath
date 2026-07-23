"""add estimated_drive_ft to users

Revision ID: e5a1c9d3f0b2
Revises: d4f7a9c2e1b8
Create Date: 2026-07-23 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e5a1c9d3f0b2'
down_revision: Union[str, Sequence[str], None] = 'd4f7a9c2e1b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('estimated_drive_ft', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'estimated_drive_ft')
