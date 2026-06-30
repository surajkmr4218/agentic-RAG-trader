"""row level security on tenant tables

Revision ID: 9f6b21b80a84
Revises: dc5f45ab4851
Create Date: 2026-06-30 11:51:14.750977

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '9f6b21b80a84'
down_revision: Union[str, Sequence[str], None] = 'dc5f45ab4851'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TENANT_TABLES = ("decisions", "orders", "outcomes")


def upgrade() -> None:
    for t in TENANT_TABLES:
        op.execute(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {t} FORCE ROW LEVEL SECURITY;")  # owner is subject too
        # `true` = missing_ok: unset app.user_id -> NULL -> zero rows (fail closed)
        op.execute(
            f"CREATE POLICY tenant_isolation ON {t} "
            f"USING (user_id = current_setting('app.user_id', true));"
        )


def downgrade() -> None:
    for t in TENANT_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {t};")
        op.execute(f"ALTER TABLE {t} NO FORCE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {t} DISABLE ROW LEVEL SECURITY;")
