"""金额处理（spec §41）：禁止 float，统一 Decimal + 明确的币种精度与舍入规则。"""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

# 常见币种最小单位（ISO 4217 exponent）
CURRENCY_EXPONENTS: dict[str, int] = {
    "USD": 2,
    "EUR": 2,
    "GBP": 2,
    "CNY": 2,
    "JPY": 0,
    "KRW": 0,
}


class MoneyError(Exception):
    pass


def exponent_of(currency: str) -> int:
    code = (currency or "").upper()
    if not code:
        raise MoneyError("缺少币种（currency）")
    return CURRENCY_EXPONENTS.get(code, 2)


def to_decimal(value: str | int | Decimal) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, float):
        raise MoneyError("禁止使用 float 表示金额，请使用字符串或 Decimal")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise MoneyError(f"非法金额：{value!r}") from exc


def quantize(value: Decimal, currency: str) -> Decimal:
    exp = exponent_of(currency)
    quantum = Decimal(1).scaleb(-exp)
    return value.quantize(quantum, rounding=ROUND_HALF_UP)


def money(value: str | int | Decimal, currency: str) -> Decimal:
    return quantize(to_decimal(value), currency)


def add(a: Decimal, b: Decimal, currency: str) -> Decimal:
    return quantize(a + b, currency)


def sub(a: Decimal, b: Decimal, currency: str) -> Decimal:
    return quantize(a - b, currency)


def mul(a: Decimal, b: Decimal, currency: str) -> Decimal:
    return quantize(a * b, currency)


def as_str(value: Decimal, currency: str) -> str:
    return f"{quantize(value, currency):f}"
