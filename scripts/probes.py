"""Run the five acceptance probes against the app in-process."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models import UsageEvent, Tenant, TenantStatus
from app.services.plans import seed_plans

SQLALCHEMY_DATABASE_URL = "sqlite:///./probe_evidence.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
Base.metadata.create_all(bind=engine)
db = TestingSessionLocal()
seed_plans(db)
db.close()

client = TestClient(app)


def probe_1_idempotency():
    print("\n=== PROBE 1: Idempotency ===")
    tenant = client.post("/tenants", json={"name": "P1", "email": "p1@example.com"}).json()
    key = "probe-1-idem"
    r1 = client.post(
        "/generate",
        json={"tenant_id": tenant["id"], "api_calls": 1},
        headers={"Idempotency-Key": key},
    )
    r2 = client.post(
        "/generate",
        json={"tenant_id": tenant["id"], "api_calls": 1},
        headers={"Idempotency-Key": key},
    )
    print(f"Request 1: {r1.status_code} -> {r1.json()}")
    print(f"Request 2: {r2.status_code} -> {r2.json()}")
    assert r1.json()["usage_event_id"] == r2.json()["usage_event_id"]
    db = TestingSessionLocal()
    count = db.query(UsageEvent).filter(UsageEvent.tenant_id == tenant["id"]).count()
    db.close()
    print(f"Usage events recorded for tenant: {count}")
    assert count == 1
    print("PASS: exactly one event recorded")


def probe_2_boundary():
    print("\n=== PROBE 2: Quota boundary ===")
    tenant = client.post("/tenants", json={"name": "P2", "email": "p2@example.com"}).json()
    tid = tenant["id"]
    # 999 calls
    for i in range(999):
        r = client.post(
            "/generate",
            json={"tenant_id": tid, "api_calls": 1},
            headers={"Idempotency-Key": f"p2-{i}"},
        )
        assert r.status_code == 200
    # 1000th call
    r = client.post(
        "/generate",
        json={"tenant_id": tid, "api_calls": 1},
        headers={"Idempotency-Key": "p2-999"},
    )
    print(f"Call 1000: {r.status_code} -> {r.json()}")
    assert r.status_code == 200
    # 1001st call
    r = client.post(
        "/generate",
        json={"tenant_id": tid, "api_calls": 1},
        headers={"Idempotency-Key": "p2-1000"},
    )
    print(f"Call 1001: {r.status_code} -> {r.json()}")
    assert r.status_code == 429
    print("PASS: boundary enforced with 429")


def probe_5_pricing():
    print("\n=== PROBE 5: Token pricing ===")
    tenant = client.post("/tenants", json={"name": "P5", "email": "p5@example.com"}).json()
    tid = tenant["id"]
    r = client.post(
        "/generate",
        json={
            "tenant_id": tid,
            "api_calls": 100,
            "input_tokens": 20_000,
            "cached_input_tokens": 40_000,
            "output_tokens": 20_000,
            "reasoning_tokens": 20_000,
        },
        headers={"Idempotency-Key": "p5-pricing"},
    )
    print(f"Generate: {r.status_code} -> {r.json()}")
    usage = client.get(f"/usage/{tid}").json()
    print(f"Usage: {usage}")
    # Expected: API = 100 cents = 100,000 millicents
    # tokens: input 20k*50/1M=1, cached 40k*25/1M=1, output+reasoning 40k*150/1M=6
    # total = 108 cents = 108,000 millicents
    assert usage["total_cost_cents"] == 108
    assert usage["total_cost_millicents"] == 108_000
    print("PASS: cost math is exact")


def main():
    probe_1_idempotency()
    probe_2_boundary()
    probe_5_pricing()
    print("\nAll probes passed.")


if __name__ == "__main__":
    main()
