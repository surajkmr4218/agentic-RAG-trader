"""drop backtest (eval_runs) + reshape outcomes for live reconciliation

Week-5 sessions 4-5 (backtest/calibration) are deferred. Remove the backtest-only
eval_runs table and reshape outcomes from the backtest-scored shape
(entry/exit/ret/spy_ret/correct) to the live Week-7 reconciliation shape
(fill_price/forward_return/spy_return, nullable). decisions/orders are unchanged —
they are the live trading schema.

Revision ID: e3c4d5f6a7b8
Revises: d2b3c4e5f6a7
Create Date: 2026-06-29 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e3c4d5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'd2b3c4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_table('eval_runs')

    op.drop_index(op.f('ix_outcomes_decision_id'), table_name='outcomes')
    op.drop_table('outcomes')
    op.create_table(
        'outcomes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('decision_id', sa.String(length=64), nullable=False),
        sa.Column('fill_price', sa.Float(), nullable=True),
        sa.Column('forward_return', sa.Float(), nullable=True),
        sa.Column('spy_return', sa.Float(), nullable=True),
        sa.Column('horizon_days', sa.Integer(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['decision_id'], ['decisions.decision_id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_outcomes_decision_id'), 'outcomes', ['decision_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema — restore the backtest-scored outcomes + eval_runs."""
    op.drop_index(op.f('ix_outcomes_decision_id'), table_name='outcomes')
    op.drop_table('outcomes')
    op.create_table(
        'outcomes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('decision_id', sa.String(length=64), nullable=False),
        sa.Column('horizon_days', sa.Integer(), nullable=False),
        sa.Column('entry_price', sa.Float(), nullable=False),
        sa.Column('exit_price', sa.Float(), nullable=False),
        sa.Column('ret', sa.Float(), nullable=False),
        sa.Column('spy_ret', sa.Float(), nullable=False),
        sa.Column('correct', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['decision_id'], ['decisions.decision_id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_outcomes_decision_id'), 'outcomes', ['decision_id'], unique=False)

    op.create_table(
        'eval_runs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('kind', sa.String(length=32), nullable=False),
        sa.Column('n_filings', sa.Integer(), nullable=False),
        sa.Column('horizon_days', sa.Integer(), nullable=False),
        sa.Column('hit_rate', sa.Float(), nullable=False),
        sa.Column('sharpe', sa.Float(), nullable=False),
        sa.Column('mean_excess_ret', sa.Float(), nullable=False),
        sa.Column('params', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
