import datetime as dt
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status

from app.models import UsageEvent, Tenant, TenantStatus, UsageType
from app.services.pricing import calculate_token_cost_cents, calculate_api_call_cost_cents


class QuotaResult:
    allowed: bool
    status_code: int
    message: str

    def __init__(self, allowed: bool, status_code: int = 200, message: str = ""):
        self.allowed = allowed
        self.status_code = status_code
        self.message = message


def _month_bounds(now: dt.datetime) -> tuple[dt.datetime, dt.datetime]:
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end


def _utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def get_monthly_usage(db: Session, tenant_id: int, usage_type: str, now: dt.datetime | None = None) -> int:
    if now is None:
        now = _utc_now()
    start, end = _month_bounds(now)
    total = (
        db.query(func.coalesce(func.sum(UsageEvent.quantity), 0))
        .filter(
            UsageEvent.tenant_id == tenant_id,
            UsageEvent.type == usage_type,
            UsageEvent.created_at >= start,
            UsageEvent.created_at < end,
        )
        .scalar()
    )
    return int(total)


def get_monthly_token_breakdown(
    db: Session, tenant_id: int, now: dt.datetime | None = None
) -> dict[str, int]:
    if now is None:
        now = _utc_now()
    start, end = _month_bounds(now)
    row = (
        db.query(
            func.coalesce(func.sum(UsageEvent.input_tokens), 0),
            func.coalesce(func.sum(UsageEvent.cached_input_tokens), 0),
            func.coalesce(func.sum(UsageEvent.output_tokens), 0),
            func.coalesce(func.sum(UsageEvent.reasoning_tokens), 0),
        )
        .filter(
            UsageEvent.tenant_id == tenant_id,
            UsageEvent.type == UsageType.AI_TOKEN,
            UsageEvent.created_at >= start,
            UsageEvent.created_at < end,
        )
        .first()
    )
    return {
        "input": int(row[0]),
        "cached_input": int(row[1]),
        "output": int(row[2]),
        "reasoning": int(row[3]),
    }


def check_quota(db: Session, tenant: Tenant, usage_type: str, requested: int, now: dt.datetime | None = None) -> QuotaResult:
    plan = tenant.plan
    limit = plan.api_calls_limit if usage_type == UsageType.API_CALL else plan.ai_tokens_limit
    used = get_monthly_usage(db, tenant.id, usage_type, now)

    if tenant.status == TenantStatus.CANCELED or tenant.status == TenantStatus.PAST_DUE:
        return QuotaResult(
            allowed=False,
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            message=f"Subscription is {tenant.status}. Please update payment to continue.",
        )

    if used + requested > limit:
        return QuotaResult(
            allowed=False,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            message=(
                f"{usage_type} quota exceeded: used {used} of {limit} this month; "
                f"requested {requested}. Upgrade to Pro for higher limits."
            ),
        )

    return QuotaResult(allowed=True)


def record_usage(
    db: Session,
    tenant_id: int,
    usage_type: str,
    quantity: int,
    idempotency_key: str,
    token_breakdown: dict[str, int] | None = None,
    now: dt.datetime | None = None,
) -> UsageEvent:
    """Record a usage event idempotently. Raises HTTPException on duplicate creation."""
    if now is None:
        now = _utc_now()
    existing = (
        db.query(UsageEvent)
        .filter(UsageEvent.idempotency_key == idempotency_key)
        .first()
    )
    if existing:
        return existing

    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    quota = check_quota(db, tenant, usage_type, quantity, now)
    if not quota.allowed:
        raise HTTPException(status_code=quota.status_code, detail=quota.message)

    breakdown = token_breakdown or {}
    event = UsageEvent(
        tenant_id=tenant_id,
        type=usage_type,
        quantity=quantity,
        input_tokens=breakdown.get("input", 0),
        cached_input_tokens=breakdown.get("cached_input", 0),
        output_tokens=breakdown.get("output", 0),
        reasoning_tokens=breakdown.get("reasoning", 0),
        idempotency_key=idempotency_key,
    )
    db.add(event)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # Race: another request committed the same idempotency key first.
        existing = (
            db.query(UsageEvent)
            .filter(UsageEvent.idempotency_key == idempotency_key)
            .first()
        )
        if existing:
            return existing
        raise
    db.refresh(event)
    return event


def get_usage_summary(db: Session, tenant_id: int, now: dt.datetime | None = None) -> dict:
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    if now is None:
        now = _utc_now()
    start, end = _month_bounds(now)

    plan = tenant.plan
    api_used = get_monthly_usage(db, tenant_id, UsageType.API_CALL, now)
    ai_used = get_monthly_usage(db, tenant_id, UsageType.AI_TOKEN, now)
    token_breakdown = get_monthly_token_breakdown(db, tenant_id, now)

    api_cost = calculate_api_call_cost_cents(api_used)
    ai_cost = calculate_token_cost_cents(
        token_breakdown["input"],
        token_breakdown["cached_input"],
        token_breakdown["output"],
        token_breakdown["reasoning"],
    )

    return {
        "tenant_id": tenant_id,
        "plan_name": plan.name,
        "period_start": start,
        "period_end": end,
        "items": [
            {"type": UsageType.API_CALL, "used": api_used, "limit": plan.api_calls_limit, "cost_cents": api_cost},
            {"type": UsageType.AI_TOKEN, "used": ai_used, "limit": plan.ai_tokens_limit, "cost_cents": ai_cost},
        ],
        "total_cost_cents": api_cost + ai_cost,
    }
