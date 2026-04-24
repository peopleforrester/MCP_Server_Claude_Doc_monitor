# ABOUTME: Drift detector for comparing claims against documentation.
# ABOUTME: Uses Claude API to analyze and classify content freshness.

"""
Drift Detector Module
=====================

This module is the heart of the content freshness system. It takes claims
extracted from training content and compares them against current official
documentation using Claude as the analysis engine.

Pipeline Stage: Claims → [DRIFT DETECTOR] → DriftResults → Report

The process:
1. Receive a claim (e.g., "Claude has a 100k token context window")
2. Receive current documentation (fetched from Anthropic docs)
3. Format a prompt asking Claude to compare the claim against the docs
4. Parse Claude's JSON response into a structured DriftResult
5. Return the analysis with classification and recommendations

Key Concepts:
- DriftStatus: The classification of whether a claim is current or outdated
- DriftResult: Complete analysis including status, reasoning, and suggested fix
- ANALYSIS_PROMPT: The carefully crafted prompt that instructs Claude

Why use Claude for analysis? Because understanding whether a claim "matches"
documentation often requires nuanced understanding that regex can't provide.
For example, "Claude has a 100k context" needs to be compared against docs
that might say "200,000 tokens" - Claude understands these are different.
"""

# =============================================================================
# IMPORTS
# =============================================================================

from __future__ import annotations

# json: For parsing the JSON response from the analysis API call.
import json
import logging

# dataclass: Decorator for creating data container classes with auto-generated methods.
from dataclasses import dataclass, field

# Enum: Base class for creating enumerations (fixed sets of named values).
# We use it for DriftStatus to ensure only valid statuses are used.
from enum import Enum

# Path: Object-oriented filesystem paths for the config_path parameter.
from pathlib import Path
from typing import Any


# anthropic: The official Anthropic Python SDK for calling the Claude API.
# We use AsyncAnthropic for async/await support (non-blocking API calls).
import anthropic

# Import our custom types from other modules in this project.
# Claim: Represents an extracted claim from the input document.
from analyzer.input_handler import Claim

# DocSection: Represents a section of fetched documentation.
from mcp_server.tools.fetch_docs import DocSection

# get_analysis_model: Function to get the configured Claude model name.
from config import get_analysis_model

# Docs above ~80KB get chunked into multiple document content blocks.
# The Citations API has a per-document practical ceiling; staying well under
# 100KB leaves headroom for the system prompt and claim text.
_DOC_CHUNK_MAX_CHARS = 80_000

# Prompt caching: system prompt + doc corpus are identical across all claims in
# a run, so mark them cacheable. 1h TTL pairs well with batch processing runs.
CACHE_CONTROL_1H = {"type": "ephemeral", "ttl": "1h"}

logger = logging.getLogger(__name__)


def _log_cache_usage(usage: Any) -> None:
    """Emit cache-hit metrics at INFO so verbose runs surface cache behavior."""
    if usage is None:
        return
    created = getattr(usage, "cache_creation_input_tokens", 0) or 0
    read = getattr(usage, "cache_read_input_tokens", 0) or 0
    if created or read:
        logger.info("cache: created=%d read=%d tokens", created, read)


# =============================================================================
# DRIFT STATUS ENUMERATION
# =============================================================================

class DriftStatus(Enum):
    """
    Classification status for content drift.

    This enum defines the four possible outcomes when comparing a claim
    against current documentation. Using an enum instead of strings:
    1. Prevents typos (DriftStatus.CURRANT would be a syntax error)
    2. Enables IDE autocompletion
    3. Makes the valid values explicit and documented

    The status hierarchy from best to worst:
    1. CURRENT - No action needed
    2. POTENTIALLY_STALE - Manual review recommended
    3. OUTDATED - Update required
    4. UNVERIFIABLE - Documentation coverage gap

    Enum values use strings (not integers) to make JSON serialization
    and report output more readable.
    """

    # CURRENT: The claim accurately reflects current documentation.
    # Example: Claim says "Claude supports streaming" and docs confirm this.
    # Action: None needed.
    CURRENT = "CURRENT"

    # POTENTIALLY_STALE: The claim might be outdated but we can't be certain.
    # Example: Claim mentions a feature that docs don't explicitly confirm or deny.
    # Action: Manual review recommended.
    POTENTIALLY_STALE = "POTENTIALLY_STALE"

    # OUTDATED: The claim directly contradicts current documentation.
    # Example: Claim says "100k tokens" but docs say "200k tokens".
    # Action: Update the training content.
    OUTDATED = "OUTDATED"

    # UNVERIFIABLE: Cannot find relevant documentation to verify.
    # Example: Claim about an internal feature not covered in public docs.
    # Action: Consider adding documentation or removing the claim.
    UNVERIFIABLE = "UNVERIFIABLE"


# =============================================================================
# DRIFT RESULT DATA CLASS
# =============================================================================

@dataclass
class CitedEvidence:
    """A citation from the Anthropic Citations API pointing at a source document span.

    The drift analyzer collects these whenever the API returns citations attached
    to its response — they give verified pointers back into the live doc, so the
    final report can show readers exactly which text contradicts a stale claim.
    """

    cited_text: str                      # The exact span of source text cited
    document_title: str                  # Title of the source document
    document_url: str                    # URL of the source document
    char_range: tuple[int, int]          # (start, end) character offsets into the source


@dataclass
class DriftResult:
    """
    Result of analyzing a claim for drift.

    This dataclass contains all the information from analyzing a single claim:
    - The original claim text and location
    - The classification status
    - Claude's reasoning for the classification
    - A reference to the source documentation
    - A suggested correction (if applicable)

    Attributes:
        claim_text: The original text of the claim that was analyzed.
                    Preserved for the report output.

        section_title: The section where this claim appeared.
                       Helps users locate the claim in their document.

        line_number: Approximate line number of the claim.
                     Helps users find and update the specific text.

        status: The drift classification (CURRENT, OUTDATED, etc.).
                Determines what action (if any) is needed.

        reasoning: Claude's explanation of why this classification was chosen.
                   Helps users understand the analysis.

        source_reference: URL to the documentation that informed the analysis.
                          None if the claim couldn't be verified.
                          Allows users to double-check the reasoning.

        suggested_update: If OUTDATED, contains corrected text.
                          None if CURRENT or UNVERIFIABLE.
                          Gives users a ready-to-use replacement.
    """
    claim_text: str                      # The claim we analyzed
    section_title: str                   # Where it came from
    line_number: int                     # Where to find it
    status: DriftStatus                  # The classification result
    reasoning: str                       # Why this classification
    source_reference: str | None      # Doc URL if found (None if unverifiable)
    suggested_update: str | None      # Corrected text if outdated (None otherwise)
    evidence: list[CitedEvidence] = field(default_factory=list)  # Verified citations


# =============================================================================
# ANALYSIS PROMPT TEMPLATE
# =============================================================================

# This is the prompt sent to Claude for each claim analysis.
# It's a multi-line string (triple quotes) with placeholders for:
# - {claim_text}: The claim to analyze
# - {docs_content}: The formatted documentation to compare against
#
# Prompt Engineering Notes:
# 1. Clear role: "You are a technical documentation analyst"
# 2. Explicit task: Compare claim against documentation
# 3. Structured output: JSON with specific fields
# 4. Clear status definitions: Each status is explained
# 5. Format constraint: "Respond ONLY with the JSON object"
#
# This prompt has been carefully tuned to produce consistent, parseable output.

ANALYSIS_SYSTEM_PROMPT = """You are a technical documentation analyst. You receive a claim from training content and one or more source documents attached with citations enabled. Determine whether the claim still matches the current documentation.

Quote directly from the attached documents when forming your reasoning — the citations system will attach verified source pointers to those quotes automatically.

Respond with a single JSON object (no markdown fences) containing:
- "status": "CURRENT", "POTENTIALLY_STALE", "OUTDATED", or "UNVERIFIABLE"
  - CURRENT: The claim matches the documentation
  - POTENTIALLY_STALE: The claim may be outdated but cannot be confirmed
  - OUTDATED: The claim directly contradicts the documentation
  - UNVERIFIABLE: No relevant documentation found
- "reasoning": brief explanation, quoting directly from the source where possible
- "source_reference": URL from the most relevant attached document (or null)
- "suggested_update": corrected text if outdated (or null)"""


def _chunk_content(content: str, max_chars: int = _DOC_CHUNK_MAX_CHARS) -> list[str]:
    """Split document content into chunks under max_chars, preferring paragraph breaks."""
    if len(content) <= max_chars:
        return [content]

    chunks: list[str] = []
    remaining = content
    while len(remaining) > max_chars:
        # Look for the last paragraph break before the ceiling
        cut = remaining.rfind("\n\n", 0, max_chars)
        if cut == -1:
            cut = remaining.rfind("\n", 0, max_chars)
        if cut == -1:
            cut = max_chars
        chunks.append(remaining[:cut])
        remaining = remaining[cut:].lstrip("\n")
    if remaining:
        chunks.append(remaining)
    return chunks


def _build_document_blocks(docs: list[DocSection]) -> list[dict[str, Any]]:
    """Build Messages API document content blocks with citations enabled.

    Large docs are split into multiple blocks so no single block exceeds the
    per-document chunk ceiling. Each chunk preserves the source title and URL
    (in the ``context`` field) so citations can be mapped back to the live doc.

    The final block carries a 1h ephemeral cache_control, so subsequent claims
    in the same run read the whole doc corpus from cache at ~10% of input cost.
    """
    blocks: list[dict[str, Any]] = []
    for doc in docs:
        chunks = _chunk_content(doc.content)
        for i, chunk in enumerate(chunks):
            title = doc.title if len(chunks) == 1 else f"{doc.title} (part {i + 1}/{len(chunks)})"
            blocks.append({
                "type": "document",
                "source": {
                    "type": "text",
                    "media_type": "text/plain",
                    "data": chunk,
                },
                "title": title,
                "context": doc.source_url,
                "citations": {"enabled": True},
            })
    if blocks:
        blocks[-1]["cache_control"] = CACHE_CONTROL_1H
    return blocks


def _build_system_blocks() -> list[dict[str, Any]]:
    """Return the system prompt as a cacheable block list."""
    return [{
        "type": "text",
        "text": ANALYSIS_SYSTEM_PROMPT,
        "cache_control": CACHE_CONTROL_1H,
    }]


def _collect_citations(
    message: Any,
    docs: list[DocSection],
) -> list[CitedEvidence]:
    """Collect CitedEvidence objects from all text blocks in the response.

    Maps ``document_title`` back to the original DocSection URL — document titles
    carry a "(part N/M)" suffix when chunked, so we match by prefix.
    """
    evidence: list[CitedEvidence] = []
    url_by_title: dict[str, str] = {doc.title: doc.source_url for doc in docs}

    for block in getattr(message, "content", []) or []:
        citations = getattr(block, "citations", None) or []
        for citation in citations:
            title = getattr(citation, "document_title", "") or ""
            # Strip any "(part N/M)" suffix to find the original doc URL
            base_title = title.split(" (part ")[0]
            url = url_by_title.get(base_title, "")

            start = getattr(citation, "start_char_index", 0) or 0
            end = getattr(citation, "end_char_index", 0) or 0

            evidence.append(CitedEvidence(
                cited_text=getattr(citation, "cited_text", "") or "",
                document_title=title,
                document_url=url,
                char_range=(start, end),
            ))
    return evidence


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _format_docs_for_prompt(docs: list[DocSection]) -> str:
    """
    Format documentation sections for inclusion in the analysis prompt.

    This function takes the fetched documentation and converts it into a
    text format that can be embedded in the prompt. Each doc section includes:
    - The source URL (so Claude can reference it)
    - The title (for context)
    - The content (limited to prevent token overflow)

    The underscore prefix (_format_docs_for_prompt) indicates this is an
    internal/private function, not meant for external use.

    Args:
        docs: List of DocSection objects containing fetched documentation.
              Each has title, content, and source_url attributes.

    Returns:
        A formatted string ready to insert into the prompt.
        Sections are separated by "---" dividers.

    Example output:
        Source: https://docs.anthropic.com/en/api/messages
        Title: Messages API
        Content: The messages API allows you to...
        ---
        Source: https://docs.anthropic.com/en/docs/about-claude/models
        Title: Claude Models
        Content: Claude 3.5 Sonnet offers...
        ---
    """
    parts = []

    for doc in docs:
        # Add source URL for reference
        parts.append(f"Source: {doc.source_url}")

        # Add the title
        parts.append(f"Title: {doc.title}")

        # Add content, but limit to 2000 characters per doc.
        # This prevents the prompt from becoming too long (and expensive).
        # [:2000] is Python slicing that takes the first 2000 characters.
        parts.append(f"Content: {doc.content[:2000]}")

        # Add a separator between documents
        parts.append("---")

    # Join all parts with newlines into a single string
    return "\n".join(parts)


def _parse_analysis_response(response_text: str) -> dict:
    """
    Parse the JSON response from Claude.

    Claude should respond with a JSON object, but sometimes it adds
    markdown code block formatting (```json ... ```). This function
    handles both cases:
    1. Plain JSON: {"status": "CURRENT", ...}
    2. Markdown-wrapped: ```json\n{"status": "CURRENT", ...}\n```

    Args:
        response_text: The raw text response from Claude.

    Returns:
        A Python dictionary containing the parsed JSON.

    Raises:
        json.JSONDecodeError: If the response isn't valid JSON after cleanup.

    Example:
        >>> response = '```json\\n{"status": "CURRENT"}\\n```'
        >>> _parse_analysis_response(response)
        {'status': 'CURRENT'}
    """
    # Remove leading and trailing whitespace
    text = response_text.strip()

    # Check if the response is wrapped in markdown code blocks.
    # startswith() returns True if the string begins with the given prefix.
    if text.startswith("```"):
        # Split into lines
        lines = text.split("\n")

        # Filter out lines that start with ``` (the code block markers).
        # This removes both the opening ```json and closing ``` lines.
        # List comprehension: [x for x in list if condition]
        lines = [line for line in lines if not line.startswith("```")]

        # Rejoin the remaining lines
        text = "\n".join(lines)

    # Parse the JSON string into a Python dictionary.
    # json.loads() converts a JSON string to a Python object.
    # (Not to be confused with json.load() which reads from a file.)
    return json.loads(text)


# =============================================================================
# MAIN ANALYSIS FUNCTION
# =============================================================================

async def analyze_claim(
    claim: Claim,
    docs: list[DocSection],
    config_path: Path | None = None,
    client: anthropic.AsyncAnthropic | None = None
) -> DriftResult:
    """
    Analyze a claim against current documentation using Claude.

    This is the core function of the drift detection system. It:
    1. Creates an Anthropic API client
    2. Formats the documentation for the prompt
    3. Constructs the analysis prompt with the claim and docs
    4. Calls the Claude API asynchronously
    5. Parses the JSON response
    6. Returns a structured DriftResult

    Why async? API calls can take seconds. Using async/await allows the
    program to process multiple claims concurrently rather than waiting
    for each one sequentially. This is especially important when analyzing
    many claims.

    Args:
        claim: The claim to analyze. Contains text, section, and line number.
        docs: Current documentation sections to compare against.
              Should be fetched using fetch_docs.py.
        config_path: Optional path to config file for model selection.

    Returns:
        DriftResult with classification and reasoning.

    Raises:
        Exception: If the API call fails (network error, auth error, etc.)
                   or if the response can't be parsed as JSON.

    Example:
        >>> claim = Claim(text="Claude has 100k tokens", ...)
        >>> docs = await fetch_current_docs("models")
        >>> result = await analyze_claim(claim, docs)
        >>> print(result.status)
        DriftStatus.OUTDATED
        >>> print(result.suggested_update)
        "Claude has a 200,000 token context window"
    """
    # Use the provided client or create a new one.
    # AsyncAnthropic reads the API key from ANTHROPIC_API_KEY environment variable.
    if client is None:
        client = anthropic.AsyncAnthropic()

    # Get the configured model name (e.g., "claude-sonnet-4-6")
    model = get_analysis_model(config_path)

    # Build the user message: all documents as citations-enabled blocks,
    # then a trailing text block carrying the claim and instructions.
    document_blocks = _build_document_blocks(docs)
    claim_block = {
        "type": "text",
        "text": (
            f'Claim to analyze:\n"{claim.text}"\n\n'
            "Analyze this claim against the attached documents and respond with "
            "the JSON object described in your instructions."
        ),
    }

    # The SDK's message param types are tightly typed TypedDicts; our builder
    # returns dicts with the same runtime shape, so we pass as Any.
    user_content: Any = [*document_blocks, claim_block]
    system_blocks: Any = _build_system_blocks()

    message = await client.messages.create(
        model=model,
        max_tokens=1024,
        system=system_blocks,
        messages=[{"role": "user", "content": user_content}],
    )

    # Collect response text across all text blocks (Citations API may emit
    # multiple blocks when citations are attached).
    response_text = ""
    for block in message.content:
        text = getattr(block, "text", None)
        if text:
            response_text += text

    if not response_text:
        raise ValueError("Empty response from Claude API")

    # Parse the JSON response into a dictionary
    analysis = _parse_analysis_response(response_text)

    # Collect citations from the response — verified pointers into source docs.
    evidence = _collect_citations(message, docs)
    _log_cache_usage(getattr(message, "usage", None))

    return DriftResult(
        claim_text=claim.text,
        section_title=claim.section_title,
        line_number=claim.line_number,
        status=DriftStatus(analysis["status"]),
        reasoning=analysis["reasoning"],
        source_reference=analysis.get("source_reference"),
        suggested_update=analysis.get("suggested_update"),
        evidence=evidence,
    )
