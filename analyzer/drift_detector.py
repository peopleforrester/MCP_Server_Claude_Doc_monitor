# ABOUTME: Drift detector for comparing claims against documentation.
# ABOUTME: Uses Claude API to analyze and classify content freshness.

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Optional

import anthropic

from analyzer.input_handler import Claim
from mcp_server.tools.fetch_docs import DocSection
from config import get_analysis_model


class DriftStatus(Enum):
    """Classification status for content drift."""

    CURRENT = "CURRENT"
    POTENTIALLY_STALE = "POTENTIALLY_STALE"
    OUTDATED = "OUTDATED"
    UNVERIFIABLE = "UNVERIFIABLE"


@dataclass
class DriftResult:
    """Result of analyzing a claim for drift."""

    claim_text: str
    section_title: str
    line_number: int
    status: DriftStatus
    reasoning: str
    source_reference: Optional[str]
    suggested_update: Optional[str]


ANALYSIS_PROMPT = """You are a technical documentation analyst. Your task is to compare a claim from training content against current official documentation and determine if the claim is still accurate.

CLAIM TO ANALYZE:
"{claim_text}"

CURRENT DOCUMENTATION:
{docs_content}

Analyze whether the claim is accurate according to the current documentation. Respond with a JSON object (no markdown formatting) containing:
- "status": One of "CURRENT", "POTENTIALLY_STALE", "OUTDATED", or "UNVERIFIABLE"
  - CURRENT: The claim matches current documentation
  - POTENTIALLY_STALE: The claim may be outdated but cannot be definitively determined
  - OUTDATED: The claim directly contradicts current documentation
  - UNVERIFIABLE: Cannot find relevant documentation to verify the claim
- "reasoning": A brief explanation of your classification
- "source_reference": The URL from the documentation that supports your analysis (or null if none)
- "suggested_update": If outdated, suggest the corrected text (or null if current/unverifiable)

Respond ONLY with the JSON object, no other text."""


def _format_docs_for_prompt(docs: List[DocSection]) -> str:
    """Format documentation sections for the analysis prompt."""
    parts = []
    for doc in docs:
        parts.append(f"Source: {doc.source_url}")
        parts.append(f"Title: {doc.title}")
        parts.append(f"Content: {doc.content[:2000]}")  # Limit content length
        parts.append("---")
    return "\n".join(parts)


def _parse_analysis_response(response_text: str) -> dict:
    """Parse the JSON response from Claude."""
    # Clean up response text
    text = response_text.strip()

    # Remove markdown code blocks if present
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first and last lines (```json and ```)
        lines = [l for l in lines if not l.startswith("```")]
        text = "\n".join(lines)

    return json.loads(text)


async def analyze_claim(
    claim: Claim,
    docs: List[DocSection],
    config_path: Optional[Path] = None
) -> DriftResult:
    """
    Analyze a claim against current documentation using Claude.

    Args:
        claim: The claim to analyze.
        docs: Current documentation sections to compare against.
        config_path: Optional path to config file.

    Returns:
        DriftResult with classification and reasoning.

    Raises:
        Exception: If API call fails.
    """
    client = anthropic.AsyncAnthropic()
    model = get_analysis_model(config_path)

    docs_content = _format_docs_for_prompt(docs)

    prompt = ANALYSIS_PROMPT.format(
        claim_text=claim.text,
        docs_content=docs_content
    )

    message = await client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    response_text = message.content[0].text
    analysis = _parse_analysis_response(response_text)

    return DriftResult(
        claim_text=claim.text,
        section_title=claim.section_title,
        line_number=claim.line_number,
        status=DriftStatus(analysis["status"]),
        reasoning=analysis["reasoning"],
        source_reference=analysis.get("source_reference"),
        suggested_update=analysis.get("suggested_update")
    )
