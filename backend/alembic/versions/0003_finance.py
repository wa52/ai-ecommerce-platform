"""finance tables

Revision ID: 0003_finance
Revises: 0002_platform_stores
Create Date: 2026-09-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003_finance"
down_revision: Union[str, None] = "0002_platform_stores"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

AMOUNT = sa.Numeric(18, 4)


def upgrade() -> None:
    op.create_table(
        "payments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("order_ref", sa.String(120), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("amount", AMOUNT, nullable=False),
        sa.Column("refunded_amount", AMOUNT, nullable=False, server_default="0"),
        sa.Column("currency", sa.String(10), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="succeeded"),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("idempotency_key", name="uq_payments_idempotency_key"),
    )
    op.create_index("ix_payments_order_ref", "payments", ["order_ref"])

    op.create_table(
        "payment_transactions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("payment_id", sa.String(36), sa.ForeignKey("payments.id"), nullable=False),
        sa.Column("external_id", sa.String(120), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False, server_default="charge"),
        sa.Column("amount", AMOUNT, nullable=False),
        sa.Column("currency", sa.String(10), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("source", sa.String(30), nullable=False, server_default="api"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_payment_transactions_payment_id", "payment_transactions", ["payment_id"])

    op.create_table(
        "refunds",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("payment_id", sa.String(36), sa.ForeignKey("payments.id"), nullable=False),
        sa.Column("amount", AMOUNT, nullable=False),
        sa.Column("currency", sa.String(10), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="succeeded"),
        sa.Column("reason", sa.String(200), nullable=True),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("idempotency_key", name="uq_refunds_idempotency_key"),
    )
    op.create_index("ix_refunds_payment_id", "refunds", ["payment_id"])

    op.create_table(
        "refund_transactions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("refund_id", sa.String(36), sa.ForeignKey("refunds.id"), nullable=False),
        sa.Column("external_id", sa.String(120), nullable=False),
        sa.Column("amount", AMOUNT, nullable=False),
        sa.Column("currency", sa.String(10), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_refund_transactions_refund_id", "refund_transactions", ["refund_id"])

    op.create_table(
        "settlements",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column("period_start", sa.String(30), nullable=False),
        sa.Column("period_end", sa.String(30), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False),
        sa.Column("gross_amount", AMOUNT, nullable=False, server_default="0"),
        sa.Column("platform_fee", AMOUNT, nullable=False, server_default="0"),
        sa.Column("payment_fee", AMOUNT, nullable=False, server_default="0"),
        sa.Column("net_amount", AMOUNT, nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "settlement_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("settlement_id", sa.String(36), sa.ForeignKey("settlements.id"), nullable=False),
        sa.Column("order_ref", sa.String(120), nullable=False),
        sa.Column("gross_amount", AMOUNT, nullable=False),
        sa.Column("platform_fee", AMOUNT, nullable=False),
        sa.Column("payment_fee", AMOUNT, nullable=False),
        sa.Column("net_amount", AMOUNT, nullable=False),
    )
    op.create_index("ix_settlement_items_settlement_id", "settlement_items", ["settlement_id"])

    op.create_table(
        "reconciliations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("settlement_id", sa.String(36), sa.ForeignKey("settlements.id"), nullable=False),
        sa.Column("expected_net", AMOUNT, nullable=False),
        sa.Column("actual_net", AMOUNT, nullable=False),
        sa.Column("difference", AMOUNT, nullable=False),
        sa.Column("currency", sa.String(10), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_reconciliations_settlement_id", "reconciliations", ["settlement_id"])

    op.create_table(
        "finance_ledger",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("entry_type", sa.String(30), nullable=False),
        sa.Column("reference", sa.String(120), nullable=False),
        sa.Column("debit", AMOUNT, nullable=False, server_default="0"),
        sa.Column("credit", AMOUNT, nullable=False, server_default="0"),
        sa.Column("currency", sa.String(10), nullable=False),
        sa.Column("source", sa.String(30), nullable=False, server_default="api"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_finance_ledger_reference", "finance_ledger", ["reference"])


def downgrade() -> None:
    for table in (
        "finance_ledger",
        "reconciliations",
        "settlement_items",
        "settlements",
        "refund_transactions",
        "refunds",
        "payment_transactions",
        "payments",
    ):
        op.drop_table(table)
