"""Create the initial evidence and graph schema.

Revision ID: 0001_initial
Revises:
"""
from __future__ import annotations

from alembic import op

from app.db import Base
from app import models  # noqa: F401 - register metadata

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The SQLAlchemy metadata is the single schema contract for the initial
    # Windows development migration. Future revisions should use explicit
    # op.create_table/op.add_column operations as the schema evolves.
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
