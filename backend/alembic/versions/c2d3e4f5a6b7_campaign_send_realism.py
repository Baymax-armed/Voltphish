"""send-time realism: jitter, business-hours, timezone (NG-010)

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-07-22 00:15:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c2d3e4f5a6b7'
down_revision: Union[str, None] = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('campaigns', schema=None) as batch_op:
        batch_op.add_column(sa.Column('send_jitter', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('business_hours_only', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('send_timezone', sa.String(length=64), nullable=False, server_default=''))


def downgrade() -> None:
    with op.batch_alter_table('campaigns', schema=None) as batch_op:
        batch_op.drop_column('send_timezone')
        batch_op.drop_column('business_hours_only')
        batch_op.drop_column('send_jitter')
