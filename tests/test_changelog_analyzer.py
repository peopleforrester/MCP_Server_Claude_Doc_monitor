# ABOUTME: Tests for the changelog analyzer — cross-references training claims vs recent changes.
# ABOUTME: Catches drift caused by deprecations that the per-doc Citations analysis may miss.

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from anthropic.types import TextBlock

from analyzer.changelog_analyzer import (
    ChangelogImpact,
    analyze_changelog_impact,
)
from analyzer.input_handler import Claim
from mcp_server.tools.get_changelog import ChangelogEntry


@pytest.fixture
def claims() -> list[Claim]:
    return [
        Claim(text="Claude 3 Haiku is a great fast model.", section_title="Models", line_number=5),
        Claim(text="The API supports streaming.", section_title="API", line_number=10),
    ]


@pytest.fixture
def entries() -> list[ChangelogEntry]:
    return [
        ChangelogEntry(
            date="2026-04-19",
            title="Claude 3 Haiku retired",
            description="Claude 3 Haiku (claude-3-haiku-20240307) has been retired.",
            source_url="https://x/log",
        ),
        ChangelogEntry(
            date="2026-04-01",
            title="New pricing",
            description="Batch pricing updated for Opus 4.6.",
            source_url="https://x/log",
        ),
    ]


@pytest.mark.asyncio
async def test_analyze_changelog_impact_returns_structured_impacts(
    claims: list[Claim], entries: list[ChangelogEntry]
) -> None:
    """Analyzer returns list of ChangelogImpact with claim_idx / entry_idx / severity."""
    mock_text = MagicMock(spec=TextBlock)
    mock_text.text = json.dumps({
        "impacts": [
            {
                "claim_index": 0,
                "entry_index": 0,
                "severity": "HIGH",
                "explanation": "Haiku 3 was retired on 2026-04-19.",
            }
        ]
    })
    mock_response = MagicMock()
    mock_response.content = [mock_text]

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    with patch("analyzer.changelog_analyzer.get_analysis_model", return_value="claude-sonnet-4-6"):
        impacts = await analyze_changelog_impact(claims, entries, client=mock_client)

    assert len(impacts) == 1
    assert isinstance(impacts[0], ChangelogImpact)
    assert impacts[0].claim_index == 0
    assert impacts[0].entry_index == 0
    assert impacts[0].severity == "HIGH"
    assert impacts[0].claim_text == "Claude 3 Haiku is a great fast model."
    assert impacts[0].entry_title == "Claude 3 Haiku retired"


@pytest.mark.asyncio
async def test_analyze_changelog_impact_empty_inputs_short_circuits(
    claims: list[Claim],
) -> None:
    """No changelog entries means no analysis call — return empty list."""
    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock()
    impacts = await analyze_changelog_impact(claims, [], client=mock_client)
    assert impacts == []
    mock_client.messages.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_analyze_changelog_impact_handles_empty_response(
    claims: list[Claim], entries: list[ChangelogEntry]
) -> None:
    """Response with no impacts must return an empty list, not crash."""
    mock_text = MagicMock(spec=TextBlock)
    mock_text.text = json.dumps({"impacts": []})
    mock_response = MagicMock()
    mock_response.content = [mock_text]

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    with patch("analyzer.changelog_analyzer.get_analysis_model", return_value="claude-sonnet-4-6"):
        impacts = await analyze_changelog_impact(claims, entries, client=mock_client)

    assert impacts == []
