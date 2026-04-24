# ABOUTME: Tests for the Claude-based claim extractor module.
# ABOUTME: Verifies structured extraction, hash-keyed caching, and CLI integration.

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from analyzer.claim_extractor import (
    ExtractedClaim,
    _cache_path_for_content,
    _load_cached_extraction,
    _save_cached_extraction,
    extract_claims_with_llm,
)
from analyzer.input_handler import Claim, Section


@pytest.fixture
def sample_sections() -> list[Section]:
    return [
        Section(
            title="API Overview",
            content="Claude supports streaming responses. The max_tokens parameter controls output length.",
            level=1,
            start_line=1,
        ),
        Section(
            title="Limits",
            content="The context window is 200k tokens. Output is limited to 8192 tokens.",
            level=1,
            start_line=10,
        ),
    ]


@pytest.fixture
def mock_anthropic_response():
    """Mock Anthropic response carrying structured JSON claims."""
    text_block = MagicMock()
    text_block.text = json.dumps(
        {
            "claims": [
                {
                    "text": "Claude supports streaming responses.",
                    "section_title": "API Overview",
                    "line_number": 2,
                    "category": "capability",
                    "severity_hint": "medium",
                },
                {
                    "text": "The max_tokens parameter controls output length.",
                    "section_title": "API Overview",
                    "line_number": 2,
                    "category": "parameter",
                    "severity_hint": "low",
                },
                {
                    "text": "The context window is 200k tokens.",
                    "section_title": "Limits",
                    "line_number": 11,
                    "category": "limit",
                    "severity_hint": "high",
                },
            ]
        }
    )
    response = MagicMock()
    response.content = [text_block]
    return response


def test_extracted_claim_is_usable_as_claim() -> None:
    """ExtractedClaim must be compatible with Claim — downstream code expects Claim shape."""
    ec = ExtractedClaim(
        text="Claude supports X",
        section_title="Overview",
        line_number=5,
        category="capability",
        severity_hint="medium",
    )
    assert isinstance(ec, Claim)
    assert ec.text == "Claude supports X"
    assert ec.section_title == "Overview"
    assert ec.line_number == 5
    assert ec.category == "capability"
    assert ec.severity_hint == "medium"


@pytest.mark.asyncio
async def test_extract_claims_with_llm_returns_structured_claims(
    sample_sections: list[Section],
    mock_anthropic_response: MagicMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Basic extraction: LLM returns structured claims parsed into ExtractedClaim list."""
    monkeypatch.setenv("HOME", str(tmp_path))

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=mock_anthropic_response)

    claims = await extract_claims_with_llm(sample_sections, client=mock_client)

    assert len(claims) == 3
    assert all(isinstance(c, ExtractedClaim) for c in claims)
    assert claims[0].text == "Claude supports streaming responses."
    assert claims[0].category == "capability"
    assert claims[2].category == "limit"
    assert claims[2].severity_hint == "high"
    mock_client.messages.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_extraction_cached_on_second_call(
    sample_sections: list[Section],
    mock_anthropic_response: MagicMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Second call with identical content must hit cache — no API call."""
    monkeypatch.setenv("HOME", str(tmp_path))

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=mock_anthropic_response)

    await extract_claims_with_llm(sample_sections, client=mock_client)
    await extract_claims_with_llm(sample_sections, client=mock_client)

    mock_client.messages.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_cache_miss_on_different_content(
    sample_sections: list[Section],
    mock_anthropic_response: MagicMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Different content must produce different cache keys — API called twice."""
    monkeypatch.setenv("HOME", str(tmp_path))

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=mock_anthropic_response)

    await extract_claims_with_llm(sample_sections, client=mock_client)

    different_sections = [
        Section(title="Other", content="Completely different text here.", level=1, start_line=1)
    ]
    await extract_claims_with_llm(different_sections, client=mock_client)

    assert mock_client.messages.create.await_count == 2


@pytest.mark.asyncio
async def test_extraction_handles_empty_sections(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty sections must return empty list without an API call."""
    monkeypatch.setenv("HOME", str(tmp_path))
    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock()

    claims = await extract_claims_with_llm([], client=mock_client)

    assert claims == []
    mock_client.messages.create.assert_not_awaited()


def test_cache_path_is_deterministic_by_content(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Same content must map to same path; different content to different paths."""
    monkeypatch.setenv("HOME", str(tmp_path))

    p1 = _cache_path_for_content("hello world")
    p2 = _cache_path_for_content("hello world")
    p3 = _cache_path_for_content("different")

    assert p1 == p2
    assert p1 != p3
    assert p1.name.endswith(".json")


def test_cache_roundtrip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Saved extractions must be retrievable and produce identical ExtractedClaim objects."""
    monkeypatch.setenv("HOME", str(tmp_path))

    claims = [
        ExtractedClaim(
            text="Test claim",
            section_title="Test",
            line_number=1,
            category="capability",
            severity_hint="low",
        )
    ]
    path = _cache_path_for_content("some content")
    _save_cached_extraction(path, claims, model="claude-sonnet-4-6")

    loaded = _load_cached_extraction(path)
    assert loaded is not None
    assert len(loaded) == 1
    assert loaded[0] == claims[0]


def test_cache_returns_none_on_version_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Stale cache schema version must be ignored, not deserialized incorrectly."""
    monkeypatch.setenv("HOME", str(tmp_path))

    path = _cache_path_for_content("x")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"version": 999, "model": "m", "claims": []}))

    assert _load_cached_extraction(path) is None
