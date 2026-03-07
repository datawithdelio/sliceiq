"""Baseline migration.

This marks the starting point for Alembic-managed changes.
Initial schema is still applied from migrations/schema.sql.
"""

from typing import Sequence, Union


revision: str = "20260306_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
