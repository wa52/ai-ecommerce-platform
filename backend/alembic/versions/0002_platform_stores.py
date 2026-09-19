"""platform_stores table

Revision ID: 0002_platform_stores
Revises: 0001_baseline
Create Date: 2026-09-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_platform_stores"
down_revision: Union[str, None] = "0001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "platform_stores",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("platform", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="USD"),
        sa.Column("country", sa.String(length=10), nullable=True),
        sa.Column("credentials_encrypted", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_platform_stores_platform", "platform_stores", ["platform"])


def downgrade() -> None:
    op.drop_index("ix_platform_stores_platform", table_name="platform_stores")
    op.drop_table("platform_stores")
