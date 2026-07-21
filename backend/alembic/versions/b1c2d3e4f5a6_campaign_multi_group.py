"""multi target groups + exclusion groups per campaign (NG-001)

Revision ID: b1c2d3e4f5a6
Revises: a0b1c2d3e4f5
Create Date: 2026-07-21 23:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, None] = 'a0b1c2d3e4f5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for table in ("campaign_target_groups", "campaign_exclude_groups"):
        op.create_table(
            table,
            sa.Column("campaign_id", sa.Integer(), nullable=False),
            sa.Column("group_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["group_id"], ["groups.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("campaign_id", "group_id"),
        )

    # Backfill: every existing campaign targets its current primary group.
    op.execute(
        "INSERT INTO campaign_target_groups (campaign_id, group_id) "
        "SELECT id, group_id FROM campaigns WHERE group_id IS NOT NULL"
    )


def downgrade() -> None:
    op.drop_table("campaign_exclude_groups")
    op.drop_table("campaign_target_groups")
