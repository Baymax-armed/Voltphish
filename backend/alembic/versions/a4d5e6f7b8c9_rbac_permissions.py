"""granular RBAC: per-user extra permissions

Revision ID: a4d5e6f7b8c9
Revises: f3c4d5e6a7b8
Create Date: 2026-07-21 16:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a4d5e6f7b8c9'
down_revision: Union[str, None] = 'f3c4d5e6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('extra_permissions', sa.String(length=500), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('extra_permissions')
