import stripe as stripe_lib
from fastapi import APIRouter, Request, HTTPException, status, Depends
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import ProcessedStripeEvent
from app.services.stripe_client import sync_subscription_from_stripe

router = APIRouter(tags=["webhooks"])
settings = get_settings()


@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    sig_header = request.headers.get("Stripe-Signature")

    if not settings.stripe_webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe webhook secret not configured",
        )

    try:
        event = stripe_lib.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except (ValueError, stripe_lib.error.SignatureVerificationError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Stripe webhook signature",
        )

    # Deduplicate: ignore already-processed Stripe event IDs.
    existing = (
        db.query(ProcessedStripeEvent)
        .filter(ProcessedStripeEvent.stripe_event_id == event["id"])
        .first()
    )
    if existing:
        return {"status": "already processed"}

    # Mark processed before handling to remain idempotent.
    processed = ProcessedStripeEvent(
        stripe_event_id=event["id"],
        type=event["type"],
    )
    db.add(processed)
    db.commit()

    data = event.get("data", {}).get("object", {})

    if event["type"] == "checkout.session.completed":
        tenant_id = int(data.get("metadata", {}).get("tenant_id", 0))
        # Subscription details are in the subscription object; fetch or rely on
        # the customer.subscription.updated event for full sync.
        sub_id = data.get("subscription")
        if sub_id and tenant_id:
            sync_subscription_from_stripe(
                db, tenant_id, sub_id, "active"
            )

    elif event["type"] in ("customer.subscription.updated", "customer.subscription.deleted"):
        tenant_id = _resolve_tenant_id(db, data.get("customer"))
        if tenant_id:
            sync_subscription_from_stripe(
                db,
                tenant_id,
                data["id"],
                data.get("status", "canceled"),
                data.get("current_period_start"),
                data.get("current_period_end"),
            )

    return {"status": "processed"}


def _resolve_tenant_id(db: Session, customer_id: str | None) -> int | None:
    from app.models import Tenant
    if not customer_id:
        return None
    tenant = db.query(Tenant).filter(Tenant.stripe_customer_id == customer_id).first()
    return tenant.id if tenant else None
