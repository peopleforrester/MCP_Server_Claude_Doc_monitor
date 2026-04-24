# ABOUTME: Tests for the cost estimator that pre-flights a drift run via count_tokens.
# ABOUTME: Validates the math so users can trust the dollar figures before paying.

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from analyzer.cost_estimator import (
    CostEstimate,
    estimate_cost,
    model_pricing,
)
from analyzer.input_handler import Claim
from mcp_server.tools.fetch_docs import DocSection


@pytest.fixture
def claims() -> list[Claim]:
    return [
        Claim(text="x", section_title="s", line_number=1),
        Claim(text="y", section_title="s", line_number=2),
    ]


@pytest.fixture
def docs() -> list[DocSection]:
    return [DocSection(title="D", content="body", source_url="https://x")]


@pytest.mark.asyncio
async def test_estimate_cost_returns_all_fields(
    claims: list[Claim], docs: list[DocSection]
) -> None:
    """Estimator surfaces sync cost, batch cost, and token totals."""
    mock_client = MagicMock()
    mock_client.messages.count_tokens = AsyncMock(return_value=MagicMock(input_tokens=100))

    estimate = await estimate_cost(
        claims, docs, model="claude-sonnet-4-6", client=mock_client
    )

    assert isinstance(estimate, CostEstimate)
    assert estimate.input_tokens_per_claim == 100
    assert estimate.total_input_tokens == 200
    assert estimate.sync_cost_usd > 0
    assert estimate.batch_cost_usd > 0
    assert estimate.batch_cost_usd < estimate.sync_cost_usd


@pytest.mark.asyncio
async def test_estimate_cost_batch_is_half_sync(
    claims: list[Claim], docs: list[DocSection]
) -> None:
    """Batch discount must land at exactly 50% input cost."""
    mock_client = MagicMock()
    mock_client.messages.count_tokens = AsyncMock(return_value=MagicMock(input_tokens=1000))

    estimate = await estimate_cost(
        claims, docs, model="claude-sonnet-4-6", client=mock_client
    )

    # Batch input-tokens cost is half; output cost is also half
    pricing = model_pricing("claude-sonnet-4-6")
    expected_sync_input = (2 * 1000 / 1_000_000) * pricing.input_per_mtok
    expected_batch_input = expected_sync_input * 0.5
    assert estimate.sync_input_cost_usd == pytest.approx(expected_sync_input)
    assert estimate.batch_input_cost_usd == pytest.approx(expected_batch_input)


@pytest.mark.asyncio
async def test_estimate_cost_empty_claims_returns_zero(docs: list[DocSection]) -> None:
    """No claims means no cost — don't call count_tokens."""
    mock_client = MagicMock()
    mock_client.messages.count_tokens = AsyncMock()

    estimate = await estimate_cost([], docs, model="claude-sonnet-4-6", client=mock_client)

    assert estimate.sync_cost_usd == 0
    assert estimate.batch_cost_usd == 0
    mock_client.messages.count_tokens.assert_not_awaited()


def test_model_pricing_known_models_have_rates() -> None:
    """Every model ID the project might use must be priced."""
    for model in ("claude-opus-4-6", "claude-sonnet-4-6", "claude-haiku-4-5"):
        p = model_pricing(model)
        assert p.input_per_mtok > 0
        assert p.output_per_mtok > 0


def test_model_pricing_unknown_model_falls_back_to_sonnet() -> None:
    """Unknown model IDs must fall back to Sonnet pricing — never raise."""
    p = model_pricing("some-future-model-id")
    assert p.input_per_mtok > 0
