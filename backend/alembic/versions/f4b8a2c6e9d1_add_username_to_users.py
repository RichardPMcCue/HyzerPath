"""add username to users

Revision ID: f4b8a2c6e9d1
Revises: c8f3a1e6d2b7
Create Date: 2026-06-10 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f4b8a2c6e9d1'
down_revision: Union[str, Sequence[str], None] = 'c8f3a1e6d2b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('username', sa.String(), nullable=True))
    op.create_unique_constraint('uq_users_username', 'users', ['username'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('uq_users_username', 'users', type_='unique')
    op.drop_column('users', 'username')
