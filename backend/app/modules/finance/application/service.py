import logging
import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.finance.domain.money import add, money, sub, as_str
from app.modules.finance.repository.models import (
    FinanceLedger,
    Payment,
    PaymentTransaction,
    Reconciliation,
    Refund,
    RefundTransaction,
    Settlement,
    SettlementItem,
)

logger = logging.getLogger(__name__)


class FinanceError(Exception):
    def __init__(self, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


class NotFound(FinanceError):
    def __init__(self, message: str):
        super().__init__(message, status_code=404)


class FinanceService:
    def __init__(self, session: AsyncSession):
        self._session = session

    # ---------- Payment ----------

    async def create_payment(
        self,
        *,
        order_ref: str,
        provider: str,
        amount: str,
        currency: str,
        idempotency_key: str,
        source: str = "api",
    ) -> tuple[Payment, bool]:
        """创建支付。同一 idempotency_key 重复请求只产生一次有效交易。"""
        existing = await self._session.scalar(
            select(Payment).where(Payment.idempotency_key == idempotency_key)
        )
        if existing is not None:
            return existing, False

        amount_dec = money(amount, currency)
        if amount_dec <= 0:
            raise FinanceError("支付金额必须大于 0", status_code=422)

        payment = Payment(
            order_ref=order_ref,
            provider=provider,
            amount=amount_dec,
            refunded_amount=Decimal("0"),
            currency=currency.upper(),
            status="succeeded",
            idempotency_key=idempotency_key,
        )
        self._session.add(payment)
        await self._session.flush()
        self._session.add(
            PaymentTransaction(
                payment_id=payment.id,
                external_id=f"txn_{uuid.uuid4().hex[:12]}",
                kind="charge",
                amount=amount_dec,
                currency=payment.currency,
                status="succeeded",
                source=source,
            )
        )
        self._session.add(
            FinanceLedger(
                entry_type="payment",
                reference=payment.id,
                debit=Decimal("0"),
                credit=amount_dec,
                currency=payment.currency,
                source=source,
            )
        )
        await self._session.commit()
        await self._session.refresh(payment)
        return payment, True

    async def get_payment(self, payment_id: str) -> Payment:
        payment = await self._session.get(Payment, payment_id)
        if payment is None:
            raise NotFound(f"支付单不存在：{payment_id}")
        return payment

    async def list_payments(self, *, limit: int = 50) -> list[Payment]:
        stmt = select(Payment).order_by(Payment.created_at.desc()).limit(limit)
        return list((await self._session.execute(stmt)).scalars())

    # ---------- Refund ----------

    async def create_refund(
        self,
        *,
        payment_id: str,
        amount: str,
        idempotency_key: str,
        reason: str | None = None,
        source: str = "api",
    ) -> tuple[Refund, bool]:
        existing = await self._session.scalar(select(Refund).where(Refund.idempotency_key == idempotency_key))
        if existing is not None:
            return existing, False

        payment = await self.get_payment(payment_id)
        refund_amount = money(amount, payment.currency)
        if refund_amount <= 0:
            raise FinanceError("退款金额必须大于 0", status_code=422)

        refundable = sub(payment.amount, payment.refunded_amount, payment.currency)
        if refund_amount > refundable:
            raise FinanceError(
                f"退款金额超过可退款额度（可退 {as_str(refundable, payment.currency)} {payment.currency}）",
                status_code=409,
            )

        refund = Refund(
            payment_id=payment.id,
            amount=refund_amount,
            currency=payment.currency,
            status="succeeded",
            reason=reason,
            idempotency_key=idempotency_key,
        )
        self._session.add(refund)
        await self._session.flush()
        self._session.add(
            RefundTransaction(
                refund_id=refund.id,
                external_id=f"rfd_{uuid.uuid4().hex[:12]}",
                amount=refund_amount,
                currency=payment.currency,
                status="succeeded",
            )
        )
        payment.refunded_amount = add(payment.refunded_amount, refund_amount, payment.currency)
        self._session.add(
            FinanceLedger(
                entry_type="refund",
                reference=refund.id,
                debit=refund_amount,
                credit=Decimal("0"),
                currency=payment.currency,
                source=source,
            )
        )
        await self._session.commit()
        await self._session.refresh(refund)
        return refund, True

    async def list_refunds(self, *, payment_id: str | None = None, limit: int = 50) -> list[Refund]:
        stmt = select(Refund).order_by(Refund.created_at.desc()).limit(limit)
        if payment_id:
            stmt = stmt.where(Refund.payment_id == payment_id)
        return list((await self._session.execute(stmt)).scalars())

    # ---------- Settlement ----------

    async def create_settlement(
        self,
        *,
        platform: str,
        period_start: str,
        period_end: str,
        currency: str,
        items: list[dict],
        platform_fee_rate: str = "0",
        payment_fee_rate: str = "0",
    ) -> Settlement:
        """结算：按费率计算平台/支付手续费与净额（spec §41）。"""
        from app.modules.finance.domain.money import mul

        currency = currency.upper()
        gross_total = Decimal("0")
        platform_fee_total = Decimal("0")
        payment_fee_total = Decimal("0")
        net_total = Decimal("0")

        settlement = Settlement(
            platform=platform,
            period_start=period_start,
            period_end=period_end,
            currency=currency,
            status="open",
        )
        self._session.add(settlement)
        await self._session.flush()

        for item in items:
            gross = money(item["gross_amount"], currency)
            platform_fee = mul(gross, money(platform_fee_rate, currency) / Decimal("100"), currency) if Decimal(platform_fee_rate) else Decimal("0")
            payment_fee = mul(gross, money(payment_fee_rate, currency) / Decimal("100"), currency) if Decimal(payment_fee_rate) else Decimal("0")
            net = sub(sub(gross, platform_fee, currency), payment_fee, currency)

            gross_total = add(gross_total, gross, currency)
            platform_fee_total = add(platform_fee_total, platform_fee, currency)
            payment_fee_total = add(payment_fee_total, payment_fee, currency)
            net_total = add(net_total, net, currency)

            self._session.add(
                SettlementItem(
                    settlement_id=settlement.id,
                    order_ref=item["order_ref"],
                    gross_amount=gross,
                    platform_fee=platform_fee,
                    payment_fee=payment_fee,
                    net_amount=net,
                )
            )

        settlement.gross_amount = gross_total
        settlement.platform_fee = platform_fee_total
        settlement.payment_fee = payment_fee_total
        settlement.net_amount = net_total
        self._session.add(
            FinanceLedger(
                entry_type="settlement",
                reference=settlement.id,
                debit=Decimal("0"),
                credit=net_total,
                currency=currency,
                source="api",
            )
        )
        await self._session.commit()
        await self._session.refresh(settlement)
        return settlement

    async def get_settlement(self, settlement_id: str) -> Settlement:
        settlement = await self._session.get(Settlement, settlement_id)
        if settlement is None:
            raise NotFound(f"结算单不存在：{settlement_id}")
        return settlement

    async def list_settlements(self, *, limit: int = 50) -> list[Settlement]:
        stmt = select(Settlement).order_by(Settlement.created_at.desc()).limit(limit)
        return list((await self._session.execute(stmt)).scalars())

    async def settlement_items(self, settlement_id: str) -> list[SettlementItem]:
        stmt = select(SettlementItem).where(SettlementItem.settlement_id == settlement_id)
        return list((await self._session.execute(stmt)).scalars())

    # ---------- Reconciliation ----------

    async def reconcile(self, *, settlement_id: str, actual_net: str, note: str | None = None) -> Reconciliation:
        settlement = await self.get_settlement(settlement_id)
        actual = money(actual_net, settlement.currency)
        difference = sub(actual, settlement.net_amount, settlement.currency)
        status = "matched" if difference == 0 else "mismatched"
        record = Reconciliation(
            settlement_id=settlement.id,
            expected_net=settlement.net_amount,
            actual_net=actual,
            difference=difference,
            currency=settlement.currency,
            status=status,
            note=note,
        )
        self._session.add(record)
        await self._session.commit()
        await self._session.refresh(record)
        return record

    async def list_reconciliations(self, *, settlement_id: str | None = None, limit: int = 50) -> list[Reconciliation]:
        stmt = select(Reconciliation).order_by(Reconciliation.created_at.desc()).limit(limit)
        if settlement_id:
            stmt = stmt.where(Reconciliation.settlement_id == settlement_id)
        return list((await self._session.execute(stmt)).scalars())

    # ---------- Ledger ----------

    async def list_ledger(self, *, limit: int = 100) -> list[FinanceLedger]:
        stmt = select(FinanceLedger).order_by(FinanceLedger.created_at.desc()).limit(limit)
        return list((await self._session.execute(stmt)).scalars())
