# ABOUTME: Tests for the batch runner that submits many claims via the Batches API.
# ABOUTME: Verifies request construction, polling, and result parsing.

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from anthropic.types import TextBlock

from analyzer.batch_runner import (
    analyze_claims_batch,
    build_batch_requests,
    parse_batch_results,
    poll_until_complete,
)
from analyzer.drift_detector import DriftResult, DriftStatus
from analyzer.input_handler import Claim
from mcp_server.tools.fetch_docs import DocSection


@pytest.fixture
def claims() -> list[Claim]:
    return [
        Claim(text="Claim A", section_title="S1", line_number=1),
        Claim(text="Claim B", section_title="S2", line_number=5),
    ]


@pytest.fixture
def docs() -> list[DocSection]:
    return [DocSection(title="Doc", content="Doc body.", source_url="https://x/doc")]


def test_build_batch_requests_has_unique_custom_ids(
    claims: list[Claim], docs: list[DocSection]
) -> None:
    """Each claim must map to a unique custom_id so results can be joined back."""
    requests = build_batch_requests(claims, docs, model="claude-sonnet-4-6")

    assert len(requests) == 2
    ids = {r["custom_id"] for r in requests}
    assert len(ids) == 2


def test_build_batch_requests_carries_cached_system_and_docs(
    claims: list[Claim], docs: list[DocSection]
) -> None:
    """Every batch request reuses the cached system prompt + doc corpus."""
    requests = build_batch_requests(claims, docs, model="claude-sonnet-4-6")

    for req in requests:
        params = req["params"]
        # system is a list of blocks with cache_control
        assert isinstance(params["system"], list)
        assert params["system"][-1]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}
        # Last doc block cached
        user_content = params["messages"][0]["content"]
        doc_blocks = [b for b in user_content if b.get("type") == "document"]
        assert doc_blocks[-1]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}


def test_parse_batch_results_maps_custom_id_to_drift_result(
    claims: list[Claim], docs: list[DocSection]
) -> None:
    """Successful batch entries must parse into DriftResult objects keyed by claim."""
    text_block = MagicMock(spec=TextBlock)
    text_block.text = (
        '{"status": "OUTDATED", "reasoning": "old",'
        ' "source_reference": "https://x/doc", "suggested_update": "fix"}'
    )
    text_block.citations = None

    message = MagicMock()
    message.content = [text_block]

    raw_results = [
        MagicMock(
            custom_id="claim-0",
            result=MagicMock(type="succeeded", message=message),
        ),
        MagicMock(
            custom_id="claim-1",
            result=MagicMock(type="succeeded", message=message),
        ),
    ]

    parsed = parse_batch_results(raw_results, claims, docs)

    assert len(parsed) == 2
    assert all(isinstance(r, DriftResult) for r in parsed)
    assert parsed[0].status == DriftStatus.OUTDATED
    assert parsed[0].claim_text == "Claim A"
    assert parsed[1].claim_text == "Claim B"


def test_parse_batch_results_skips_errored_entries(
    claims: list[Claim], docs: list[DocSection]
) -> None:
    """Errored batch entries must be filtered, not crash the parser."""
    text_block = MagicMock(spec=TextBlock)
    text_block.text = '{"status": "CURRENT", "reasoning": "ok", "source_reference": null, "suggested_update": null}'
    text_block.citations = None
    success_message = MagicMock()
    success_message.content = [text_block]

    raw_results = [
        MagicMock(custom_id="claim-0", result=MagicMock(type="succeeded", message=success_message)),
        MagicMock(custom_id="claim-1", result=MagicMock(type="errored", error=MagicMock(message="rate_limit"))),
    ]

    parsed = parse_batch_results(raw_results, claims, docs)
    assert len(parsed) == 1
    assert parsed[0].claim_text == "Claim A"


@pytest.mark.asyncio
async def test_poll_until_complete_waits_for_ended_status() -> None:
    """Poller must loop until processing_status == 'ended', then return the batch."""
    client = MagicMock()
    statuses = ["in_progress", "in_progress", "ended"]
    batches = [MagicMock(processing_status=s, id="batch-1") for s in statuses]
    client.messages.batches.retrieve = AsyncMock(side_effect=batches)

    result = await poll_until_complete("batch-1", client, poll_interval=0)

    assert result.processing_status == "ended"
    assert client.messages.batches.retrieve.await_count == 3


@pytest.mark.asyncio
async def test_analyze_claims_batch_end_to_end(
    claims: list[Claim], docs: list[DocSection], tmp_path: Path
) -> None:
    """The full batch pipeline: submit → poll → parse → DriftResult list."""
    text_block = MagicMock(spec=TextBlock)
    text_block.text = '{"status": "CURRENT", "reasoning": "ok", "source_reference": null, "suggested_update": null}'
    text_block.citations = None
    message = MagicMock()
    message.content = [text_block]

    async def _fake_results_iter(_batch_id: str):
        for cid in ["claim-0", "claim-1"]:
            yield MagicMock(
                custom_id=cid,
                result=MagicMock(type="succeeded", message=message),
            )

    client = MagicMock()
    client.messages.batches.create = AsyncMock(return_value=MagicMock(id="batch-1"))
    client.messages.batches.retrieve = AsyncMock(return_value=MagicMock(id="batch-1", processing_status="ended"))
    client.messages.batches.results = MagicMock(side_effect=_fake_results_iter)

    with patch("analyzer.batch_runner.get_analysis_model", return_value="claude-sonnet-4-6"):
        results = await analyze_claims_batch(claims, docs, client=client, poll_interval=0)

    assert len(results) == 2
    assert all(isinstance(r, DriftResult) for r in results)
