"""add human_decision to decisions

The Week-5 flat schema omitted human_decision, but Week 7's approval gate
(db.set_human_decision) and Week 8's queue assertion both depend on it.
Restore it now so those weeks need no schema scramble.

Revision ID: d2b3c4e5f6a7
Revises: c1a2b3d4e5f6
Create Date: 2026-06-29 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd2b3c4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'c1a2b3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('decisions', sa.Column(
        'human_decision', sa.String(length=16),
        nullable=False, server_default='pending',
    ))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('decisions', 'human_decision')
