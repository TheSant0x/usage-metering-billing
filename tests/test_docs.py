from fastapi.testclient import TestClient


def test_swagger_ui_reachable(client: TestClient):
    resp = client.get("/docs")
    assert resp.status_code == 200
    assert "Swagger UI" in resp.text or "swagger" in resp.text.lower()


def test_openapi_schema_reachable(client: TestClient):
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()
    paths = schema.get("paths", {})
    assert "/tenants" in paths
    assert "/generate" in paths
    assert "/usage/{tenant_id}" in paths
    assert "/checkout" in paths
    assert "/webhooks/stripe" in paths


def test_full_crud_cycle(client: TestClient):
    # Create
    resp = client.post("/tenants", json={"name": "CRUD", "email": "crud@example.com"})
    assert resp.status_code == 201
    tenant_id = resp.json()["id"]

    # Read
    resp = client.get(f"/tenants/{tenant_id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "CRUD"

    # Usage starts empty
    resp = client.get(f"/usage/{tenant_id}")
    assert resp.status_code == 200
    assert resp.json()["items"][0]["used"] == 0

    # Billable action
    resp = client.post(
        "/generate",
        json={"tenant_id": tenant_id, "api_calls": 1},
        headers={"Idempotency-Key": "crud-1"},
    )
    assert resp.status_code == 200

    # Usage updated
    resp = client.get(f"/usage/{tenant_id}")
    assert resp.status_code == 200
    assert resp.json()["items"][0]["used"] == 1
