"""webhook delivery health (last_status/error/attempt)

Revision ID: f9a0b1c2d3e4
Revises: e8f9a0b1c2d3
Create Date: 2026-07-21 21:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f9a0b1c2d3e4'
down_revision: Union[str, None] = 'e8f9a0b1c2d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('webhooks', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_status', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('last_error', sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column('last_attempt_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('webhooks', schema=None) as batch_op:
        batch_op.drop_column('last_attempt_at')
        batch_op.drop_column('last_error')
        batch_op.drop_column('last_status')
