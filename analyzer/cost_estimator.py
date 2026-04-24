# ABOUTME: Pre-flight cost estimator using the Anthropic count_tokens API and current pricing.
# ABOUTME: Surfaces sync vs batch costs so users decide before paying.

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import anthropic

from analyzer.drift_detector import (
    _build_document_blocks,
    _build_system_blocks,
)
from analyzer.input_handler import Claim
from mcp_server.tools.fetch_docs import DocSection


@dataclass
class ModelPricing:
    input_per_mtok: float
    output_per_mtok: float


# Pricing as of April 2026. Update when Anthropic publishes changes.
# Source: https://platform.claude.com/docs/en/about-claude/pricing
_PRICING: dict[str, ModelPricing] = {
    "claude-opus-4-6": ModelPricing(input_per_mtok=5.0, output_per_mtok=25.0),
    "claude-sonnet-4-6": ModelPricing(input_per_mtok=3.0, output_per_mtok=15.0),
    "claude-haiku-4-5": ModelPricing(input_per_mtok=1.0, output_per_mtok=5.0),
}

# Conservative estimate of output tokens per claim — drift responses are terse JSON.
_OUTPUT_TOKENS_PER_CLAIM = 200


def model_pricing(model: str) -> ModelPricing:
    """Return pricing for a model ID, falling back to Sonnet if unknown."""
    # Strip any date suffix that some callers may still include (e.g. -20260220)
    base = model
    for key in _PRICING:
        if base.startswith(key):
            return _PRICING[key]
    return _PRICING["claude-sonnet-4-6"]


@dataclass
class CostEstimate:
    model: str
    claim_count: int
    input_tokens_per_claim: int
    total_input_tokens: int
    output_tokens_per_claim: int
    total_output_tokens: int
    sync_input_cost_usd: float
    sync_output_cost_usd: float
    sync_cost_usd: float
    batch_input_cost_usd: float
    batch_output_cost_usd: float
    batch_cost_usd: float

    def format_summary(self) -> str:
        return (
            f"Cost estimate ({self.model}, {self.claim_count} claims):\n"
            f"  Input tokens: {self.total_input_tokens:,} "
            f"({self.input_tokens_per_claim:,}/claim)\n"
            f"  Output tokens: ~{self.total_output_tokens:,} "
            f"({self.output_tokens_per_claim}/claim, estimate)\n"
            f"  Sync cost:  ${self.sync_cost_usd:.4f}\n"
            f"  Batch cost: ${self.batch_cost_usd:.4f}  (50% off, up to 1h latency)\n"
            f"  Note: prompt caching reduces actual sync cost on claims 2+"
        )


async def estimate_cost(
    claims: list[Claim],
    docs: list[DocSection],
    model: str,
    client: anthropic.AsyncAnthropic | None = None,
    config_path: Path | None = None,
) -> CostEstimate:
    """Estimate total cost for a drift run at the given model + batch setting.

    Counts tokens for a single representative claim via the free count_tokens
    endpoint, then multiplies by claim count. Output tokens are estimated since
    they're only knowable after the run — we use a conservative 200/claim.
    """
    pricing = model_pricing(model)

    if not claims:
        return CostEstimate(
            model=model, claim_count=0,
            input_tokens_per_claim=0, total_input_tokens=0,
            output_tokens_per_claim=_OUTPUT_TOKENS_PER_CLAIM,
            total_output_tokens=0,
            sync_input_cost_usd=0.0, sync_output_cost_usd=0.0, sync_cost_usd=0.0,
            batch_input_cost_usd=0.0, batch_output_cost_usd=0.0, batch_cost_usd=0.0,
        )

    if client is None:
        client = anthropic.AsyncAnthropic()

    # Build a single representative request for the first claim.
    doc_blocks = _build_document_blocks(docs)
    system_blocks = _build_system_blocks()
    claim = claims[0]
    claim_block: dict[str, Any] = {
        "type": "text",
        "text": (
            f'Claim to analyze:\n"{claim.text}"\n\n'
            "Analyze this claim against the attached documents and respond with "
            "the JSON object described in your instructions."
        ),
    }

    system_any: Any = system_blocks
    content_any: Any = [*doc_blocks, claim_block]

    resp = await client.messages.count_tokens(
        model=model,
        system=system_any,
        messages=[{"role": "user", "content": content_any}],
    )
    tokens_per_claim = int(resp.input_tokens)
    total_input = tokens_per_claim * len(claims)
    total_output = _OUTPUT_TOKENS_PER_CLAIM * len(claims)

    sync_input = (total_input / 1_000_000) * pricing.input_per_mtok
    sync_output = (total_output / 1_000_000) * pricing.output_per_mtok
    batch_input = sync_input * 0.5
    batch_output = sync_output * 0.5

    return CostEstimate(
        model=model,
        claim_count=len(claims),
        input_tokens_per_claim=tokens_per_claim,
        total_input_tokens=total_input,
        output_tokens_per_claim=_OUTPUT_TOKENS_PER_CLAIM,
        total_output_tokens=total_output,
        sync_input_cost_usd=sync_input,
        sync_output_cost_usd=sync_output,
        sync_cost_usd=sync_input + sync_output,
        batch_input_cost_usd=batch_input,
        batch_output_cost_usd=batch_output,
        batch_cost_usd=batch_input + batch_output,
    )
