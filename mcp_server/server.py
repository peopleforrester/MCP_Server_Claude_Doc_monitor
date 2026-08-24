# ABOUTME: FastMCP server exposing drift detection, doc search, and changelog lookup as MCP tools.
# ABOUTME: Runs over stdio by default so Claude Code / Desktop can invoke the tools locally.

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from dotenv import load_dotenv as _load_dotenv
from mcp.server.fastmcp import FastMCP

from analyzer.batch_runner import analyze_claims_batch
from analyzer.claim_extractor import extract_claims_with_llm
from analyzer.drift_detector import DriftResult
from analyzer.input_handler import Claim, parse_sections
from config import get_doc_sources
from mcp_server.tools.fetch_docs import DocSection, fetch_current_docs
from mcp_server.tools.get_changelog import ChangelogEntry, get_recent_changes
from mcp_server.tools.search_docs import search_docs as search_docs_fn

# Load credentials from the nearest .env file so the project .env wins over
# any ambient export from ~/.keys or ~/.bashrc (override=True is load-bearing).
for _d in [Path.cwd(), *Path.cwd().parents]:
    _env_path = _d / ".env"
    if _env_path.exists():
        _load_dotenv(_env_path, override=True)
        break

logger = logging.getLogger(__name__)

mcp = FastMCP("DocMonitor")


async def _fetch_all_docs() -> list[DocSection]:
    """Fetch every configured doc source. Broken out so tests can patch it."""
    import asyncio

    topics = list(get_doc_sources().keys())

    async def _one(topic: str) -> list[DocSection]:
        try:
            return await fetch_current_docs(topic)
        except Exception as exc:
            logger.warning("Failed to fetch topic %s: %s", topic, exc)
            return []

    results = await asyncio.gather(*(_one(t) for t in topics))
    flat: list[DocSection] = []
    for docs in results:
        flat.extend(docs)
    return flat


def _serialize_drift_result(result: DriftResult) -> dict[str, Any]:
    return {
        "claim_text": result.claim_text,
        "section_title": result.section_title,
        "line_number": result.line_number,
        "status": result.status.value,
        "reasoning": result.reasoning,
        "source_reference": result.source_reference,
        "suggested_update": result.suggested_update,
        "evidence": [
            {
                "cited_text": e.cited_text,
                "document_title": e.document_title,
                "document_url": e.document_url,
                "char_range": list(e.char_range),
            }
            for e in result.evidence
        ],
    }


async def check_drift_impl(markdown: str) -> dict[str, Any]:
    """Analyze a training document for claims that have drifted from live docs."""
    sections = parse_sections(markdown)
    extracted = await extract_claims_with_llm(sections)
    # Widen to list[Claim] — ExtractedClaim inherits from Claim but list is invariant.
    claims: list[Claim] = list(extracted)
    if not claims:
        return {"summary": {"total": 0}, "claims": []}

    docs = await _fetch_all_docs()
    results = await analyze_claims_batch(claims, docs)

    by_status: dict[str, int] = {}
    for r in results:
        by_status[r.status.value] = by_status.get(r.status.value, 0) + 1

    return {
        "summary": {"total": len(results), "by_status": by_status},
        "claims": [_serialize_drift_result(r) for r in results],
    }


@mcp.tool()
async def check_drift(markdown: str) -> dict[str, Any]:
    """Analyze training-content markdown for drift against current Claude documentation.

    Extracts capability claims, fetches the configured doc sources, and classifies
    each claim as CURRENT, POTENTIALLY_STALE, OUTDATED, or UNVERIFIABLE with cited
    evidence from the live docs.
    """
    return await check_drift_impl(markdown)


@mcp.tool()
async def search_docs(query: str) -> list[dict[str, Any]]:
    """Keyword-search configured Claude documentation for the given query.

    Returns a ranked list of snippets with source URLs. Use this to verify
    specific facts or discover where a topic is documented.
    """
    results = await search_docs_fn(query)
    return [
        {
            "source_url": r.source_url,
            "snippet": r.snippet,
            "relevance_score": r.relevance_score,
        }
        for r in results
    ]


@mcp.tool()
async def get_changelog(days: int = 30) -> list[dict[str, Any]]:
    """Return changelog entries from the last ``days`` days (default 30).

    Use this to identify what has changed recently in Claude's capabilities so
    training materials can be checked for newly-deprecated or updated features.
    """
    entries: list[ChangelogEntry] = await get_recent_changes(days=days)
    return [
        {
            "date": e.date,
            "title": e.title,
            "description": e.description,
            "source_url": e.source_url,
        }
        for e in entries
    ]


@mcp.resource("docs://{topic}")
async def get_doc_resource(topic: str) -> str:
    """Return the current content for a documentation topic (e.g. ``docs://models``)."""
    sections = await fetch_current_docs(topic)
    if not sections:
        return f"(no content fetched for topic '{topic}')"
    parts: list[str] = []
    for s in sections:
        parts.append(f"# {s.title}\nSource: {s.source_url}\n\n{s.content}")
    return "\n\n---\n\n".join(parts)


def main() -> None:
    """Entry point for the MCP server. Runs over stdio for local clients."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
