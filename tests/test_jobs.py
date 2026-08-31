from app.jobs.usage_alerts import check_usage_alerts
from tests.conftest import TestingSessionLocal


def test_usage_alert_logs_near_quota(client, free_tenant, caplog):
    tenant_id = free_tenant["id"]

    # Consume 850 API calls (85% of Free 1,000 limit)
    for i in range(850):
        resp = client.post(
            "/generate",
            json={"tenant_id": tenant_id, "api_calls": 1},
            headers={"Idempotency-Key": f"alert-{i}"},
        )
        assert resp.status_code == 200

    db = TestingSessionLocal()
    with caplog.at_level("WARNING", logger="app.jobs.usage_alerts"):
        check_usage_alerts(db)
    db.close()

    assert any("ALERT" in rec.message and str(tenant_id) in rec.message for rec in caplog.records)
