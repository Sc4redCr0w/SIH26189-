"""Add camera monitoring and visual observation tables.

Revision ID: 0003_camera_module
Revises: 0002_case_context
"""
from alembic import op

from app.db import Base
from app import models  # noqa: F401

revision = "0003_camera_module"
down_revision = "0002_case_context"
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
