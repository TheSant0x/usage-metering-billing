"""Seed a demo tenant and exercise the core probes locally."""
import httpx

BASE_URL = "http://localhost:8000"


def main():
    with httpx.Client(base_url=BASE_URL, timeout=10) as client:
        # Create tenant
        resp = client.post("/tenants", json={"name": "Demo Tenant", "email": "demo@example.com"})
        print("CREATE TENANT:", resp.status_code, resp.json())
        tenant_id = resp.json()["id"]

        # Record usage within Free plan limits (<= 100k AI tokens total)
        resp = client.post(
            "/generate",
            json={
                "tenant_id": tenant_id,
                "api_calls": 1,
                "input_tokens": 20_000,
                "cached_input_tokens": 40_000,
                "output_tokens": 20_000,
                "reasoning_tokens": 20_000,
            },
            headers={"Idempotency-Key": "seed-demo-1"},
        )
        print("GENERATE:", resp.status_code, resp.json())

        # Check usage
        resp = client.get(f"/usage/{tenant_id}")
        print("USAGE:", resp.status_code, resp.json())


if __name__ == "__main__":
    main()
