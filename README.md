# FlyRank Capstone: Usage Metering & Billing Engine

A small, correct backend service that meters usage, enforces plan quotas, calculates AI-token costs with real-world pricing rules, and syncs subscription state with Stripe in test mode.

## What it does

Every SaaS must answer three questions:

1. How much has this customer used this month?
2. What does it cost?
3. Have they reached their plan limits?

This service answers all three with exactly-once metering, honest quota enforcement, integer money math, and verified Stripe webhooks.

## Architecture

```text
┌─────────┐     POST /generate (Idempotency-Key)     ┌──────────────┐
│  Client │ ───────────────────────────────────────► │   FastAPI    │
└─────────┘                                          └──────┬───────┘
                                                            │
                            ┌───────────────────────────────┼───────────────────────────────┐
                            │                               │                               │
                            ▼                               ▼                               ▼
                    ┌───────────────┐              ┌───────────────┐              ┌───────────────┐
                    │  Tenant CRUD  │              │ MeterService  │              │ Stripe webhook│
                    │   /tenants    │              │  /generate    │              │   /webhooks   │
                    └───────────────┘              └───────┬───────┘              └───────┬───────┘
                                                           │                              │
                              ┌────────────────────────────┘                              │
                              │                                                           │
                              ▼                                                           ▼
                    ┌─────────────────────┐                                    ┌─────────────────────┐
                    │  Quota check        │                                    │ Signature verify    │
                    │  200 / 429 / 402    │                                    │ Deduplicate event   │
                    └─────────────────────┘                                    │ Update tenant plan  │
                                                                               └─────────────────────┘
                                                                                         │
                              ┌──────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────────┐
                    │   UsageEvent table  │
                    │  tenants, plans,    │
                    │  subscriptions,     │
                    │ processed_events    │
                    └─────────────────────┘
```

## Stack

- **Language & framework**: Python 3.11+, FastAPI
- **Database**: SQLite by default (PostgreSQL-compatible schema via SQLAlchemy)
- **Payments**: Stripe Python SDK in test mode
- **Testing**: pytest + FastAPI TestClient

## Setup

```bash
# 1. Clone / enter the repo
python -m venv --system-site-packages .venv
source .venv/bin/activate
pip install stripe==9.7.0          # if system packages already include FastAPI/SQLAlchemy/pytest
# OR on a clean machine:
# pip install -r requirements.txt

cp .env.example .env
# Edit .env with your Stripe test keys (never commit .env)
uvicorn app.main:app --reload
```

## Configuration

Copy `.env.example` to `.env` and fill in:

```bash
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_ID_PRO=price_...
```

The app defaults to SQLite at `./flyrank_billing.db`. Set `DATABASE_URL` to a PostgreSQL connection string for production.

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/tenants` | Create a tenant (Free plan) |
| GET | `/tenants/{tenant_id}` | Read tenant details |
| POST | `/generate` | Dummy billable endpoint; accepts `Idempotency-Key` header |
| GET | `/usage/{tenant_id}` | Monthly usage, limits, and cost |
| POST | `/checkout` | Create Stripe Checkout session for Pro upgrade |
| POST | `/webhooks/stripe` | Receive and verify Stripe events |
| GET | `/docs` | Swagger UI |

## Run & seed

```bash
# Terminal 1
source .venv/bin/activate
uvicorn app.main:app --reload

# Terminal 2
source .venv/bin/activate
python scripts/seed.py
```

## Tests

```bash
source .venv/bin/activate
pytest
```

See [EVIDENCE.md](EVIDENCE.md) for probe transcripts and full test output.

## Idempotency guarantee

The client sends a unique `Idempotency-Key` header with every `/generate` request. The service first checks `usage_events` for that key; if found, it returns the stored result without creating a new row. This guarantees exactly-once recording under network retries.

## Quota enforcement

Before recording usage, the service rolls up the current month's usage and checks `used + requested <= limit`.

- **Free plan exceeded** → `429 Too Many Requests`
- **Lapsed / unpaid subscription** → `402 Payment Required`

## AI token pricing

Money is stored as integer cents. Token rates are cents per 1,000,000 tokens:

| Category | Rate |
|----------|------|
| Input | $0.50 / 1M tokens |
| Cached input | $0.25 / 1M tokens |
| Output | $1.50 / 1M tokens |
| Reasoning | billed as output |

## Stripe webhooks

The `/webhooks/stripe` endpoint:

1. Verifies the Stripe signature (`400` if forged)
2. Deduplicates by Stripe event ID (replays are ignored)
3. Updates the tenant's plan and status

Use the Stripe CLI locally:

```bash
stripe listen --forward-to localhost:8000/webhooks/stripe
stripe trigger customer.subscription.updated
```

## Limitations

- SQLite is used for portability; swap `DATABASE_URL` for PostgreSQL in production.
- No proration, invoicing, or overage billing — these are stretch goals.
- Token costs use integer division of cents-per-1M rates; sub-cent remainders are truncated.
- The checkout success path is verified via mocked Stripe events and webhook tests; real browser checkout requires valid Stripe test keys.

## License

MIT
