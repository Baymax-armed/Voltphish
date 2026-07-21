"""VAP: mark high-value targets (VIP)

Revision ID: b5e6f7a8c9d0
Revises: a4d5e6f7b8c9
Create Date: 2026-07-21 17:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b5e6f7a8c9d0'
down_revision: Union[str, None] = 'a4d5e6f7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('targets', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_vip', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    with op.batch_alter_table('targets', schema=None) as batch_op:
        batch_op.drop_column('is_vip')
