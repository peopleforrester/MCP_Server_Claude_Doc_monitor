# ABOUTME: Claude-based claim extractor replacing regex patterns for higher recall.
# ABOUTME: Results are cached by content SHA256 so re-runs on unchanged files are free.

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

import anthropic

from analyzer.input_handler import Claim, Section
from config import get_analysis_model

logger = logging.getLogger(__name__)

CACHE_SCHEMA_VERSION = 1

ClaimCategory = Literal["capability", "parameter", "limit", "pricing", "availability"]
SeverityHint = Literal["low", "medium", "high"]

EXTRACTION_SYSTEM_PROMPT = """You extract verifiable factual claims from training documentation about Claude.

A claim is a statement about Claude's capabilities, API parameters, numeric limits, pricing, or model availability — anything that could become stale as Anthropic updates Claude.

Extract every distinct claim. Paraphrases of the same underlying fact count once.

For each claim:
- text: the claim as a complete sentence, quoted verbatim where possible
- section_title: the section header it appears under
- line_number: the source line (use the section start_line for best approximation)
- category: one of "capability", "parameter", "limit", "pricing", "availability"
- severity_hint: "high" for claims about numeric limits, deprecated features, or pricing; "medium" for capabilities and parameters; "low" for general descriptive statements

Respond with a single JSON object of the form:
{"claims": [ {"text": "...", "section_title": "...", "line_number": N, "category": "...", "severity_hint": "..."}, ... ]}

No markdown fences, no commentary — only the JSON object."""


@dataclass
class ExtractedClaim(Claim):
    """Claim with LLM-extracted metadata. Inherits text/section_title/line_number from Claim."""

    category: ClaimCategory = "capability"
    severity_hint: SeverityHint = "medium"


def _cache_dir() -> Path:
    return Path.home() / ".cache" / "freshness-check" / "extractions"


def _content_hash(sections: list[Section]) -> str:
    joined = "\n---SECTION---\n".join(
        f"{s.level}|{s.start_line}|{s.title}\n{s.content}" for s in sections
    )
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def _cache_path_for_content(content: str) -> Path:
    sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return _cache_dir() / f"{sha}.json"


def _cache_path_for_sections(sections: list[Section]) -> Path:
    return _cache_dir() / f"{_content_hash(sections)}.json"


def _save_cached_extraction(path: Path, claims: list[ExtractedClaim], model: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": CACHE_SCHEMA_VERSION,
        "model": model,
        "claims": [asdict(c) for c in claims],
    }
    path.write_text(json.dumps(payload, indent=2))


def _load_cached_extraction(path: Path) -> list[ExtractedClaim] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Cache read failed at %s: %s", path, exc)
        return None
    if payload.get("version") != CACHE_SCHEMA_VERSION:
        return None
    return [ExtractedClaim(**item) for item in payload.get("claims", [])]


def _build_extraction_user_message(sections: list[Section]) -> str:
    blocks = []
    for s in sections:
        blocks.append(
            f"## Section: {s.title} (start_line={s.start_line}, level={s.level})\n{s.content}"
        )
    return "Extract all claims from the following training content:\n\n" + "\n\n".join(blocks)


def _parse_extraction_response(text: str) -> list[ExtractedClaim]:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines)

    data: dict[str, Any] = json.loads(stripped)
    raw_claims = data.get("claims", [])
    return [
        ExtractedClaim(
            text=item["text"],
            section_title=item["section_title"],
            line_number=int(item["line_number"]),
            category=item.get("category", "capability"),
            severity_hint=item.get("severity_hint", "medium"),
        )
        for item in raw_claims
    ]


async def extract_claims_with_llm(
    sections: list[Section],
    client: anthropic.AsyncAnthropic | None = None,
    config_path: Path | None = None,
) -> list[ExtractedClaim]:
    """Extract claims from parsed markdown sections using Claude.

    Caches results by content SHA256 so unchanged input is free on re-run.
    Returns an empty list for empty input without calling the API.
    """
    if not sections:
        return []

    cache_path = _cache_path_for_sections(sections)
    cached = _load_cached_extraction(cache_path)
    if cached is not None:
        logger.info("Using cached extraction from %s", cache_path)
        return cached

    if client is None:
        client = anthropic.AsyncAnthropic()

    model = get_analysis_model(config_path)
    user_message = _build_extraction_user_message(sections)

    response = await client.messages.create(
        model=model,
        max_tokens=4096,
        system=EXTRACTION_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    text_content = ""
    for block in response.content:
        text = getattr(block, "text", None)
        if text:
            text_content += text

    claims = _parse_extraction_response(text_content)
    _save_cached_extraction(cache_path, claims, model=model)
    return claims
