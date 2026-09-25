"""Add case notes and saved investigation context.

Revision ID: 0002_case_context
Revises: 0001_initial
"""
from alembic import op

from app.db import Base
from app import models  # noqa: F401

revision = "0002_case_context"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
