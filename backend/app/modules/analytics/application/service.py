"""Analytics 服务（spec §12、§42）：订单与财务数据聚合为统一口径指标。"""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.base import CommerceAdapter
from app.modules.analytics.domain.formulas import FORMULAS, MetricInputs, compute_metrics
from app.modules.finance.repository.models import Payment, Refund, Settlement
from app.modules.finance.domain.money import money

logger = logging.getLogger(__name__)


class AnalyticsError(Exception):
    def __init__(self, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


class AnalyticsService:
    def __init__(self, adapter: CommerceAdapter, session: AsyncSession, token: str | None = None):
        self._adapter = adapter
        self._session = session
        self._token = token

    async def _orders(self, *, since: datetime, limit: int) -> list[dict]:
        from app.modules.commerce.application.service import CommerceService

        commerce = CommerceService(self._adapter, token=self._token)
        result: list[dict] = []
        cursor: str | None = None
        scanned = 0
        # Saleor 单页上限 100；按页拉取，跳过窗口外订单，限制总扫描量
        while len(result) < limit and scanned < 500:
            page_size = min(100, limit - len(result))
            orders, page = await commerce.list_orders(channel=None, first=page_size, after=cursor)
            if not orders:
                break
            for order in orders:
                scanned += 1
                created = order.created_at
                try:
                    created_at = datetime.fromisoformat(created.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    created_at = None
                if created_at is not None and created_at < since:
                    continue
                result.append(
                    {
                        "number": order.number,
                        "amount": order.total_amount,
                        "currency": order.currency,
                        "status": order.status,
                    }
                )
            if not page.has_next_page:
                break
            cursor = page.end_cursor
        return result

    async def overview(
        self, *, days: int = 30, other_cost: str = "0", currency: str | None = None, limit: int = 200
    ) -> dict:
        since = datetime.now(UTC) - timedelta(days=days)
        orders = await self._orders(since=since, limit=limit)

        payments = list(
            (await self._session.execute(select(Payment).where(Payment.created_at >= since))).scalars()
        )
        refunds = list(
            (await self._session.execute(select(Refund).where(Refund.created_at >= since))).scalars()
        )
        settlements = list(
            (await self._session.execute(select(Settlement).where(Settlement.created_at >= since))).scalars()
        )

        currencies = sorted(
            {o["currency"] for o in orders}
            | {p.currency for p in payments}
            | {r.currency for r in refunds}
            | {s.currency for s in settlements}
        )
        if currency:
            currencies = [c for c in currencies if c.upper() == currency.upper()]
        if not currencies:
            return {
                "window_days": days,
                "since": since.isoformat(),
                "formulas": FORMULAS,
                "by_currency": {},
                "note": "区间内没有可统计的数据",
            }

        by_currency: dict[str, dict] = {}
        for cur in currencies:
            order_rows = [o for o in orders if o["currency"] == cur]
            payment_rows = [p for p in payments if p.currency == cur]
            refund_rows = [r for r in refunds if r.currency == cur]
            settlement_rows = [s for s in settlements if s.currency == cur]

            gmv = sum((money(o["amount"], cur) for o in order_rows), money("0", cur))
            refund_total = sum((money(r.amount, cur) for r in refund_rows), money("0", cur))
            platform_fee = sum((money(s.platform_fee, cur) for s in settlement_rows), money("0", cur))
            payment_fee = sum((money(s.payment_fee, cur) for s in settlement_rows), money("0", cur))
            net_settled = sum((money(s.net_amount, cur) for s in settlement_rows), money("0", cur))

            metrics = compute_metrics(
                MetricInputs(
                    gmv=gmv,
                    refund_total=refund_total,
                    order_count=len(order_rows),
                    platform_fee=platform_fee,
                    payment_fee=payment_fee,
                    net_settled=net_settled,
                    currency=cur,
                    other_cost=money(other_cost, cur),
                )
            )
            metrics["payment_count"] = str(len(payment_rows))
            metrics["settlement_count"] = str(len(settlement_rows))
            by_currency[cur] = metrics

        return {
            "window_days": days,
            "since": since.isoformat(),
            "formulas": FORMULAS,
            "by_currency": by_currency,
        }

    @staticmethod
    def formulas() -> dict[str, str]:
        return FORMULAS
