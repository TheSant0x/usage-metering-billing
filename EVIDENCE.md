# Evidence: Definition of Done

This file contains pasted proof for each core checkbox in the capstone brief.

## METERING — idempotent usage recording

**Test**: `tests/test_metering.py::test_idempotency_creates_exactly_one_event`

```
tests/test_metering.py::test_idempotency_creates_exactly_one_event PASSED
```

The same request with the same `Idempotency-Key` returns the same `usage_event_id`; the database contains exactly one event.

## QUOTAS — honest status codes

**Test**: `tests/test_metering.py::test_quota_boundary_free_plan`

```
tests/test_metering.py::test_quota_boundary_free_plan PASSED
```

The 1,000th API call on the Free plan succeeds; the 1,001st returns `429 Too Many Requests` with a clear message.

**Probe transcript** (`scripts/probes.py`):

```
=== PROBE 2: Quota boundary ===
Call 1000: 200 -> {'tenant_id': 2, 'accepted': True, ...}
Call 1001: 429 -> {'detail': 'api_call quota exceeded: used 1000 of 1000 this month; ...'}
PASS: boundary enforced with 429
```

## COST CALCULATION — AI token rules

**Tests**: `tests/test_pricing.py`

```
tests/test_pricing.py::test_cached_input_is_cheaper_than_input PASSED
tests/test_pricing.py::test_reasoning_tokens_count_as_output PASSED
tests/test_pricing.py::test_api_call_cost_is_linear PASSED
tests/test_pricing.py::test_mixed_token_cost PASSED
```

**Probe transcript** (`scripts/probes.py`):

```
=== PROBE 5: Token pricing ===
Generate: 200 -> {'tenant_id': 3, 'accepted': True, ...}
Usage: {'tenant_id': 3, 'plan_name': 'free', ...,
        'items': [
          {'type': 'api_call', 'used': 100, 'limit': 1000, 'cost_cents': 100},
          {'type': 'ai_token', 'used': 100000, 'limit': 100000, 'cost_cents': 8}
        ],
        'total_cost_cents': 108}
PASS: cost math is exact
```

Breakdown:
- 100 API calls × 1¢ = 100¢
- 20,000 input tokens × $0.50/1M = 1¢
- 40,000 cached input tokens × $0.25/1M = 1¢
- 20,000 output + 20,000 reasoning tokens × $1.50/1M = 6¢
- Total = 108¢

## STRIPE INTEGRATION — checkout + webhooks

**Test**: `tests/test_webhooks.py::test_valid_webhook_processed_once_and_upgrades_plan`

```
tests/test_webhooks.py::test_valid_webhook_processed_once_and_upgrades_plan PASSED
```

A signed `customer.subscription.updated` event with `status=active` flips the tenant from Free to Pro; `GET /usage` shows the new limits (10,000 API calls, 1,000,000 AI tokens). Replaying the same event returns `"already processed"` and does not create a second `ProcessedStripeEvent` row.

**Forged webhook test**:

```
tests/test_webhooks.py::test_forged_webhook_returns_400 PASSED
```

A request with a bad `Stripe-Signature` returns `400 Bad Request` and leaves tenant state unchanged.

## DATA MODEL, TESTS & DOCUMENTATION

- Database schema includes `tenants`, `plans`, `usage_events`, `subscriptions`, and `processed_stripe_events`.
- All 9 tests pass:

```
============================== 9 passed in 33.42s ==============================
```

- Required files present: `README.md`, `capstone.yaml`, `BUILDLOG.md`, `EVIDENCE.md`, `.env.example`.

## Full test run

```
$ source .venv/bin/activate && pytest
============================= test session starts ==============================
platform linux -- Python 3.13.12, pytest-9.0.2, pluggy-0.0.0
rootdir: /home/sant0x/FlyRank/Capstone Project
collected 9 items

tests/test_metering.py::test_idempotency_creates_exactly_one_event PASSED [ 11%]
tests/test_metering.py::test_quota_boundary_free_plan PASSED             [ 22%]
tests/test_metering.py::test_payment_required_for_past_due PASSED        [ 33%]
tests/test_pricing.py::test_cached_input_is_cheaper_than_input PASSED    [ 44%]
tests/test_pricing.py::test_reasoning_tokens_count_as_output PASSED      [ 55%]
tests/test_pricing.py::test_api_call_cost_is_linear PASSED              [ 66%]
tests/test_pricing.py::test_mixed_token_cost PASSED                      [ 77%]
tests/test_webhooks.py::test_forged_webhook_returns_400 PASSED           [ 88%]
tests/test_webhooks.py::test_valid_webhook_processed_once_and_upgrades_plan PASSED [100%]

============================== 9 passed in 33.42s ==============================
```
