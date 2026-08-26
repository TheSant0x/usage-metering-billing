from fastapi.testclient import TestClient

from app.models import UsageEvent
from tests.conftest import TestingSessionLocal


def test_idempotency_creates_exactly_one_event(client: TestClient, free_tenant):
    tenant_id = free_tenant["id"]
    key = "idem-test-1"

    resp1 = client.post(
        "/generate",
        json={"tenant_id": tenant_id, "api_calls": 1},
        headers={"Idempotency-Key": key},
    )
    assert resp1.status_code == 200
    data1 = resp1.json()

    resp2 = client.post(
        "/generate",
        json={"tenant_id": tenant_id, "api_calls": 1},
        headers={"Idempotency-Key": key},
    )
    assert resp2.status_code == 200
    data2 = resp2.json()

    assert data1["usage_event_id"] == data2["usage_event_id"]

    db = TestingSessionLocal()
    events = db.query(UsageEvent).filter(UsageEvent.tenant_id == tenant_id).all()
    db.close()
    # one API call event + one token event (zero tokens) = 2 rows, both sharing the key prefix
    assert len(events) == 2


def test_quota_boundary_free_plan(client: TestClient, free_tenant):
    tenant_id = free_tenant["id"]
    # Free plan: 1,000 API calls per month.
    # Drive tenant to exactly 999 calls with individual requests.
    for i in range(999):
        resp = client.post(
            "/generate",
            json={"tenant_id": tenant_id, "api_calls": 1},
            headers={"Idempotency-Key": f"boundary-{i}"},
        )
        assert resp.status_code == 200, f"failed at call {i}: {resp.text}"

    # The 1,000th call should still succeed (boundary inclusive).
    resp = client.post(
        "/generate",
        json={"tenant_id": tenant_id, "api_calls": 1},
        headers={"Idempotency-Key": "boundary-999"},
    )
    assert resp.status_code == 200

    # The 1,001st call must be rejected with 429.
    resp = client.post(
        "/generate",
        json={"tenant_id": tenant_id, "api_calls": 1},
        headers={"Idempotency-Key": "boundary-1000"},
    )
    assert resp.status_code == 429
    assert "quota exceeded" in resp.json()["detail"].lower()


def test_payment_required_for_past_due(client: TestClient, free_tenant):
    from app.models import Tenant, TenantStatus

    tenant_id = free_tenant["id"]
    db = TestingSessionLocal()
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    tenant.status = TenantStatus.PAST_DUE
    db.commit()
    db.close()

    resp = client.post(
        "/generate",
        json={"tenant_id": tenant_id, "api_calls": 1},
        headers={"Idempotency-Key": "past-due-1"},
    )
    assert resp.status_code == 402
    assert "payment" in resp.json()["detail"].lower()
