# ABOUTME: Cross-references training claims against recent changelog entries.
# ABOUTME: Catches drift from newly-deprecated features that per-doc analysis can miss.

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import anthropic

from analyzer.drift_detector import _parse_analysis_response
from analyzer.input_handler import Claim
from config import get_analysis_model
from mcp_server.tools.get_changelog import ChangelogEntry

logger = logging.getLogger(__name__)

ImpactSeverity = Literal["HIGH", "MEDIUM", "LOW"]

CHANGELOG_SYSTEM_PROMPT = """You identify training-content claims whose accuracy is affected by recent Claude changelog entries.

You receive:
1. A numbered list of claims from training material.
2. A numbered list of recent changelog entries (deprecations, new features, pricing changes).

For each claim whose accuracy is affected by any changelog entry, emit an impact entry.

Respond with a single JSON object (no markdown fences):
{"impacts": [
  {
    "claim_index": N,
    "entry_index": M,
    "severity": "HIGH" | "MEDIUM" | "LOW",
    "explanation": "brief, specific reason"
  }
]}

Severity rubric:
- HIGH: the claim is directly contradicted by the changelog (e.g., feature retired, deprecated model)
- MEDIUM: the claim may need updating to reflect new capabilities or pricing
- LOW: the claim is tangentially related but not necessarily wrong

If no claims are affected, return {"impacts": []}."""


@dataclass
class ChangelogImpact:
    claim_index: int
    entry_index: int
    severity: ImpactSeverity
    explanation: str
    claim_text: str
    entry_title: str
    entry_date: str
    entry_url: str


def _format_inputs(claims: list[Claim], entries: list[ChangelogEntry]) -> str:
    claim_lines = [f"[{i}] {c.text}" for i, c in enumerate(claims)]
    entry_lines = [
        f"[{i}] {e.date} — {e.title}\n    {e.description}"
        for i, e in enumerate(entries)
    ]
    return (
        "CLAIMS:\n" + "\n".join(claim_lines)
        + "\n\nCHANGELOG ENTRIES:\n" + "\n".join(entry_lines)
    )


async def analyze_changelog_impact(
    claims: list[Claim],
    entries: list[ChangelogEntry],
    client: anthropic.AsyncAnthropic | None = None,
    config_path: Path | None = None,
) -> list[ChangelogImpact]:
    """Cross-reference claims against recent changelog entries.

    Single Claude call — cheap vs. one call per claim — so we can run this on
    every drift analysis without meaningful overhead.
    """
    if not claims or not entries:
        return []

    if client is None:
        client = anthropic.AsyncAnthropic()

    model = get_analysis_model(config_path)
    user_content = _format_inputs(claims, entries)

    response = await client.messages.create(
        model=model,
        max_tokens=2048,
        system=CHANGELOG_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )

    text = ""
    for block in response.content:
        t = getattr(block, "text", None)
        if t:
            text += t

    if not text:
        return []

    try:
        data: dict[str, Any] = _parse_analysis_response(text)
    except json.JSONDecodeError as exc:
        logger.warning("Changelog response not valid JSON: %s", exc)
        return []

    impacts: list[ChangelogImpact] = []
    for raw in data.get("impacts", []):
        try:
            ci = int(raw["claim_index"])
            ei = int(raw["entry_index"])
        except (KeyError, ValueError, TypeError):
            continue
        if ci < 0 or ci >= len(claims):
            continue
        if ei < 0 or ei >= len(entries):
            continue
        severity = raw.get("severity", "LOW")
        if severity not in ("HIGH", "MEDIUM", "LOW"):
            severity = "LOW"

        impacts.append(ChangelogImpact(
            claim_index=ci,
            entry_index=ei,
            severity=severity,
            explanation=raw.get("explanation", ""),
            claim_text=claims[ci].text,
            entry_title=entries[ei].title,
            entry_date=entries[ei].date,
            entry_url=entries[ei].source_url,
        ))
    return impacts
