from app.services.pricing import (
    calculate_token_cost_cents,
    calculate_api_call_cost_cents,
    TOKEN_RATES,
)


def test_cached_input_is_cheaper_than_input():
    qty = 1_000_000
    input_cost = calculate_token_cost_cents(qty, 0, 0, 0)
    cached_cost = calculate_token_cost_cents(0, qty, 0, 0)
    assert cached_cost < input_cost
    assert input_cost == TOKEN_RATES.input_cents_per_1m
    assert cached_cost == TOKEN_RATES.cached_input_cents_per_1m


def test_reasoning_tokens_count_as_output():
    qty = 1_000_000
    output_only = calculate_token_cost_cents(0, 0, qty, 0)
    reasoning_only = calculate_token_cost_cents(0, 0, 0, qty)
    combined = calculate_token_cost_cents(0, 0, qty // 2, qty // 2)
    assert reasoning_only == output_only
    assert combined == output_only


def test_api_call_cost_is_linear():
    assert calculate_api_call_cost_cents(0) == 0
    assert calculate_api_call_cost_cents(1) == 1
    assert calculate_api_call_cost_cents(1000) == 1000


def test_mixed_token_cost():
    # 2M input + 1M cached + 500k output + 500k reasoning
    cost = calculate_token_cost_cents(2_000_000, 1_000_000, 500_000, 500_000)
    # output + reasoning = 1M total output
    expected = 2 * 50 + 1 * 25 + 1 * 150  # cents
    assert cost == expected
