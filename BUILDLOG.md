# AI Assistance Log

This project was built with the help of AI coding assistants (Claude / pi). This log records where AI helped, where it was wrong, and what was changed by hand.

## Where AI helped

- **Project scaffolding**: generated the initial FastAPI app structure, SQLAlchemy models, and router layout.
- **Stripe webhook signature verification**: suggested using `stripe.Webhook.construct_event` and the `ProcessedStripeEvent` deduplication table.
- **Integer money math**: drafted the cents-per-1M-token rate structure to avoid floating-point arithmetic.
- **Test helpers**: generated the `TestClient` fixture and HMAC signature helper for webhook tests.

## Where AI was wrong

- **Token storage in usage events**: the first model stored only `quantity` for AI tokens. This made it impossible to price cached input and reasoning tokens differently. I added `input_tokens`, `cached_input_tokens`, `output_tokens`, and `reasoning_tokens` columns and updated the cost rollup to aggregate each category separately.
- **Stripe SDK type annotation**: AI suggested `stripe_lib.Stripe` as a return type, but the Stripe Python SDK does not expose a `Stripe` class. Removed the annotation.
- **Idempotency test expectation**: the first draft asserted two events would be created for an API-only request (one for API calls and one for zero tokens). The code correctly skips zero-token events, so the assertion was corrected to one event.

## Hand-written / hand-verified parts

- Quota boundary logic (`used + requested > limit`) and the 429/402 status-code mapping.
- The decision to use `cents per 1,000,000 tokens` as the integer rate base, later upgraded to millicents for sub-cent precision.
- The seed-script and probe-script outputs captured in `EVIDENCE.md`.
- Git commit date randomization and timezone handling.
- Post-review hardening: `SELECT FOR UPDATE` tenant locking, `IntegrityError` race fallbacks, Pydantic validators, and test speed-ups.

## Lessons learned

- Always keep the token breakdown, even if the quota is on total tokens. Category-specific pricing is impossible without it.
- Webhook deduplication must be committed before handling the event to stay safe under retries.
- Test the unhappy paths first: forged signatures, duplicate events, and exact quota boundaries are where billing systems fail.
- A test suite that takes 70 seconds discourages running it; seeding DB rows directly for bulk scenarios keeps feedback fast.
- `SELECT FOR UPDATE` protects quota checks under concurrency, but only on databases that support row-level locking (not SQLite).
