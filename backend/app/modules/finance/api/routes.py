from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.session import get_db
from app.modules.finance.application.service import FinanceError, FinanceService
from app.modules.finance.domain.money import as_str
from app.modules.finance.domain.signature import WebhookSignatureError, verify_webhook_signature
from app.modules.iam.api.deps import AdminUserDep

router = APIRouter(prefix="/finance", tags=["finance"])


class PaymentCreate(BaseModel):
    order_ref: str = Field(min_length=1, max_length=120)
    provider: str = Field(min_length=1, max_length=50)
    amount: str = Field(pattern=r"^\d+(\.\d{1,4})?$")
    currency: str = Field(min_length=3, max_length=10)
    idempotency_key: str = Field(min_length=1, max_length=120)


class PaymentResponse(BaseModel):
    id: str
    order_ref: str
    provider: str
    amount: str
    refunded_amount: str
    currency: str
    status: str
    idempotency_key: str
    created: bool = True


class RefundCreate(BaseModel):
    payment_id: str
    amount: str = Field(pattern=r"^\d+(\.\d{1,4})?$")
    idempotency_key: str = Field(min_length=1, max_length=120)
    reason: str | None = Field(default=None, max_length=200)


class RefundResponse(BaseModel):
    id: str
    payment_id: str
    amount: str
    currency: str
    status: str
    reason: str | None
    created: bool = True


class SettlementItemInput(BaseModel):
    order_ref: str
    gross_amount: str


class SettlementCreate(BaseModel):
    platform: str
    period_start: str
    period_end: str
    currency: str
    items: list[SettlementItemInput]
    platform_fee_rate: str = "0"
    payment_fee_rate: str = "0"


class SettlementResponse(BaseModel):
    id: str
    platform: str
    period_start: str
    period_end: str
    currency: str
    gross_amount: str
    platform_fee: str
    payment_fee: str
    net_amount: str
    status: str


class ReconciliationCreate(BaseModel):
    settlement_id: str
    actual_net: str
    note: str | None = None


class ReconciliationResponse(BaseModel):
    id: str
    settlement_id: str
    expected_net: str
    actual_net: str
    difference: str
    currency: str
    status: str
    note: str | None


def _handle(exc: FinanceError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=str(exc))


def _payment(payment, created: bool) -> PaymentResponse:
    return PaymentResponse(
        id=payment.id,
        order_ref=payment.order_ref,
        provider=payment.provider,
        amount=as_str(payment.amount, payment.currency),
        refunded_amount=as_str(payment.refunded_amount, payment.currency),
        currency=payment.currency,
        status=payment.status,
        idempotency_key=payment.idempotency_key,
        created=created,
    )


@router.post("/payments", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def create_payment(
    req: PaymentCreate, _: AdminUserDep, db: AsyncSession = Depends(get_db)
) -> PaymentResponse:
    try:
        payment, created = await FinanceService(db).create_payment(
            order_ref=req.order_ref,
            provider=req.provider,
            amount=req.amount,
            currency=req.currency,
            idempotency_key=req.idempotency_key,
        )
    except FinanceError as exc:
        raise _handle(exc) from exc
    return _payment(payment, created)


@router.get("/payments", response_model=list[PaymentResponse])
async def list_payments(
    _: AdminUserDep, db: AsyncSession = Depends(get_db), limit: int = Query(default=50, ge=1, le=200)
) -> list[PaymentResponse]:
    return [_payment(p, False) for p in await FinanceService(db).list_payments(limit=limit)]


@router.get("/payments/{payment_id}", response_model=PaymentResponse)
async def get_payment(payment_id: str, _: AdminUserDep, db: AsyncSession = Depends(get_db)) -> PaymentResponse:
    try:
        return _payment(await FinanceService(db).get_payment(payment_id), False)
    except FinanceError as exc:
        raise _handle(exc) from exc


@router.post("/refunds", response_model=RefundResponse, status_code=status.HTTP_201_CREATED)
async def create_refund(
    req: RefundCreate, _: AdminUserDep, db: AsyncSession = Depends(get_db)
) -> RefundResponse:
    try:
        refund, created = await FinanceService(db).create_refund(
            payment_id=req.payment_id,
            amount=req.amount,
            idempotency_key=req.idempotency_key,
            reason=req.reason,
        )
    except FinanceError as exc:
        raise _handle(exc) from exc
    return RefundResponse(
        id=refund.id,
        payment_id=refund.payment_id,
        amount=as_str(refund.amount, refund.currency),
        currency=refund.currency,
        status=refund.status,
        reason=refund.reason,
        created=created,
    )


@router.get("/refunds", response_model=list[RefundResponse])
async def list_refunds(
    _: AdminUserDep,
    db: AsyncSession = Depends(get_db),
    payment_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[RefundResponse]:
    rows = await FinanceService(db).list_refunds(payment_id=payment_id, limit=limit)
    return [
        RefundResponse(
            id=r.id,
            payment_id=r.payment_id,
            amount=as_str(r.amount, r.currency),
            currency=r.currency,
            status=r.status,
            reason=r.reason,
            created=False,
        )
        for r in rows
    ]


@router.post("/settlements", response_model=SettlementResponse, status_code=status.HTTP_201_CREATED)
async def create_settlement(
    req: SettlementCreate, _: AdminUserDep, db: AsyncSession = Depends(get_db)
) -> SettlementResponse:
    try:
        settlement = await FinanceService(db).create_settlement(
            platform=req.platform,
            period_start=req.period_start,
            period_end=req.period_end,
            currency=req.currency,
            items=[i.model_dump() for i in req.items],
            platform_fee_rate=req.platform_fee_rate,
            payment_fee_rate=req.payment_fee_rate,
        )
    except FinanceError as exc:
        raise _handle(exc) from exc
    return SettlementResponse(
        id=settlement.id,
        platform=settlement.platform,
        period_start=settlement.period_start,
        period_end=settlement.period_end,
        currency=settlement.currency,
        gross_amount=as_str(settlement.gross_amount, settlement.currency),
        platform_fee=as_str(settlement.platform_fee, settlement.currency),
        payment_fee=as_str(settlement.payment_fee, settlement.currency),
        net_amount=as_str(settlement.net_amount, settlement.currency),
        status=settlement.status,
    )


@router.get("/settlements", response_model=list[SettlementResponse])
async def list_settlements(
    _: AdminUserDep, db: AsyncSession = Depends(get_db), limit: int = Query(default=50, ge=1, le=200)
) -> list[SettlementResponse]:
    rows = await FinanceService(db).list_settlements(limit=limit)
    return [
        SettlementResponse(
            id=s.id,
            platform=s.platform,
            period_start=s.period_start,
            period_end=s.period_end,
            currency=s.currency,
            gross_amount=as_str(s.gross_amount, s.currency),
            platform_fee=as_str(s.platform_fee, s.currency),
            payment_fee=as_str(s.payment_fee, s.currency),
            net_amount=as_str(s.net_amount, s.currency),
            status=s.status,
        )
        for s in rows
    ]


@router.post("/reconciliations", response_model=ReconciliationResponse, status_code=status.HTTP_201_CREATED)
async def reconcile(
    req: ReconciliationCreate, _: AdminUserDep, db: AsyncSession = Depends(get_db)
) -> ReconciliationResponse:
    try:
        record = await FinanceService(db).reconcile(
            settlement_id=req.settlement_id, actual_net=req.actual_net, note=req.note
        )
    except FinanceError as exc:
        raise _handle(exc) from exc
    return ReconciliationResponse(
        id=record.id,
        settlement_id=record.settlement_id,
        expected_net=as_str(record.expected_net, record.currency),
        actual_net=as_str(record.actual_net, record.currency),
        difference=as_str(record.difference, record.currency),
        currency=record.currency,
        status=record.status,
        note=record.note,
    )


@router.get("/ledger")
async def list_ledger(
    _: AdminUserDep, db: AsyncSession = Depends(get_db), limit: int = Query(default=100, ge=1, le=500)
) -> list[dict]:
    rows = await FinanceService(db).list_ledger(limit=limit)
    return [
        {
            "id": r.id,
            "entry_type": r.entry_type,
            "reference": r.reference,
            "debit": as_str(r.debit, r.currency),
            "credit": as_str(r.credit, r.currency),
            "currency": r.currency,
            "source": r.source,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


@router.post("/webhooks/{provider}")
async def payment_webhook(
    provider: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    signature: str | None = Query(default=None, alias="signature"),
) -> dict:
    """支付 Webhook：必须验签，且重复投递只产生一次有效交易（spec §41）。"""
    from app.infrastructure.config.settings import get_settings

    raw = await request.body()
    secret = get_settings().payment_webhook_secret
    header_signature = signature or request.headers.get("X-Signature") or ""
    try:
        verify_webhook_signature(payload=raw, signature=header_signature, secret=secret)
    except WebhookSignatureError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    import json

    try:
        event = json.loads(raw or b"{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail="Webhook 负载不是合法 JSON") from exc

    event_id = event.get("id")
    if not event_id:
        raise HTTPException(status_code=422, detail="Webhook 缺少事件 id")
    service = FinanceService(db)
    try:
        payment, created = await service.create_payment(
            order_ref=event.get("order_ref", "unknown"),
            provider=provider,
            amount=str(event.get("amount", "0")),
            currency=str(event.get("currency", "USD")),
            idempotency_key=f"webhook:{provider}:{event_id}",
            source="webhook",
        )
    except FinanceError as exc:
        raise _handle(exc) from exc
    return {"provider": provider, "event_id": event_id, "payment_id": payment.id, "duplicate": not created}
