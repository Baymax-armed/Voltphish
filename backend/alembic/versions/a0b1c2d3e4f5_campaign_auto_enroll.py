"""per-campaign auto-enroll on failure (trigger/module/email)

Revision ID: a0b1c2d3e4f5
Revises: f9a0b1c2d3e4
Create Date: 2026-07-21 22:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a0b1c2d3e4f5'
down_revision: Union[str, None] = 'f9a0b1c2d3e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('campaigns', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('auto_enroll_trigger', sa.String(length=12), nullable=False, server_default='off')
        )
        batch_op.add_column(sa.Column('auto_enroll_module_id', sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column('auto_enroll_email', sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.create_foreign_key(
            'fk_campaigns_auto_enroll_module', 'training_modules',
            ['auto_enroll_module_id'], ['id'], ondelete='SET NULL',
        )


def downgrade() -> None:
    with op.batch_alter_table('campaigns', schema=None) as batch_op:
        batch_op.drop_constraint('fk_campaigns_auto_enroll_module', type_='foreignkey')
        batch_op.drop_column('auto_enroll_email')
        batch_op.drop_column('auto_enroll_module_id')
        batch_op.drop_column('auto_enroll_trigger')
