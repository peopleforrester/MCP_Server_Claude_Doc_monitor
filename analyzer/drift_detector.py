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

# json: For parsing Claude's JSON response.
# Claude returns analysis as a JSON object, which we parse into a Python dict.
import json

# dataclass: Decorator for creating data container classes with auto-generated methods.
from dataclasses import dataclass

# Enum: Base class for creating enumerations (fixed sets of named values).
# We use it for DriftStatus to ensure only valid statuses are used.
from enum import Enum

# Path: Object-oriented filesystem paths for the config_path parameter.
from pathlib import Path

# Type hints for function signatures.
# - List[X]: A list containing items of type X
# - Optional[X]: Either X or None
from typing import List, Optional

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
    source_reference: Optional[str]      # Doc URL if found (None if unverifiable)
    suggested_update: Optional[str]      # Corrected text if outdated (None otherwise)


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


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _format_docs_for_prompt(docs: List[DocSection]) -> str:
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
        lines = [l for l in lines if not l.startswith("```")]

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
    docs: List[DocSection],
    config_path: Optional[Path] = None
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
    # Create an async Anthropic client.
    # AsyncAnthropic is the async version of the Anthropic client.
    # It reads the API key from the ANTHROPIC_API_KEY environment variable.
    client = anthropic.AsyncAnthropic()

    # Get the configured model name (e.g., "claude-sonnet-4-20250514")
    model = get_analysis_model(config_path)

    # Format the documentation for inclusion in the prompt
    docs_content = _format_docs_for_prompt(docs)

    # Construct the prompt by substituting placeholders.
    # str.format() replaces {name} with the corresponding keyword argument.
    prompt = ANALYSIS_PROMPT.format(
        claim_text=claim.text,
        docs_content=docs_content
    )

    # Call the Claude API.
    # await: Pause this coroutine until the API responds.
    #        Control returns to the event loop, which can run other tasks.
    # messages.create(): The Messages API endpoint for chat completions.
    message = await client.messages.create(
        model=model,                    # Which Claude model to use
        max_tokens=1024,                # Limit response length (saves cost)
        messages=[
            # The Messages API expects a list of message dicts.
            # Each has a "role" (user/assistant) and "content".
            {"role": "user", "content": prompt}
        ]
    )

    # Extract the response text.
    # message.content is a list of content blocks.
    # [0] gets the first block, .text gets its text content.
    response_text = message.content[0].text

    # Parse the JSON response into a dictionary
    analysis = _parse_analysis_response(response_text)

    # Construct and return the DriftResult.
    # DriftStatus(analysis["status"]) converts the string to an enum value.
    # .get() returns None if the key doesn't exist (for optional fields).
    return DriftResult(
        claim_text=claim.text,
        section_title=claim.section_title,
        line_number=claim.line_number,
        status=DriftStatus(analysis["status"]),
        reasoning=analysis["reasoning"],
        source_reference=analysis.get("source_reference"),  # May be None
        suggested_update=analysis.get("suggested_update")   # May be None
    )
