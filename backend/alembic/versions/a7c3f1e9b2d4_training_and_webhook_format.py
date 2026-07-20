"""training acknowledgment + webhook format

Revision ID: a7c3f1e9b2d4
Revises: 4b10489294d9
Create Date: 2026-07-20 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a7c3f1e9b2d4'
down_revision: Union[str, None] = '4b10489294d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # When did this recipient acknowledge the just-in-time training page?
    with op.batch_alter_table('results', schema=None) as batch_op:
        batch_op.add_column(sa.Column('trained_at', sa.DateTime(), nullable=True))

    # Payload format for outbound webhooks: 'generic' (signed JSON), 'slack', 'teams'.
    with op.batch_alter_table('webhooks', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('format', sa.String(length=20), nullable=False, server_default='generic')
        )


def downgrade() -> None:
    with op.batch_alter_table('webhooks', schema=None) as batch_op:
        batch_op.drop_column('format')

    with op.batch_alter_table('results', schema=None) as batch_op:
        batch_op.drop_column('trained_at')
