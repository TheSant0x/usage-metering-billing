"""
Integer money math for AI token pricing.

Money is tracked in integer millicents (1/1000 of a cent) for sub-cent precision.
Plan prices and displayed costs are rounded to integer cents. This avoids all
floating-point arithmetic while still pricing small token counts accurately.
"""
from dataclasses import dataclass


MILLICENTS_PER_CENT = 1000


@dataclass(frozen=True)
class TokenRates:
    input_millicents_per_1m: int
    cached_input_millicents_per_1m: int
    output_millicents_per_1m: int


# Realistic test-mode rates.
TOKEN_RATES = TokenRates(
    input_millicents_per_1m=50_000,          # $0.50 / 1M input tokens
    cached_input_millicents_per_1m=25_000,   # $0.25 / 1M cached input tokens
    output_millicents_per_1m=150_000,        # $1.50 / 1M output tokens
)

API_CALL_COST_MILLICENTS = 1_000  # 1 cent = 1000 millicents per API call


def calculate_token_cost_millicents(
    input_tokens: int,
    cached_input_tokens: int,
    output_tokens: int,
    reasoning_tokens: int,
) -> int:
    """
    Calculate total token cost in integer millicents.

    Rules:
      * cached input tokens are priced cheaper than fresh input
      * reasoning tokens count as output tokens
    """
    rates = TOKEN_RATES
    input_cost = (input_tokens * rates.input_millicents_per_1m) // 1_000_000
    cached_cost = (cached_input_tokens * rates.cached_input_millicents_per_1m) // 1_000_000
    total_output_tokens = output_tokens + reasoning_tokens
    output_cost = (total_output_tokens * rates.output_millicents_per_1m) // 1_000_000
    return input_cost + cached_cost + output_cost


def calculate_api_call_cost_millicents(api_calls: int) -> int:
    return api_calls * API_CALL_COST_MILLICENTS


def millicents_to_cents(millicents: int) -> int:
    """Round millicents to nearest integer cents for display."""
    return (millicents + MILLICENTS_PER_CENT // 2) // MILLICENTS_PER_CENT
