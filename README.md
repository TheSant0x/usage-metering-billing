# FlyRank Capstone: Usage Metering & Billing Engine

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111%2B-009688)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A production-oriented backend service that answers the three questions every SaaS must get right:

1. **How much has this customer used?**
2. **What does it cost?**
3. **Have they hit their plan limits?**

Built with **FastAPI**, **SQLAlchemy**, and **Stripe test mode**, this project demonstrates exactly-once usage metering, honest quota enforcement, integer money math for AI-token pricing, and cryptographically verified Stripe webhooks.

---

## Table of Contents

- [Architecture](#architecture)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [API Reference](#api-reference)
- [Running Tests](#running-tests)
- [Acceptance Probes](#acceptance-probes)
- [Project Structure](#project-structure)
- [Design Decisions](#design-decisions)
- [Limitations & Roadmap](#limitations--roadmap)
- [License](#license)

---

## Architecture

```text
                    ┌─────────────────────────────────────────────────────────────┐
                    │                        FastAPI App                          │
                    │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
     Client ───────►│  │ /tenants    │  │ /generate   │  │ /webhooks/stripe    │  │
                    │  │ CRUD        │  │ Idempotency │  │ Signature + dedup   │  │
                    │  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘  │
                    └─────────┼────────────────┼────────────────────┼─────────────┘
                              │                │                    │
                              ▼                ▼                    ▼
                    ┌─────────────────────────────────────────────────────────────┐
                    │                         Service Layer                         │
                    │   MeterService          PricingService        StripeService   │
                    │   - quota check         - integer cents       - checkout      │
                    │   - idempotent record   - token breakdown     - webhook sync  │
                    └────────────────────────────┬──────────────────────────────────┘
                                                 │
                              ┌──────────────────┼──────────────────┐
                              │                  │                  │
                              ▼                  ▼                  ▼
                    ┌─────────────────┐ ┌───────────────┐ ┌─────────────────────┐
                    │   tenants       │ │ usage_events  │ │ processed_stripe_   │
                    │   plans         │ │ subscriptions │ │ events              │
                    └─────────────────┘ └───────────────┘ └─────────────────────┘
```

---

## Features

| Capability | Implementation |
|------------|----------------|
| **Idempotent metering** | `Idempotency-Key` header + unique DB constraint + `IntegrityError` fallback |
| **Quota enforcement** | `used + requested > limit` check before any write; returns `429` or `402` |
| **AI token pricing** | Cached input cheaper; reasoning tokens billed as output; integer cents |
| **Stripe integration** | Test-mode Checkout + signature-verified, deduplicated webhooks |
| **Subscription sync** | `customer.subscription.updated/deleted` flips tenant plan Free ↔ Pro |
| **Background jobs** | In-process usage-alert scheduler (production: swap for Celery/RQ) |
| **OpenAPI / Swagger** | `GET /docs` interactive documentation |

---

## Tech Stack

- **Runtime**: Python 3.11+
- **Web framework**: FastAPI
- **ORM**: SQLAlchemy 2.0
- **Database**: SQLite (default), PostgreSQL-ready
- **Payments**: Stripe Python SDK (test mode only)
- **Validation**: Pydantic v2
- **Testing**: pytest + FastAPI TestClient

---

## Quick Start

```bash
# 1. Clone the repo and create a virtual environment
git clone <repo-url>
cd flyrank-capstone-metering-billing
python -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment variables
cp .env.example .env
# Edit .env and add your Stripe test keys (never commit .env)

# 4. Run the server
uvicorn app.main:app --reload

# 5. Open Swagger UI
open http://localhost:8000/docs
```

### Seed demo data

With the server running:

```bash
source .venv/bin/activate
python scripts/seed.py
```

---

## Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | No | `sqlite:///./flyrank_billing.db` | SQLAlchemy database URL |
| `APP_BASE_URL` | No | `http://localhost:8000` | Public URL for Stripe redirects |
| `STRIPE_SECRET_KEY` | For Checkout | — | `sk_test_...` |
| `STRIPE_WEBHOOK_SECRET` | For webhooks | — | `whsec_...` |
| `STRIPE_PRICE_ID_PRO` | For Checkout | — | `price_...` for Pro plan |

---

## API Reference

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/tenants` | Create a tenant on the Free plan |
| `GET` | `/tenants/{tenant_id}` | Read tenant details |
| `POST` | `/generate` | Dummy billable endpoint; requires `Idempotency-Key` header |
| `GET` | `/usage/{tenant_id}` | Monthly usage, limits, and cost rollup |
| `POST` | `/checkout` | Create a Stripe Checkout session to upgrade to Pro |
| `POST` | `/webhooks/stripe` | Stripe webhook endpoint |
| `GET` | `/docs` | Swagger UI |

### Example: record usage

```bash
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: req-001" \
  -d '{
    "tenant_id": 1,
    "api_calls": 1,
    "input_tokens": 20000,
    "cached_input_tokens": 40000,
    "output_tokens": 20000,
    "reasoning_tokens": 20000
  }'
```

### Example: check usage

```bash
curl http://localhost:8000/usage/1
```

---

## Running Tests

```bash
source .venv/bin/activate
pytest
```

All 13 tests run in-process via `TestClient` (no real network sockets required).

---

## Acceptance Probes

The capstone probes are exercised in `scripts/probes.py` and the test suite:

1. **Idempotency** — same `Idempotency-Key` produces exactly one `UsageEvent`.
2. **Quota boundary** — call 1,000 succeeds; call 1,001 returns `429`.
3. **Stripe upgrade** — webhook flips tenant Free → Pro; `/usage` reflects new limits.
4. **Webhook security** — forged signature returns `400`; replayed event is ignored.
5. **Token pricing** — cached input cheaper; reasoning tokens count as output; integer cents.

See [`EVIDENCE.md`](EVIDENCE.md) for pasted transcripts.

---

## Project Structure

```text
.
├── app/
│   ├── config.py              # Pydantic settings
│   ├── database.py            # SQLAlchemy engine & session
│   ├── main.py                # FastAPI app + lifespan
│   ├── models.py              # Database models
│   ├── schemas.py             # Pydantic request/response models
│   ├── jobs/                  # Background scheduler + usage alerts
│   ├── routers/               # HTTP route handlers
│   └── services/              # Business logic (meter, pricing, Stripe)
├── scripts/
│   ├── seed.py                # Demo data seed
│   └── probes.py              # Acceptance probe runner
├── tests/                     # pytest suite
├── BUILDLOG.md                # AI assistance log
├── DESIGN.md                  # Design document
├── EVIDENCE.md                # Verification transcripts
├── capstone.yaml              # Evaluator manifest
├── requirements.txt           # Pinned dependencies
└── README.md                  # This file
```

---

## Design Decisions

- **Integer money**: all stored prices and computed costs use integer cents. Token rates are expressed as cents per 1,000,000 tokens to avoid floating-point arithmetic.
- **Idempotency**: a unique constraint on `usage_events.idempotency_key` is the final guard against double-recording under concurrent retries.
- **Webhook safety**: events are persisted to `processed_stripe_events` before handling so replays are always idempotent, even if the handler crashes mid-flight.
- **Layered architecture**: routers validate and serialize; services contain business logic; models define the schema. Swapping SQLite for PostgreSQL requires only a connection-string change.

---

## Limitations & Roadmap

- **SQLite** is used for portability; production should use PostgreSQL.
- **Token cost precision**: sub-cent remainders from `cents-per-1M` rates are truncated. For higher precision, use millicents internally.
- **No proration, invoicing, or overage billing** — these are deliberate stretch goals.
- **In-process scheduler** is fine for demos; replace with Celery/RQ and a persistent broker in production.
- **No authentication/authorization** in this scope; every endpoint trusts the `tenant_id` supplied by the caller.

---

## License

This project is licensed under the [MIT License](LICENSE).
