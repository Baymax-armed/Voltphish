"""settings key/value table

Revision ID: b8e2d4f6a1c3
Revises: a7c3f1e9b2d4
Create Date: 2026-07-20 17:20:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b8e2d4f6a1c3'
down_revision: Union[str, None] = 'a7c3f1e9b2d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'settings',
        sa.Column('key', sa.String(length=64), nullable=False),
        sa.Column('value', sa.Text(), nullable=True),
        sa.Column('modified_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('key'),
    )


def downgrade() -> None:
    op.drop_table('settings')
