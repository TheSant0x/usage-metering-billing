# Design Document: Usage Metering & Billing Engine

## Problem

A multi-tenant SaaS needs to answer three questions for every customer:
1. How much has this tenant used this month?
2. What does it cost?
3. Have they hit their plan limits?

This service provides idempotent usage metering, honest quota enforcement, AI-token cost math, and Stripe subscription sync.

## Data Model

### `Tenant`
- `id` (PK)
- `name`, `email`
- `plan_id` → Plan
- `stripe_customer_id`
- `status`: active / past_due / canceled

### `Plan`
- `id` (PK)
- `name`: Free / Pro
- `api_calls_limit`: monthly allowed API calls
- `ai_tokens_limit`: monthly allowed AI tokens
- `price_cents`: monthly subscription price
- `stripe_price_id`

### `UsageEvent`
- `id` (PK)
- `tenant_id` → Tenant
- `type`: api_call / ai_token
- `quantity`: integer count
- `idempotency_key`: unique per external request
- `created_at`
- Composite index on `(tenant_id, type, created_at)` for fast rollups

### `Subscription` (mirror of Stripe state)
- `id` (PK)
- `tenant_id` → Tenant
- `stripe_subscription_id`
- `status`
- `current_period_start/end`

### `ProcessedStripeEvent`
- `id` (PK)
- `stripe_event_id`: Stripe event idempotency
- `type`
- `processed_at`

## API Surface

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/tenants` | Create tenant |
| GET | `/tenants/{id}` | Read tenant |
| POST | `/generate` | Dummy billable action |
| GET | `/usage/{tenant_id}` | Monthly usage + cost |
| POST | `/checkout` | Start Pro upgrade Checkout |
| POST | `/webhooks/stripe` | Receive Stripe events |
| GET | `/docs` | Swagger UI |

## Layers

```
HTTP (FastAPI routers)
    │
    ▼
Service (MeterService, BillingService, StripeService)
    │
    ▼
Repository (SQLAlchemy models / queries)
    │
    ▼
Database (SQLite / PostgreSQL)
```

Business logic lives in services; HTTP layer only validates and serializes.

## Idempotency Strategy

The client sends an `Idempotency-Key` header. The service:
1. Locks/selects existing `UsageEvent` by key.
2. If found, returns the stored response without creating a new row.
3. If not found, records the event inside a transaction and returns the result.

This guarantees exactly-once recording even under network retries.

## Quota Enforcement

Before recording usage, the service rolls up the tenant's current month usage for the relevant type and checks `used + requested <= limit`. Free plan returns `429 Too Many Requests`; a lapsed Pro subscription returns `402 Payment Required`.

## Cost Calculation

Money is stored as integer cents. Token pricing follows real-world rules:
- Cached input tokens are cheaper than fresh input.
- Reasoning tokens are billed as output tokens.

Rates are pinned in config and tested.

## Explicit Non-Goal

Proration, invoicing, and overage billing are intentionally out of scope. They are listed as stretch goals and would add significant complexity without exercising the core correctness requirements.
