"""training LMS (modules, quiz questions, enrollments)

Revision ID: f3c4d5e6a7b8
Revises: e2b3c4d5f6a7
Create Date: 2026-07-21 15:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f3c4d5e6a7b8'
down_revision: Union[str, None] = 'e2b3c4d5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'training_modules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=160), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('category', sa.String(length=60), nullable=False, server_default='General'),
        sa.Column('difficulty', sa.Enum('beginner', 'intermediate', 'advanced', name='difficulty'),
                  nullable=False, server_default='beginner'),
        sa.Column('content_html', sa.Text(), nullable=False, server_default=''),
        sa.Column('video_url', sa.String(length=500), nullable=True),
        sa.Column('estimated_minutes', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('pass_score', sa.Integer(), nullable=False, server_default='80'),
        sa.Column('points', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('is_published', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('modified_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'quiz_questions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('module_id', sa.Integer(), nullable=False),
        sa.Column('prompt', sa.Text(), nullable=False),
        sa.Column('options', sa.Text(), nullable=False, server_default='[]'),
        sa.Column('correct_index', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('order', sa.Integer(), nullable=False, server_default='0'),
        sa.ForeignKeyConstraint(['module_id'], ['training_modules.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'training_enrollments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('module_id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=320), nullable=False),
        sa.Column('token', sa.String(length=64), nullable=False),
        sa.Column('status', sa.Enum('assigned', 'in_progress', 'completed', 'failed', name='enrollmentstatus'),
                  nullable=False, server_default='assigned'),
        sa.Column('score', sa.Integer(), nullable=True),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('campaign_id', sa.Integer(), nullable=True),
        sa.Column('assigned_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['module_id'], ['training_modules.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token'),
    )
    op.create_index('ix_training_enrollments_module_id', 'training_enrollments', ['module_id'])
    op.create_index('ix_training_enrollments_email', 'training_enrollments', ['email'])
    op.create_index('ix_training_enrollments_token', 'training_enrollments', ['token'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_training_enrollments_token', table_name='training_enrollments')
    op.drop_index('ix_training_enrollments_email', table_name='training_enrollments')
    op.drop_index('ix_training_enrollments_module_id', table_name='training_enrollments')
    op.drop_table('training_enrollments')
    op.drop_table('quiz_questions')
    op.drop_table('training_modules')
