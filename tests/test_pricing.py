from app.services.pricing import (
    calculate_token_cost_millicents,
    calculate_api_call_cost_millicents,
    millicents_to_cents,
    TOKEN_RATES,
    MILLICENTS_PER_CENT,
)


def test_cached_input_is_cheaper_than_input():
    qty = 1_000_000
    input_cost = calculate_token_cost_millicents(qty, 0, 0, 0)
    cached_cost = calculate_token_cost_millicents(0, qty, 0, 0)
    assert cached_cost < input_cost
    assert input_cost == TOKEN_RATES.input_millicents_per_1m
    assert cached_cost == TOKEN_RATES.cached_input_millicents_per_1m


def test_reasoning_tokens_count_as_output():
    qty = 1_000_000
    output_only = calculate_token_cost_millicents(0, 0, qty, 0)
    reasoning_only = calculate_token_cost_millicents(0, 0, 0, qty)
    combined = calculate_token_cost_millicents(0, 0, qty // 2, qty // 2)
    assert reasoning_only == output_only
    assert combined == output_only


def test_api_call_cost_is_linear():
    assert calculate_api_call_cost_millicents(0) == 0
    assert calculate_api_call_cost_millicents(1) == MILLICENTS_PER_CENT
    assert calculate_api_call_cost_millicents(1000) == 1000 * MILLICENTS_PER_CENT


def test_millicents_to_cents_rounds_correctly():
    assert millicents_to_cents(0) == 0
    assert millicents_to_cents(499) == 0
    assert millicents_to_cents(500) == 1
    assert millicents_to_cents(1_000) == 1
    assert millicents_to_cents(1_500) == 2


def test_millicents_improves_rounding_vs_cents_truncation():
    # 30,000 input tokens at $0.50/1M = 1.5 cents.
    # With integer-cent truncation this becomes 1 cent.
    # With millicents it stays 1,500 millicents and rounds to 2 cents.
    millicents = calculate_token_cost_millicents(30_000, 0, 0, 0)
    cents = millicents_to_cents(millicents)
    assert millicents == 1_500
    assert cents == 2


def test_mixed_token_cost():
    # 2M input + 1M cached + 500k output + 500k reasoning
    cost = calculate_token_cost_millicents(2_000_000, 1_000_000, 500_000, 500_000)
    # output + reasoning = 1M total output
    expected = 2 * 50_000 + 1 * 25_000 + 1 * 150_000  # millicents
    assert cost == expected
