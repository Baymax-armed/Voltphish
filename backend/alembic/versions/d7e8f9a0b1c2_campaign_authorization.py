"""governance: campaign launch authorization

Revision ID: d7e8f9a0b1c2
Revises: c6f7a8b9d0e1
Create Date: 2026-07-21 19:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd7e8f9a0b1c2'
down_revision: Union[str, None] = 'c6f7a8b9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('campaigns', schema=None) as batch_op:
        batch_op.add_column(sa.Column('authorized_by', sa.String(length=320), nullable=True))
        batch_op.add_column(sa.Column('authorization_ref', sa.String(length=500), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('campaigns', schema=None) as batch_op:
        batch_op.drop_column('authorization_ref')
        batch_op.drop_column('authorized_by')
