"""Concurrency tests for quota and idempotency guarantees.

Note: these tests verify behavior under a real database that supports row-level
locking (e.g., PostgreSQL). SQLite serializes at the database level, so the
concurrency test is skipped when running against SQLite.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest
from fastapi.testclient import TestClient

from app.database import engine
from app.models import UsageEvent, UsageType
from tests.conftest import TestingSessionLocal


pytestmark = pytest.mark.skipif(
    engine.dialect.name == "sqlite",
    reason="SQLite does not support row-level FOR UPDATE locking",
)


def _post_generate(tenant_id: int, key: str):
    client = TestClient(__import__("app.main", fromlist=["app"]).app)
    return client.post(
        "/generate",
        json={"tenant_id": tenant_id, "api_calls": 1},
        headers={"Idempotency-Key": key},
    )


def test_concurrent_requests_honor_quota(client: TestClient, free_tenant):
    tenant_id = free_tenant["id"]

    # Seed 998 API-call events so 2 more will hit the 1,000 limit.
    db = TestingSessionLocal()
    for i in range(998):
        db.add(
            UsageEvent(
                tenant_id=tenant_id,
                type=UsageType.API_CALL,
                quantity=1,
                idempotency_key=f"concurrent-seed-{i}",
            )
        )
    db.commit()
    db.close()

    # Fire 5 concurrent requests.
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [
            executor.submit(_post_generate, tenant_id, f"concurrent-{i}")
            for i in range(5)
        ]
        statuses = [f.result().status_code for f in as_completed(futures)]

    successes = statuses.count(200)
    failures = statuses.count(429)

    db = TestingSessionLocal()
    total = (
        db.query(UsageEvent)
        .filter(UsageEvent.tenant_id == tenant_id, UsageEvent.type == UsageType.API_CALL)
        .count()
    )
    db.close()

    # Exactly 2 should succeed, 3 should be rejected, and total must be 1,000.
    assert successes == 2, f"expected 2 successes, got {successes}; statuses={statuses}"
    assert failures == 3, f"expected 3 failures, got {failures}; statuses={statuses}"
    assert total == 1000, f"expected total 1000, got {total}"
