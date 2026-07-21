"""admin two-factor auth (TOTP)

Revision ID: d1a2b3c4e5f6
Revises: c9f1a3e5d7b2
Create Date: 2026-07-21 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd1a2b3c4e5f6'
down_revision: Union[str, None] = 'c9f1a3e5d7b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('totp_secret_enc', sa.String(length=255), nullable=True))
        batch_op.add_column(
            sa.Column('totp_enabled', sa.Boolean(), server_default=sa.false(), nullable=False)
        )


def downgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('totp_enabled')
        batch_op.drop_column('totp_secret_enc')
