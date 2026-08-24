# FlyRank Capstone: Usage Metering & Billing Engine

A small, correct backend service that meters usage, enforces plan quotas, calculates AI-token costs, and syncs subscription state with Stripe in test mode.

## Architecture

```
Client
  │ POST /generate (idempotency-key)
  ▼
MeterService.record()
  ├── duplicate key? → return cached result
  ├── store usage_event
  └── QuotaCheck → allowed / 429 / 402
  │
  ▼
GET /usage → rollup(usage_events) → {used, limit, cost}

Stripe Checkout → customer.subscription.updated
  │
  ▼
POST /webhooks/stripe
  ├── verify signature → forged? 400
  ├── deduplicate event → replay? ignored
  └── update tenant plan/status
```

## Stack

- Python 3.11+
- FastAPI
- SQLAlchemy + SQLite (PostgreSQL-compatible schema)
- Stripe Python SDK (test mode)
- pytest

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Fill in your Stripe test keys
uvicorn app.main:app --reload
```

## API

- `POST /tenants` — create a tenant
- `GET /tenants/{tenant_id}` — read a tenant
- `POST /generate` — dummy billable endpoint
- `GET /usage/{tenant_id}` — monthly usage + cost
- `POST /checkout` — create Stripe Checkout session
- `POST /webhooks/stripe` — Stripe webhook handler
- `GET /docs` — Swagger UI

## Limitations

- SQLite is used for portability; swap `DATABASE_URL` for PostgreSQL in production.
- No proration, invoicing, or overage billing (stretch goals).
- Webhooks are verified against Stripe signatures only; local replay uses the CLI.
- Token costs are computed with integer math; sub-cent values are tracked internally.

## Tests

```bash
pytest
```

See [EVIDENCE.md](EVIDENCE.md) for probe transcripts.
