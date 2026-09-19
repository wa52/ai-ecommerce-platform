"""指标口径定义（spec §42）。

所有指标必须在此集中定义，避免前端 / AI / 报表使用不同口径。
金额一律 Decimal，按币种分别计算。
"""

from dataclasses import dataclass
from decimal import Decimal

from app.modules.finance.domain.money import add, as_str, money, sub

FORMULAS: dict[str, str] = {
    "gmv": "GMV = Σ 区间内订单金额（gross，含未退款部分）",
    "net_sales": "销售额 = GMV − 退款总额",
    "order_count": "订单量 = 区间内订单数量",
    "avg_order_value": "客单价 = GMV ÷ 订单量（订单量为 0 时记 0）",
    "refund_rate": "退款率 = 退款总额 ÷ GMV（GMV 为 0 时记 0）",
    "platform_fee": "平台手续费 = Σ 结算单平台手续费",
    "payment_fee": "支付手续费 = Σ 结算单支付手续费",
    "net_settled": "实际到账 = Σ 结算单净额（gross − 平台费 − 支付费）",
    "other_cost": "其他成本 = 调用方传入的已计入成本",
    "profit": "利润 = 销售额 − 平台手续费 − 支付手续费 − 其他成本",
    "profit_margin": "利润率 = 利润 ÷ 销售额 × 100（销售额 ≤ 0 时记 0）",
}


@dataclass
class MetricInputs:
    gmv: Decimal
    refund_total: Decimal
    order_count: int
    platform_fee: Decimal
    payment_fee: Decimal
    net_settled: Decimal
    currency: str
    other_cost: Decimal = Decimal("0")


def compute_metrics(inputs: MetricInputs) -> dict[str, str]:
    """按 FORMULAS 中的口径计算指标，返回按币种精度格式化的字符串。"""
    currency = inputs.currency
    net_sales = sub(inputs.gmv, inputs.refund_total, currency)
    profit = sub(sub(sub(net_sales, inputs.platform_fee, currency), inputs.payment_fee, currency), inputs.other_cost, currency)

    aov = Decimal("0")
    if inputs.order_count > 0:
        aov = money(inputs.gmv / Decimal(inputs.order_count), currency)

    refund_rate = Decimal("0")
    if inputs.gmv > 0:
        refund_rate = money(inputs.refund_total / inputs.gmv * Decimal("100"), currency)

    margin = Decimal("0")
    if net_sales > 0:
        margin = money(profit / net_sales * Decimal("100"), currency)
    else:
        margin = money("0", currency)

    return {
        "currency": currency,
        "gmv": as_str(inputs.gmv, currency),
        "net_sales": as_str(net_sales, currency),
        "order_count": str(inputs.order_count),
        "avg_order_value": as_str(aov, currency),
        "refund_total": as_str(inputs.refund_total, currency),
        "refund_rate_percent": as_str(refund_rate, currency),
        "platform_fee": as_str(inputs.platform_fee, currency),
        "payment_fee": as_str(inputs.payment_fee, currency),
        "net_settled": as_str(inputs.net_settled, currency),
        "other_cost": as_str(inputs.other_cost, currency),
        "profit": as_str(profit, currency),
        "profit_margin_percent": as_str(margin, currency),
    }


def sum_money(values: list[Decimal], currency: str) -> Decimal:
    total = Decimal("0")
    for value in values:
        total = add(total, value, currency)
    return total
