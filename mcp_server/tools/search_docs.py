# ABOUTME: Tool for searching across Claude documentation.
# ABOUTME: Performs keyword-based search across fetched documentation.

import re
from dataclasses import dataclass
from typing import List

import httpx

from mcp_server.tools.fetch_docs import DOC_SOURCES, SimpleHTMLTextExtractor


@dataclass
class SearchResult:
    """Represents a search result from documentation."""

    snippet: str
    source_url: str
    relevance_score: float


def _extract_snippet(text: str, query: str, context_chars: int = 150) -> str:
    """Extract a snippet around the query match."""
    query_lower = query.lower()
    text_lower = text.lower()

    pos = text_lower.find(query_lower)
    if pos == -1:
        return ""

    start = max(0, pos - context_chars)
    end = min(len(text), pos + len(query) + context_chars)

    snippet = text[start:end].strip()

    # Add ellipsis if truncated
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."

    return snippet


def _calculate_relevance(text: str, query: str) -> float:
    """Calculate a simple relevance score based on query frequency."""
    query_lower = query.lower()
    text_lower = text.lower()

    # Count occurrences
    count = text_lower.count(query_lower)
    if count == 0:
        return 0.0

    # Simple scoring: more occurrences = higher score, capped at 1.0
    # Also consider position (earlier = better)
    first_pos = text_lower.find(query_lower)
    position_factor = 1.0 - (first_pos / max(len(text), 1))

    frequency_score = min(count / 10.0, 0.5)  # Max 0.5 from frequency
    position_score = position_factor * 0.5    # Max 0.5 from position

    return min(frequency_score + position_score, 1.0)


async def search_docs(query: str) -> List[SearchResult]:
    """
    Search across Claude documentation for matching content.

    Args:
        query: The search query string.

    Returns:
        List of SearchResult objects sorted by relevance.
    """
    results: List[SearchResult] = []

    async with httpx.AsyncClient(
        timeout=30.0,
        follow_redirects=True,
        headers={"User-Agent": "ContentFreshnessSystem/1.0"}
    ) as client:
        for topic, url in DOC_SOURCES.items():
            try:
                response = await client.get(url)
                response.raise_for_status()

                parser = SimpleHTMLTextExtractor()
                parser.feed(response.text)
                content = parser.get_text()

                # Check if query matches
                if query.lower() in content.lower():
                    snippet = _extract_snippet(content, query)
                    relevance = _calculate_relevance(content, query)

                    if snippet:
                        results.append(SearchResult(
                            snippet=snippet,
                            source_url=url,
                            relevance_score=relevance
                        ))
            except httpx.HTTPError:
                # Skip URLs that fail to load
                continue

    # Sort by relevance score descending
    results.sort(key=lambda r: r.relevance_score, reverse=True)

    return results
