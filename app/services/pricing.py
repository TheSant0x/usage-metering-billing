"""
Integer money math for AI token pricing.

Money is tracked in integer cents. Token rates are stored as cents per 1M tokens
so no floats are needed. Costs are computed with integer arithmetic; sub-cent
precision is rounded to the nearest cent at display time.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class TokenRates:
    input_cents_per_1m: int
    cached_input_cents_per_1m: int
    output_cents_per_1m: int


# Realistic test-mode rates.
TOKEN_RATES = TokenRates(
    input_cents_per_1m=50,          # $0.50 / 1M input tokens
    cached_input_cents_per_1m=25,   # $0.25 / 1M cached input tokens
    output_cents_per_1m=150,        # $1.50 / 1M output tokens
)

API_CALL_COST_CENTS = 1  # 1 cent per API call


def calculate_token_cost_cents(
    input_tokens: int,
    cached_input_tokens: int,
    output_tokens: int,
    reasoning_tokens: int,
) -> int:
    """
    Calculate total token cost in integer cents.

    Rules:
      * cached input tokens are priced cheaper than fresh input
      * reasoning tokens count as output tokens
    """
    rates = TOKEN_RATES
    input_cost = (input_tokens * rates.input_cents_per_1m) // 1_000_000
    cached_cost = (cached_input_tokens * rates.cached_input_cents_per_1m) // 1_000_000
    total_output_tokens = output_tokens + reasoning_tokens
    output_cost = (total_output_tokens * rates.output_cents_per_1m) // 1_000_000
    return input_cost + cached_cost + output_cost


def calculate_api_call_cost_cents(api_calls: int) -> int:
    return api_calls * API_CALL_COST_CENTS
