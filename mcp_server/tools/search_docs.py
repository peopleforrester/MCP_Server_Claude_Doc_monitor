# ABOUTME: Tool for searching across Claude documentation.
# ABOUTME: Performs keyword-based search across fetched documentation.

"""
Documentation Search Module
===========================

This module provides keyword search functionality across all configured
documentation sources. It's useful for finding specific information
when you don't know which documentation page contains it.

Use Case: "Where is the rate limit documented?" - search for "rate limit"
and get back snippets from relevant pages with URLs.

Process:
1. Receive a search query (e.g., "context window")
2. Fetch all configured documentation pages
3. Check each page for query matches
4. Extract relevant snippets around matches
5. Calculate relevance scores
6. Return sorted results

Key Components:
- SearchResult: Data class for one search result
- _extract_snippet: Helper to get text around a match
- _calculate_relevance: Helper to score result relevance
- search_docs: Main async function to perform the search

This is a simple implementation using case-insensitive substring matching.
More sophisticated implementations could use:
- Word boundary matching
- Fuzzy matching (Levenshtein distance)
- TF-IDF ranking
- Semantic search with embeddings

But for documentation search, simple substring matching works well enough.
"""

# =============================================================================
# IMPORTS
# =============================================================================

# re: Regular expression module.
# (Imported for potential future use - not currently used in this file,
# but included for consistency with other modules.)
import re

# dataclass: Decorator for creating data container classes.
from dataclasses import dataclass

# List: Type hint for lists.
from typing import List

# httpx: Modern async HTTP client for Python.
import httpx

# Import shared utilities from our fetch_docs module.
# DOC_SOURCES: Dictionary of topic names to documentation URLs
# SimpleHTMLTextExtractor: HTML parser for extracting text content
from mcp_server.tools.fetch_docs import DOC_SOURCES, SimpleHTMLTextExtractor


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class SearchResult:
    """
    Represents a search result from documentation.

    Each result contains a snippet of text around the match,
    the source URL, and a relevance score for ranking.

    Attributes:
        snippet: A text snippet containing the search query.
                 Includes some context before and after the match.
                 Truncated with ellipsis (...) if needed.
                 Example: "...The context window is 200k tokens, which allows..."

        source_url: The URL of the documentation page containing this match.
                    Can be used to link users to the full page.
                    Example: "https://docs.anthropic.com/en/docs/about-claude/models"

        relevance_score: A score from 0.0 to 1.0 indicating match quality.
                         Higher is better.
                         Based on frequency and position of matches.
    """
    snippet: str            # Text excerpt with match
    source_url: str         # Where the match was found
    relevance_score: float  # 0.0 to 1.0, higher is better


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _extract_snippet(text: str, query: str, context_chars: int = 150) -> str:
    """
    Extract a snippet around the query match.

    When we find a match, we don't want to return the entire document.
    Instead, we extract a window of text centered on the match,
    giving the user enough context to understand the result.

    Args:
        text: The full text content to extract from.
        query: The search query to find.
        context_chars: Number of characters to include before and after
                       the match. Default: 150 (about 20-30 words).

    Returns:
        A snippet string with the query in context.
        Prefixed with "..." if truncated at the start.
        Suffixed with "..." if truncated at the end.
        Empty string if the query isn't found.

    Example:
        >>> text = "The Claude API supports streaming responses..."
        >>> _extract_snippet(text, "streaming", context_chars=20)
        "...supports streaming responses..."
    """
    # Convert both to lowercase for case-insensitive matching.
    # We search in lowercase but return original text (preserving case).
    query_lower = query.lower()
    text_lower = text.lower()

    # Find the first occurrence of the query.
    # str.find() returns the index of the first match, or -1 if not found.
    pos = text_lower.find(query_lower)

    # If not found, return empty string
    if pos == -1:
        return ""

    # Calculate the window boundaries.
    # We want context_chars before the match...
    # max(0, ...) ensures we don't go negative (before the string start).
    start = max(0, pos - context_chars)

    # ...and context_chars after the match.
    # min(len(text), ...) ensures we don't go past the string end.
    end = min(len(text), pos + len(query) + context_chars)

    # Extract the snippet from the original text (preserving case).
    # strip() removes leading/trailing whitespace.
    snippet = text[start:end].strip()

    # Add ellipsis if we truncated at the start.
    # This tells the user there's more text before this snippet.
    if start > 0:
        snippet = "..." + snippet

    # Add ellipsis if we truncated at the end.
    if end < len(text):
        snippet = snippet + "..."

    return snippet


def _calculate_relevance(text: str, query: str) -> float:
    """
    Calculate a simple relevance score based on query frequency.

    The relevance score helps rank search results so the most relevant
    appear first. This implementation uses a simple heuristic:
    - More occurrences of the query = higher score
    - Earlier first occurrence = higher score

    This is a simplistic approach. More sophisticated ranking could consider:
    - Exact phrase matches vs partial matches
    - Query terms appearing close together
    - Matches in headings vs body text
    - Term rarity (TF-IDF)

    Args:
        text: The full text content to analyze.
        query: The search query.

    Returns:
        A relevance score from 0.0 to 1.0.
        0.0 = query not found
        1.0 = maximum relevance (many occurrences, appears early)

    Example:
        >>> _calculate_relevance("Claude is great. Claude can help.", "Claude")
        0.6  # High score due to 2 occurrences
    """
    # Convert to lowercase for case-insensitive counting
    query_lower = query.lower()
    text_lower = text.lower()

    # Count how many times the query appears in the text.
    # str.count() returns the number of non-overlapping occurrences.
    count = text_lower.count(query_lower)

    # No matches = zero relevance
    if count == 0:
        return 0.0

    # =================================================================
    # SCORING FORMULA
    # =================================================================
    # We combine two factors:
    # 1. Frequency score: How often does the query appear?
    # 2. Position score: How early does the first match appear?
    #
    # Each contributes up to 0.5 to the final score (max total = 1.0).

    # Frequency score: More occurrences = higher score.
    # count / 10.0 means 10+ occurrences maxes out the frequency score.
    # min() caps the score at 0.5.
    frequency_score = min(count / 10.0, 0.5)  # Max 0.5 from frequency

    # Position score: Earlier first match = higher score.
    # Find position of first match.
    first_pos = text_lower.find(query_lower)

    # Calculate position factor: 0.0 if at the end, 1.0 if at the start.
    # first_pos / len(text) gives position as fraction of document.
    # 1.0 - that value inverts it (early = high score).
    # max(len(text), 1) prevents division by zero.
    position_factor = 1.0 - (first_pos / max(len(text), 1))

    # Scale position factor to max 0.5
    position_score = position_factor * 0.5    # Max 0.5 from position

    # Combine scores, capped at 1.0
    return min(frequency_score + position_score, 1.0)


# =============================================================================
# MAIN SEARCH FUNCTION
# =============================================================================

async def search_docs(query: str) -> List[SearchResult]:
    """
    Search across Claude documentation for matching content.

    This function searches all configured documentation sources for
    pages containing the given query. Results are sorted by relevance.

    The search is:
    - Case-insensitive (matches "Token", "token", "TOKEN", etc.)
    - Substring-based (matches partial words like "stream" in "streaming")
    - Concurrent within httpx's connection pool

    Note: This fetches all documentation pages on every search.
    For production use, you might want to:
    - Cache fetched pages
    - Use a search index (Elasticsearch, SQLite FTS, etc.)
    - Limit concurrent connections

    Args:
        query: The search query string.
               Case-insensitive.
               Example: "rate limit", "context window", "vision"

    Returns:
        List of SearchResult objects sorted by relevance (highest first).
        Empty list if no matches found.

    Example:
        >>> results = await search_docs("context window")
        >>> for r in results[:3]:
        ...     print(f"{r.relevance_score:.2f}: {r.source_url}")
        0.85: https://docs.anthropic.com/en/docs/build-with-claude/context-windows
        0.62: https://docs.anthropic.com/en/docs/about-claude/models
        0.45: https://docs.anthropic.com/en/api/messages
    """
    # Collect results as we search
    results: List[SearchResult] = []

    # Create async HTTP client.
    # Using a shorter timeout (30s) since we're making many requests.
    async with httpx.AsyncClient(
        timeout=30.0,                # 30 second timeout per request
        follow_redirects=True,       # Follow HTTP redirects
        headers={"User-Agent": "ContentFreshnessSystem/1.0"}
    ) as client:

        # Search each documentation source.
        # DOC_SOURCES is a dict mapping topic names to URLs.
        # .items() gives us (key, value) pairs.
        for topic, url in DOC_SOURCES.items():
            try:
                # Fetch the documentation page.
                # await allows other requests to proceed while waiting.
                response = await client.get(url)

                # Raise exception for HTTP errors
                response.raise_for_status()

                # Parse the HTML to extract text content
                parser = SimpleHTMLTextExtractor()
                parser.feed(response.text)
                content = parser.get_text()

                # Check if the query matches (case-insensitive).
                # We use 'in' for substring matching with lowercased strings.
                if query.lower() in content.lower():
                    # Found a match! Extract snippet and calculate relevance.
                    snippet = _extract_snippet(content, query)
                    relevance = _calculate_relevance(content, query)

                    # Only add if we got a valid snippet
                    # (edge case: query at very edge might produce empty snippet)
                    if snippet:
                        results.append(SearchResult(
                            snippet=snippet,
                            source_url=url,
                            relevance_score=relevance
                        ))

            except httpx.HTTPError:
                # Skip URLs that fail to load (network error, 404, etc.).
                # We continue searching other URLs rather than failing entirely.
                # This makes the search more resilient.
                continue

    # Sort results by relevance score in descending order (highest first).
    # list.sort() modifies the list in-place.
    # key=lambda r: r.relevance_score tells it what to sort by.
    # reverse=True gives descending order (high to low).
    results.sort(key=lambda r: r.relevance_score, reverse=True)

    return results
