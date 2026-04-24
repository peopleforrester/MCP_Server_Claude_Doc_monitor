# ABOUTME: Opt-in batch-mode runner that submits all claims via the Anthropic Batches API.
# ABOUTME: Trades latency for a 50% discount, stackable with prompt caching for ~10x savings.

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

import anthropic

from analyzer.drift_detector import (
    ANALYSIS_SYSTEM_PROMPT,
    DriftResult,
    DriftStatus,
    _build_document_blocks,
    _build_system_blocks,
    _collect_citations,
    _parse_analysis_response,
)
from analyzer.input_handler import Claim
from config import get_analysis_model
from mcp_server.tools.fetch_docs import DocSection

logger = logging.getLogger(__name__)

DEFAULT_POLL_INTERVAL = 30  # seconds
DEFAULT_POLL_TIMEOUT = 7200  # 2 hours


def _claim_block(claim: Claim) -> dict[str, Any]:
    return {
        "type": "text",
        "text": (
            f'Claim to analyze:\n"{claim.text}"\n\n'
            "Analyze this claim against the attached documents and respond with "
            "the JSON object described in your instructions."
        ),
    }


def build_batch_requests(
    claims: list[Claim], docs: list[DocSection], model: str, max_tokens: int = 1024
) -> list[dict[str, Any]]:
    """Build one batch Request per claim, sharing cached system prompt and doc corpus."""
    document_blocks = _build_document_blocks(docs)
    system_blocks = _build_system_blocks()

    requests: list[dict[str, Any]] = []
    for i, claim in enumerate(claims):
        requests.append({
            "custom_id": f"claim-{i}",
            "params": {
                "model": model,
                "max_tokens": max_tokens,
                "system": system_blocks,
                "messages": [{
                    "role": "user",
                    "content": [*document_blocks, _claim_block(claim)],
                }],
            },
        })
    return requests


async def poll_until_complete(
    batch_id: str,
    client: anthropic.AsyncAnthropic,
    poll_interval: int = DEFAULT_POLL_INTERVAL,
    timeout: int = DEFAULT_POLL_TIMEOUT,
    progress_cb: Any = None,
) -> Any:
    """Poll the batch until its processing_status == 'ended', return the final batch object."""
    elapsed = 0
    while True:
        batch = await client.messages.batches.retrieve(batch_id)
        if progress_cb is not None:
            progress_cb(batch)
        if batch.processing_status == "ended":
            return batch
        if elapsed >= timeout:
            raise TimeoutError(
                f"Batch {batch_id} still {batch.processing_status} after {timeout}s"
            )
        if poll_interval > 0:
            await asyncio.sleep(poll_interval)
        elapsed += poll_interval


def parse_batch_results(
    raw_results: list[Any], claims: list[Claim], docs: list[DocSection]
) -> list[DriftResult]:
    """Map batch entries back to DriftResult objects using the custom_id claim index."""
    parsed: list[DriftResult] = []
    for entry in raw_results:
        custom_id = entry.custom_id
        result = entry.result
        if getattr(result, "type", None) != "succeeded":
            err = getattr(getattr(result, "error", None), "message", "unknown")
            logger.warning("Batch entry %s failed: %s", custom_id, err)
            continue

        try:
            claim_idx = int(custom_id.rsplit("-", 1)[1])
        except (IndexError, ValueError):
            logger.warning("Unrecognized custom_id format: %s", custom_id)
            continue
        if claim_idx < 0 or claim_idx >= len(claims):
            logger.warning("custom_id %s points past the claim list", custom_id)
            continue
        claim = claims[claim_idx]

        message = result.message
        response_text = ""
        for block in message.content:
            text = getattr(block, "text", None)
            if text:
                response_text += text

        if not response_text:
            logger.warning("Empty response text for %s", custom_id)
            continue

        analysis = _parse_analysis_response(response_text)
        evidence = _collect_citations(message, docs)

        parsed.append(DriftResult(
            claim_text=claim.text,
            section_title=claim.section_title,
            line_number=claim.line_number,
            status=DriftStatus(analysis["status"]),
            reasoning=analysis["reasoning"],
            source_reference=analysis.get("source_reference"),
            suggested_update=analysis.get("suggested_update"),
            evidence=evidence,
        ))
    return parsed


async def analyze_claims_batch(
    claims: list[Claim],
    docs: list[DocSection],
    client: anthropic.AsyncAnthropic | None = None,
    config_path: Path | None = None,
    poll_interval: int = DEFAULT_POLL_INTERVAL,
    progress_cb: Any = None,
) -> list[DriftResult]:
    """End-to-end batch pipeline: submit, poll, retrieve, parse.

    Trades 5min-1hr latency for 50% cost reduction vs. sync analysis; combined
    with prompt caching on the system prompt and doc corpus, cost per claim
    drops to roughly a tenth of the sync path.
    """
    if not claims:
        return []
    if client is None:
        client = anthropic.AsyncAnthropic()

    model = get_analysis_model(config_path)
    requests = build_batch_requests(claims, docs, model=model)
    logger.info("Submitting batch with %d claim requests", len(requests))

    # SDK's Request type is a TypedDict; runtime accepts dicts of the same shape.
    create: Any = client.messages.batches.create
    batch = await create(requests=requests)
    await poll_until_complete(batch.id, client, poll_interval=poll_interval, progress_cb=progress_cb)

    # SDK's .results() is an awaitable that resolves to an async-iterable decoder.
    # Tests mock it as sync-return of an async generator, so handle both forms.
    results_fn: Any = client.messages.batches.results
    results_obj = results_fn(batch.id)
    if asyncio.iscoroutine(results_obj):
        results_obj = await results_obj
    raw_results = [r async for r in results_obj]
    return parse_batch_results(raw_results, claims, docs)


# Re-exporting ANALYSIS_SYSTEM_PROMPT so consumers of batch_runner don't need
# to reach into drift_detector for prompt customization.
__all__ = [
    "ANALYSIS_SYSTEM_PROMPT",
    "analyze_claims_batch",
    "build_batch_requests",
    "parse_batch_results",
    "poll_until_complete",
]
