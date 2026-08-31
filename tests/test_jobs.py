from app.jobs.usage_alerts import check_usage_alerts
from app.models import UsageEvent, UsageType
from tests.conftest import TestingSessionLocal


def test_usage_alert_logs_near_quota(client, free_tenant, caplog):
    tenant_id = free_tenant["id"]

    # Seed 850 API-call events directly (faster than 850 HTTP requests).
    db = TestingSessionLocal()
    for i in range(850):
        event = UsageEvent(
            tenant_id=tenant_id,
            type=UsageType.API_CALL,
            quantity=1,
            idempotency_key=f"alert-seed-{i}",
        )
        db.add(event)
    db.commit()

    with caplog.at_level("WARNING", logger="app.jobs.usage_alerts"):
        check_usage_alerts(db)
    db.close()

    assert any("ALERT" in rec.message and str(tenant_id) in rec.message for rec in caplog.records)
