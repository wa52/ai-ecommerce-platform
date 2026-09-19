import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base

AMOUNT = Numeric(18, 4)


class Payment(Base):
    """支付单。idempotency_key 唯一，重复请求只产生一次有效交易（spec §41）。"""

    __tablename__ = "payments"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_payments_idempotency_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    order_ref: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    amount: Mapped[Decimal] = mapped_column(AMOUNT, nullable=False)
    refunded_amount: Mapped[Decimal] = mapped_column(AMOUNT, nullable=False, default=Decimal("0"))
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="succeeded")
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    transactions: Mapped[list["PaymentTransaction"]] = relationship(back_populates="payment")


class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    payment_id: Mapped[str] = mapped_column(ForeignKey("payments.id"), nullable=False, index=True)
    external_id: Mapped[str] = mapped_column(String(120), nullable=False)
    kind: Mapped[str] = mapped_column(String(30), nullable=False, default="charge")
    amount: Mapped[Decimal] = mapped_column(AMOUNT, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    source: Mapped[str] = mapped_column(String(30), nullable=False, default="api")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    payment: Mapped[Payment] = relationship(back_populates="transactions")


class Refund(Base):
    __tablename__ = "refunds"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_refunds_idempotency_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    payment_id: Mapped[str] = mapped_column(ForeignKey("payments.id"), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(AMOUNT, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="succeeded")
    reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class RefundTransaction(Base):
    __tablename__ = "refund_transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    refund_id: Mapped[str] = mapped_column(ForeignKey("refunds.id"), nullable=False, index=True)
    external_id: Mapped[str] = mapped_column(String(120), nullable=False)
    amount: Mapped[Decimal] = mapped_column(AMOUNT, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Settlement(Base):
    __tablename__ = "settlements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    period_start: Mapped[str] = mapped_column(String(30), nullable=False)
    period_end: Mapped[str] = mapped_column(String(30), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    gross_amount: Mapped[Decimal] = mapped_column(AMOUNT, nullable=False, default=Decimal("0"))
    platform_fee: Mapped[Decimal] = mapped_column(AMOUNT, nullable=False, default=Decimal("0"))
    payment_fee: Mapped[Decimal] = mapped_column(AMOUNT, nullable=False, default=Decimal("0"))
    net_amount: Mapped[Decimal] = mapped_column(AMOUNT, nullable=False, default=Decimal("0"))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    items: Mapped[list["SettlementItem"]] = relationship(back_populates="settlement")


class SettlementItem(Base):
    __tablename__ = "settlement_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    settlement_id: Mapped[str] = mapped_column(ForeignKey("settlements.id"), nullable=False, index=True)
    order_ref: Mapped[str] = mapped_column(String(120), nullable=False)
    gross_amount: Mapped[Decimal] = mapped_column(AMOUNT, nullable=False)
    platform_fee: Mapped[Decimal] = mapped_column(AMOUNT, nullable=False)
    payment_fee: Mapped[Decimal] = mapped_column(AMOUNT, nullable=False)
    net_amount: Mapped[Decimal] = mapped_column(AMOUNT, nullable=False)

    settlement: Mapped[Settlement] = relationship(back_populates="items")


class Reconciliation(Base):
    __tablename__ = "reconciliations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    settlement_id: Mapped[str] = mapped_column(ForeignKey("settlements.id"), nullable=False, index=True)
    expected_net: Mapped[Decimal] = mapped_column(AMOUNT, nullable=False)
    actual_net: Mapped[Decimal] = mapped_column(AMOUNT, nullable=False)
    difference: Mapped[Decimal] = mapped_column(AMOUNT, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FinanceLedger(Base):
    """财务流水：所有关键资金动作可追溯（spec §41）。"""

    __tablename__ = "finance_ledger"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    entry_type: Mapped[str] = mapped_column(String(30), nullable=False)
    reference: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    debit: Mapped[Decimal] = mapped_column(AMOUNT, nullable=False, default=Decimal("0"))
    credit: Mapped[Decimal] = mapped_column(AMOUNT, nullable=False, default=Decimal("0"))
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    source: Mapped[str] = mapped_column(String(30), nullable=False, default="api")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
