import hmac
import hashlib
import json
import time
from unittest.mock import patch

import stripe
from fastapi.testclient import TestClient

from app.models import Tenant, Subscription, ProcessedStripeEvent
from tests.conftest import TestingSessionLocal


TEST_WEBHOOK_SECRET = "whsec_test_secret_123456789"


def _stripe_signature_payload(payload: bytes, secret: str, timestamp: int | None = None) -> tuple[str, str]:
    if timestamp is None:
        timestamp = int(time.time())
    signed_payload = f"{timestamp}.".encode() + payload
    signature = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
    header = f"t={timestamp},v1={signature}"
    return header, str(timestamp)


def _set_webhook_secret():
    from app.config import get_settings
    from app.routers import webhooks
    get_settings().stripe_webhook_secret = TEST_WEBHOOK_SECRET
    webhooks.settings.stripe_webhook_secret = TEST_WEBHOOK_SECRET


def test_forged_webhook_returns_400(client: TestClient, free_tenant):
    _set_webhook_secret()
    resp = client.post(
        "/webhooks/stripe",
        content=b'{"id":"evt_1","type":"customer.subscription.updated"}',
        headers={"Stripe-Signature": "t=1,v1=bad_signature"},
    )
    assert resp.status_code == 400


def test_valid_webhook_processed_once_and_upgrades_plan(client: TestClient, free_tenant):
    _set_webhook_secret()
    tenant_id = free_tenant["id"]

    db = TestingSessionLocal()
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    tenant.stripe_customer_id = "cus_test_123"
    db.commit()
    db.close()

    payload_dict = {
        "id": "evt_upgrade_1",
        "type": "customer.subscription.updated",
        "data": {
            "object": {
                "id": "sub_test_123",
                "customer": "cus_test_123",
                "status": "active",
                "current_period_start": 1704067200,
                "current_period_end": 1706745600,
            }
        },
    }
    payload = json.dumps(payload_dict).encode()
    sig_header, _ = _stripe_signature_payload(payload, TEST_WEBHOOK_SECRET)

    # First delivery
    resp1 = client.post(
        "/webhooks/stripe",
        content=payload,
        headers={"Stripe-Signature": sig_header, "Content-Type": "application/json"},
    )
    assert resp1.status_code == 200
    assert resp1.json()["status"] == "processed"

    # Replay delivery
    resp2 = client.post(
        "/webhooks/stripe",
        content=payload,
        headers={"Stripe-Signature": sig_header, "Content-Type": "application/json"},
    )
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "already processed"

    db = TestingSessionLocal()
    processed = db.query(ProcessedStripeEvent).filter(
        ProcessedStripeEvent.stripe_event_id == "evt_upgrade_1"
    ).all()
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    assert len(processed) == 1
    assert tenant.plan.name == "pro"
    db.close()
