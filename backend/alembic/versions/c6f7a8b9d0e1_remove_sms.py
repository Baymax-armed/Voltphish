"""remove SMS: drop sms_profiles table and campaigns.sms_profile_id

Revision ID: c6f7a8b9d0e1
Revises: b5e6f7a8c9d0
Create Date: 2026-07-21 18:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c6f7a8b9d0e1'
down_revision: Union[str, None] = 'b5e6f7a8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the FK column first (removes the dependency on sms_profiles), then the table.
    with op.batch_alter_table('campaigns', schema=None) as batch_op:
        batch_op.drop_column('sms_profile_id')
    op.drop_table('sms_profiles')


def downgrade() -> None:
    op.create_table(
        'sms_profiles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('provider', sa.String(length=20), nullable=False),
        sa.Column('from_number', sa.String(length=40), nullable=True),
        sa.Column('account', sa.String(length=255), nullable=True),
        sa.Column('config', sa.Text(), nullable=True),
        sa.Column('secret_enc', sa.String(length=1024), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('modified_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('campaigns', schema=None) as batch_op:
        batch_op.add_column(sa.Column('sms_profile_id', sa.Integer(), nullable=True))
