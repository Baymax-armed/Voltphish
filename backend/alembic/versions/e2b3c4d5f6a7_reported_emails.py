"""reported emails (report-phish add-in)

Revision ID: e2b3c4d5f6a7
Revises: d1a2b3c4e5f6
Create Date: 2026-07-21 14:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e2b3c4d5f6a7'
down_revision: Union[str, None] = 'd1a2b3c4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'reported_emails',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('reporter_email', sa.String(length=320), nullable=True),
        sa.Column('subject', sa.String(length=998), nullable=True),
        sa.Column('sender', sa.String(length=320), nullable=True),
        sa.Column('body_preview', sa.Text(), nullable=True),
        sa.Column('headers', sa.Text(), nullable=True),
        sa.Column('source', sa.String(length=16), nullable=False, server_default='addin'),
        sa.Column('is_simulation', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('matched_rid', sa.String(length=64), nullable=True),
        sa.Column('matched_result_id', sa.Integer(), nullable=True),
        sa.Column(
            'status',
            sa.Enum('new', 'reviewing', 'malicious', 'benign', 'closed', name='reportstatus'),
            nullable=False,
            server_default='new',
        ),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_reported_emails_reporter_email', 'reported_emails', ['reporter_email'])


def downgrade() -> None:
    op.drop_index('ix_reported_emails_reporter_email', table_name='reported_emails')
    op.drop_table('reported_emails')
