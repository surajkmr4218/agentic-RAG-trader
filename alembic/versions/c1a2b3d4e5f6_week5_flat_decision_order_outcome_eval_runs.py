"""week5: flat decision/order/outcome + eval_runs

Rebuilds decisions/orders/outcomes from the Week-1 normalized shape into the flat
Week-5 reasoning-trail shape that app/agents/logging.py writes, and adds eval_runs
for the backtest. The three tables are dropped and recreated: they carry no data
yet (logging.py never ran against the old schema), so nothing is lost.

Revision ID: c1a2b3d4e5f6
Revises: a5e5b9b6d326
Create Date: 2026-06-29 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1a2b3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'a5e5b9b6d326'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Drop children first (FKs point at decisions / orders).
    op.drop_index(op.f('ix_outcomes_order_id'), table_name='outcomes')
    op.drop_table('outcomes')
    op.drop_table('orders')
    op.drop_index(op.f('ix_decisions_user_id'), table_name='decisions')
    op.drop_table('decisions')

    op.create_table(
        'decisions',
        sa.Column('decision_id', sa.String(length=64), nullable=False),
        sa.Column('ticker', sa.String(length=16), nullable=False),
        sa.Column('hypothesis', sa.JSON(), nullable=False),
        sa.Column('critic_verdict', sa.JSON(), nullable=True),
        sa.Column('guardrail', sa.JSON(), nullable=False),
        sa.Column('passed', sa.Boolean(), nullable=False),
        sa.Column('user_id', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('decision_id'),
    )
    op.create_index(op.f('ix_decisions_ticker'), 'decisions', ['ticker'], unique=False)

    op.create_table(
        'orders',
        sa.Column('decision_id', sa.String(length=64), nullable=False),
        sa.Column('symbol', sa.String(length=16), nullable=False),
        sa.Column('side', sa.String(length=8), nullable=False),
        sa.Column('order_type', sa.String(length=16), nullable=False),
        sa.Column('size_usd', sa.Float(), nullable=False),
        sa.Column('qty', sa.Float(), nullable=True),
        sa.Column('limit_price', sa.Float(), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('broker_order_id', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['decision_id'], ['decisions.decision_id'], ),
        sa.PrimaryKeyConstraint('decision_id'),
    )

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


def downgrade() -> None:
    """Downgrade schema — restore the Week-1 normalized shape."""
    op.drop_table('eval_runs')
    op.drop_index(op.f('ix_outcomes_decision_id'), table_name='outcomes')
    op.drop_table('outcomes')
    op.drop_table('orders')
    op.drop_index(op.f('ix_decisions_ticker'), table_name='decisions')
    op.drop_table('decisions')

    op.create_table(
        'decisions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('decision_id', sa.String(length=64), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('hypothesis_id', sa.Integer(), nullable=False),
        sa.Column('critic_verdict', sa.JSON(), nullable=False),
        sa.Column('guardrail', sa.JSON(), nullable=False),
        sa.Column('human_decision', sa.String(length=16), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['hypothesis_id'], ['hypotheses.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('decision_id'),
    )
    op.create_index(op.f('ix_decisions_user_id'), 'decisions', ['user_id'], unique=False)

    op.create_table(
        'orders',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('decision_id', sa.String(length=64), nullable=False),
        sa.Column('symbol', sa.String(length=16), nullable=False),
        sa.Column('side', sa.String(length=8), nullable=False),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('order_type', sa.String(length=16), nullable=False),
        sa.Column('limit_price', sa.Float(), nullable=True),
        sa.Column('broker_order_id', sa.String(length=64), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('placed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['decision_id'], ['decisions.decision_id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('decision_id'),
    )

    op.create_table(
        'outcomes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('fill_price', sa.Float(), nullable=True),
        sa.Column('forward_return', sa.Float(), nullable=True),
        sa.Column('spy_return', sa.Float(), nullable=True),
        sa.Column('horizon_days', sa.Integer(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_outcomes_order_id'), 'outcomes', ['order_id'], unique=False)
