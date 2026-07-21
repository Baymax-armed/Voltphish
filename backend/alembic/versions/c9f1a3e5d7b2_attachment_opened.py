"""track attachment opens

Revision ID: c9f1a3e5d7b2
Revises: b8e2d4f6a1c3
Create Date: 2026-07-21 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c9f1a3e5d7b2'
down_revision: Union[str, None] = 'b8e2d4f6a1c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('results', schema=None) as batch_op:
        batch_op.add_column(sa.Column('attachment_opened_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('results', schema=None) as batch_op:
        batch_op.drop_column('attachment_opened_at')
