# ABOUTME: Input handler for parsing training documents and extracting claims.
# ABOUTME: Parses markdown into sections and identifies capability statements.

"""
Input Handler Module
====================

This module is responsible for the first stage of the drift detection pipeline:
reading and parsing training documents to extract "claims" that can be verified.

Pipeline Stage: Input → [INPUT HANDLER] → Claims → Analyzer → Report

A "claim" is any statement in the training content that could become outdated:
- "Claude can process images up to 5MB"
- "The context window is 100k tokens"
- "Use the 'max_tokens' parameter to limit output"

The module provides three main functions:
1. load_markdown_file: Read a markdown file from disk
2. parse_sections: Split markdown content into logical sections by headers
3. extract_claims: Find capability statements using regex pattern matching

Key Concepts:
- Section: A header plus all content until the next header of same/higher level
- Claim: A specific statement that makes a factual claim about Claude
- Line number tracking: We track where each claim appears for the final report
"""

# =============================================================================
# IMPORTS
# =============================================================================

from __future__ import annotations

# re: Regular expression module for pattern matching.
# We use regex extensively to:
# 1. Find markdown headers (# Header)
# 2. Split text into sentences
# 3. Identify claim patterns (e.g., "Claude can...")
import re

# dataclass: Decorator for creating data container classes.
# Automatically generates __init__, __repr__, __eq__, etc.
# Cleaner than manually writing these methods.
from dataclasses import dataclass

# Path: Object-oriented filesystem paths.
# Better than string manipulation for cross-platform compatibility.
from pathlib import Path



# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class Section:
    """
    Represents a section of a markdown document.

    A section is defined as a header line plus all the content that follows it,
    up until the next header of the same or higher level.

    Example markdown:
        # Introduction        <- Section 1 starts (level 1)
        Some intro text.

        ## Details           <- Section 2 starts (level 2)
        More details here.

        # Next Topic         <- Section 3 starts (level 1)

    Attributes:
        title: The header text without the # symbols.
               Example: "Introduction" (not "# Introduction")

        content: All text between this header and the next header.
                 May span multiple lines and paragraphs.

        level: The heading level (1-6), determined by number of # symbols.
               # = level 1, ## = level 2, etc.

        start_line: Line number where this section begins (1-indexed).
                    Used to tell users where to find outdated claims.
    """
    title: str       # Header text (e.g., "API Overview")
    content: str     # Body text under the header
    level: int       # Heading depth: 1 for #, 2 for ##, etc.
    start_line: int  # Line number in the original file


@dataclass
class Claim:
    """
    Represents a capability claim extracted from a document.

    A claim is a specific statement that asserts something about Claude's
    capabilities, limitations, API behavior, or parameters. These are the
    statements we need to verify against current documentation.

    Examples of claims:
    - "Claude can process images and PDFs"
    - "The maximum output is 4096 tokens"
    - "Use the temperature parameter to control randomness"

    Attributes:
        text: The full text of the claim (usually one sentence).

        section_title: Which section this claim came from.
                       Helps users locate the claim in their document.

        line_number: Approximate line number where the claim appears.
                     Note: This is approximate because we track by sentence,
                     not by exact character position.
    """
    text: str            # The claim text itself
    section_title: str   # Parent section for context
    line_number: int     # Where to find it in the source file


# =============================================================================
# FILE LOADING
# =============================================================================

def load_markdown_file(file_path: Path) -> str:
    """
    Load content from a markdown file.

    This is a simple wrapper around file reading that:
    1. Checks if the file exists before trying to read it
    2. Provides a clear error message if it doesn't

    We use Path.read_text() instead of open() because it's:
    - More concise (one method call vs context manager)
    - Automatically handles encoding (defaults to UTF-8)
    - Automatically closes the file

    Args:
        file_path: Path to the markdown file.
                   Should be an absolute or relative Path object.

    Returns:
        The file contents as a string, preserving all whitespace and newlines.

    Raises:
        FileNotFoundError: If the file does not exist.
                          Includes the path in the error message for debugging.

    Example:
        >>> content = load_markdown_file(Path("training.md"))
        >>> print(content[:50])
        '# Claude Training Guide\\n\\nThis document covers...'
    """
    # Check existence first to provide a better error message.
    # Without this, read_text() would raise a generic FileNotFoundError.
    if not file_path.exists():
        # Include the path in the error for easier debugging
        raise FileNotFoundError(f"File not found: {file_path}")

    # read_text() opens, reads, and closes the file in one call.
    # Returns the entire file content as a single string.
    return file_path.read_text()


# =============================================================================
# MARKDOWN PARSING
# =============================================================================

def parse_sections(content: str) -> list[Section]:
    """
    Parse markdown content into sections based on headers.

    This function implements a state machine that:
    1. Scans through the document line by line
    2. Detects markdown headers (lines starting with #)
    3. Groups content under each header into sections

    State Machine States:
    - Collecting intro content (before any header)
    - Collecting section content (after a header, until next header)

    Special Cases:
    - Content before the first header becomes an "(Introduction)" section
    - Empty documents return an empty list
    - Documents with only headers (no content) work correctly

    Args:
        content: The markdown content to parse.
                 Should be the raw string from a .md file.

    Returns:
        List of Section objects representing each section.
        Order matches the document order (top to bottom).

    Example:
        >>> content = '''# Overview
        ... Some overview text.
        ...
        ... ## Details
        ... Detail information here.
        ... '''
        >>> sections = parse_sections(content)
        >>> len(sections)
        2
        >>> sections[0].title
        'Overview'
    """
    # Handle edge case: empty or whitespace-only content
    # strip() removes leading/trailing whitespace
    if not content.strip():
        return []

    # Initialize the result list
    sections: list[Section] = []

    # Split content into lines for line-by-line processing.
    # We process line by line because:
    # 1. Headers are defined by what's at the start of a line
    # 2. We need to track line numbers accurately
    lines = content.split("\n")

    # Compile the header regex pattern.
    # Pattern breakdown:
    #   ^         - Start of line (in multiline mode, start of each line)
    #   (#{1,6})  - Capture group 1: 1 to 6 # characters (header levels)
    #   \s+       - One or more whitespace characters (space after #)
    #   (.+)      - Capture group 2: The header text (one or more characters)
    #   $         - End of line
    header_pattern = re.compile(r"^(#{1,6})\s+(.+)$")

    # State variables for tracking the current section being built
    current_section_title = None     # None until we hit the first header
    current_section_level = 0        # Heading level (1-6)
    current_section_start = 1        # Line number where section starts
    current_content_lines: list[str] = []  # Lines of content for current section

    # Process each line with its line number.
    # enumerate() gives us (index, value) pairs.
    # start=1 makes line numbers 1-indexed (like text editors) instead of 0-indexed.
    for line_num, line in enumerate(lines, start=1):
        # Try to match this line against the header pattern
        match = header_pattern.match(line)

        if match:
            # This line IS a header - we're starting a new section

            # First, save the previous section (if any)
            if current_section_title is not None:
                # We have a previous section to save
                sections.append(Section(
                    title=current_section_title,
                    # Join collected lines with newlines, then strip whitespace
                    content="\n".join(current_content_lines).strip(),
                    level=current_section_level,
                    start_line=current_section_start
                ))
            elif current_content_lines and any(line.strip() for line in current_content_lines):
                # No header yet, but we have content.
                # This is content before the first header - treat as introduction.
                # any(l.strip() for l in ...) checks if any line has non-whitespace.
                sections.append(Section(
                    title="(Introduction)",
                    content="\n".join(current_content_lines).strip(),
                    level=0,  # Level 0 indicates no header
                    start_line=1
                ))

            # Start tracking the new section
            # match.group(1) is the # symbols, match.group(2) is the title text
            current_section_level = len(match.group(1))  # Count # symbols
            current_section_title = match.group(2).strip()
            current_section_start = line_num
            current_content_lines = []  # Reset content collection

        else:
            # This line is NOT a header - it's content
            # Add it to our collection for the current section
            current_content_lines.append(line)

    # Don't forget the last section!
    # The loop ends without a chance to save the final section,
    # so we need to handle it here.
    if current_section_title is not None:
        sections.append(Section(
            title=current_section_title,
            content="\n".join(current_content_lines).strip(),
            level=current_section_level,
            start_line=current_section_start
        ))
    elif current_content_lines and any(line.strip() for line in current_content_lines):
        # Edge case: Document has content but no headers at all
        sections.append(Section(
            title="(Introduction)",
            content="\n".join(current_content_lines).strip(),
            level=0,
            start_line=1
        ))

    return sections


# =============================================================================
# CLAIM EXTRACTION
# =============================================================================

def extract_claims(sections: list[Section]) -> list[Claim]:
    """
    Extract capability claims from document sections.

    This is the core of the input processing: identifying statements that
    make factual claims about Claude which could become outdated.

    Strategy:
    1. Split each section's content into sentences
    2. Test each sentence against a set of regex patterns
    3. If a pattern matches, the sentence is a "claim"

    The patterns are designed to catch:
    - Capability statements: "Claude can/supports/has..."
    - API parameter mentions: "Use the X parameter..."
    - Numeric limits: "Maximum of 100k tokens..."
    - Feature descriptions: "Vision capabilities include..."

    Why regex? It's fast and catches common patterns. More sophisticated
    approaches (NLP, Claude-based extraction) would be slower and potentially
    overkill for this use case.

    Args:
        sections: List of Section objects to analyze.
                  Should come from parse_sections().

    Returns:
        List of Claim objects representing extracted claims.
        Order matches document order (section by section, sentence by sentence).

    Example:
        >>> claims = extract_claims(sections)
        >>> for claim in claims:
        ...     print(f"Line {claim.line_number}: {claim.text[:40]}...")
        Line 5: Claude can process images and generate...
        Line 12: The maximum context window is 200k tok...
    """
    claims: list[Claim] = []

    # ==========================================================================
    # CLAIM PATTERN DEFINITIONS
    # ==========================================================================
    #
    # Each pattern is a compiled regex that matches a specific type of claim.
    # re.compile() creates a regex object that can be reused efficiently.
    # re.IGNORECASE makes matching case-insensitive.

    claim_patterns = [
        # Pattern 1: "Claude can/supports/has..." statements
        # Examples:
        #   - "Claude can process images"
        #   - "Claude supports streaming responses"
        #   - "Claude has vision capabilities"
        #   - "Claude is able to understand context"
        #   - "Claude provides detailed explanations"
        # Pattern breakdown:
        #   [Cc]laude     - "Claude" or "claude"
        #   \s+           - One or more spaces
        #   (can|supports?|has|is able to|provides?)  - Action verbs
        #   \s+           - One or more spaces
        #   .+            - Any remaining text
        re.compile(r"[Cc]laude\s+(can|supports?|has|is able to|provides?)\s+.+", re.IGNORECASE),

        # Pattern 2: "Use the X parameter" statements
        # Examples:
        #   - "Use the 'max_tokens' parameter"
        #   - 'Use the "temperature" parameter'
        #   - "Use the `model` parameter"
        # Pattern breakdown:
        #   [Uu]se\s+the  - "Use the" or "use the"
        #   \s+           - Spaces
        #   [`'\"]?       - Optional opening quote/backtick
        #   \w+           - One or more word characters (the parameter name)
        #   [`'\"]?       - Optional closing quote/backtick
        #   \s+parameter  - " parameter"
        re.compile(r"[Uu]se\s+the\s+[`'\"]?\w+[`'\"]?\s+parameter", re.IGNORECASE),

        # Pattern 3: "The X parameter..." statements
        # Examples:
        #   - "The `temperature` parameter controls..."
        #   - "The max_tokens parameter limits..."
        re.compile(r"[Tt]he\s+[`'\"]?\w+[`'\"]?\s+parameter\s+", re.IGNORECASE),

        # Pattern 4: Numeric limits (max/limit + number + unit)
        # Examples:
        #   - "maximum of 100,000 tokens"
        #   - "max 200k tokens"
        #   - "limit of 4096 characters"
        #   - "up to 10 requests"
        # Pattern breakdown:
        #   (?:maximum|max|limit|up to)  - Limit keywords (non-capturing group)
        #   \s+                          - Spaces
        #   (?:of\s+)?                   - Optional "of "
        #   [\d,]+                       - Digits and commas (e.g., "100,000")
        #   k?                           - Optional 'k' for thousands
        #   \s*                          - Optional spaces
        #   (?:tokens?|requests?|characters?)  - Unit words
        re.compile(r"(?:maximum|max|limit|up to)\s+(?:of\s+)?[\d,]+k?\s*(?:tokens?|requests?|characters?)", re.IGNORECASE),

        # Pattern 5: Number + unit + limit (alternate order)
        # Examples:
        #   - "100k tokens limit"
        #   - "4096 tokens maximum"
        #   - "500 requests per minute"
        re.compile(r"[\d,]+k?\s*(?:tokens?|requests?|characters?)\s+(?:limit|maximum|max|per)", re.IGNORECASE),

        # Pattern 6: Context window specifications
        # Examples:
        #   - "context window of 200k"
        #   - "context window is 100,000 tokens"
        re.compile(r"context\s+window\s+(?:of\s+|is\s+)?[\d,]+k?", re.IGNORECASE),

        # Pattern 7: Rate limit specifications
        # Examples:
        #   - "rate limit of 1000"
        #   - "rate limit is 60 requests"
        re.compile(r"rate\s+limit\s+(?:of\s+|is\s+)?[\d,]+", re.IGNORECASE),

        # Pattern 8: API capability statements
        # Examples:
        #   - "The API supports streaming"
        #   - "The API allows batch requests"
        #   - "The API provides token counting"
        #   - "The API accepts JSON input"
        re.compile(r"[Tt]he\s+API\s+(supports?|allows?|provides?|accepts?)\s+", re.IGNORECASE),

        # Pattern 9: Vision/image/document/audio capabilities
        # Examples:
        #   - "vision capabilities include"
        #   - "image capability"
        #   - "document capabilities"
        re.compile(r"(?:vision|image|document|audio)\s+capabilit", re.IGNORECASE),

        # Pattern 10: Streaming/async support statements
        # Examples:
        #   - "supports streaming responses"
        #   - "support async operations"
        #   - "supports synchronous calls"
        re.compile(r"supports?\s+(?:streaming|async|synchronous)", re.IGNORECASE),

        # Pattern 11: Output/response limits
        # Examples:
        #   - "output is limited to 4096 tokens"
        #   - "response maximum is 8192"
        #   - "output limited to 4096"
        re.compile(r"(?:output|response)\s+(?:is\s+)?(?:limited to|maximum|max)\s+[\d,]+", re.IGNORECASE),
    ]

    # ==========================================================================
    # PROCESS EACH SECTION
    # ==========================================================================

    for section in sections:
        # Split the section content into sentences.
        #
        # Regex pattern: (?<=[.!?])\s+
        # - (?<=[.!?])  - Positive lookbehind: must be preceded by . ! or ?
        # - \s+         - One or more whitespace characters
        #
        # This splits at spaces that come after sentence-ending punctuation.
        # Lookbehind doesn't consume the punctuation, so it stays with the sentence.
        sentences = re.split(r"(?<=[.!?])\s+", section.content)

        # Track line numbers approximately.
        # We start at section.start_line + 1 to account for the header line itself.
        current_line = section.start_line + 1  # +1 for header line

        for sentence in sentences:
            # Clean up the sentence (remove leading/trailing whitespace)
            sentence = sentence.strip()

            # Skip empty sentences
            if not sentence:
                continue

            # Check if this sentence matches any claim pattern
            for pattern in claim_patterns:
                if pattern.search(sentence):
                    # Match found! This sentence is a claim.
                    # pattern.search() returns a Match object if found, None otherwise.

                    claims.append(Claim(
                        text=sentence,
                        section_title=section.title,
                        line_number=current_line
                    ))

                    # Break after first match - we don't want duplicates
                    # if a sentence matches multiple patterns
                    break  # Only add once per sentence

            # Update line counter.
            # This is approximate because we're counting by sentence, not character.
            # sentence.count("\n") handles multi-line sentences.
            # +1 assumes each sentence is roughly one line.
            current_line += sentence.count("\n") + 1

    return claims
