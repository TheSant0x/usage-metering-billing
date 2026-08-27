import stripe as stripe_lib
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Tenant, Plan, Subscription, TenantStatus
from app.services.plans import get_plan_by_name

settings = get_settings()


def _client() -> stripe_lib.Stripe:
    if not settings.stripe_secret_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe is not configured",
        )
    stripe_lib.api_key = settings.stripe_secret_key
    return stripe_lib


def get_or_create_customer(tenant: Tenant) -> str:
    if tenant.stripe_customer_id:
        return tenant.stripe_customer_id

    client = _client()
    customer = client.Customer.create(
        name=tenant.name,
        email=tenant.email,
        metadata={"tenant_id": str(tenant.id)},
    )
    tenant.stripe_customer_id = customer.id
    return customer.id


def create_checkout_session(db: Session, tenant_id: int) -> str:
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    pro_plan = get_plan_by_name(db, "pro")
    if not pro_plan or not pro_plan.stripe_price_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Pro plan or Stripe price ID not configured",
        )

    customer_id = get_or_create_customer(tenant)
    db.commit()  # persist customer id

    client = _client()
    session = client.checkout.Session.create(
        customer=customer_id,
        mode="subscription",
        line_items=[{"price": pro_plan.stripe_price_id, "quantity": 1}],
        success_url=f"{settings.app_base_url}/checkout/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{settings.app_base_url}/checkout/cancel",
        metadata={"tenant_id": str(tenant_id)},
    )
    return session.url


def upgrade_tenant_to_pro(db: Session, tenant_id: int) -> None:
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        return
    pro_plan = get_plan_by_name(db, "pro")
    if pro_plan:
        tenant.plan_id = pro_plan.id
    tenant.status = TenantStatus.ACTIVE
    db.commit()


def downgrade_tenant_to_free(db: Session, tenant_id: int) -> None:
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        return
    free_plan = get_plan_by_name(db, "free")
    if free_plan:
        tenant.plan_id = free_plan.id
    tenant.status = TenantStatus.ACTIVE
    db.commit()


def sync_subscription_from_stripe(
    db: Session,
    tenant_id: int,
    subscription_id: str,
    subscription_status: str,
    current_period_start: int | None = None,
    current_period_end: int | None = None,
) -> None:
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        return

    # Map Stripe status to local plan.
    active_statuses = {"active", "trialing"}
    if subscription_status in active_statuses:
        upgrade_tenant_to_pro(db, tenant_id)
    elif subscription_status in {"canceled", "unpaid", "incomplete_expired"}:
        downgrade_tenant_to_free(db, tenant_id)
    elif subscription_status == "past_due":
        tenant.status = TenantStatus.PAST_DUE
        db.commit()

    sub = db.query(Subscription).filter(
        Subscription.stripe_subscription_id == subscription_id
    ).first()
    if not sub:
        sub = Subscription(
            tenant_id=tenant_id,
            stripe_subscription_id=subscription_id,
            status=subscription_status,
        )
        db.add(sub)

    sub.status = subscription_status
    if current_period_start:
        sub.current_period_start = __ts_to_dt(current_period_start)
    if current_period_end:
        sub.current_period_end = __ts_to_dt(current_period_end)
    db.commit()


def __ts_to_dt(ts: int):
    import datetime as dt
    return dt.datetime.fromtimestamp(ts, tz=dt.timezone.utc)
