# ABOUTME: Input handler for parsing training documents and extracting claims.
# ABOUTME: Parses markdown into sections and identifies capability statements.

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass
class Section:
    """Represents a section of a markdown document."""

    title: str
    content: str
    level: int
    start_line: int


@dataclass
class Claim:
    """Represents a capability claim extracted from a document."""

    text: str
    section_title: str
    line_number: int


def load_markdown_file(file_path: Path) -> str:
    """
    Load content from a markdown file.

    Args:
        file_path: Path to the markdown file.

    Returns:
        The file contents as a string.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    return file_path.read_text()


def parse_sections(content: str) -> List[Section]:
    """
    Parse markdown content into sections based on headers.

    Args:
        content: The markdown content to parse.

    Returns:
        List of Section objects representing each section.
    """
    if not content.strip():
        return []

    sections: List[Section] = []
    lines = content.split("\n")
    header_pattern = re.compile(r"^(#{1,6})\s+(.+)$")

    current_section_title = None
    current_section_level = 0
    current_section_start = 1
    current_content_lines: List[str] = []

    for line_num, line in enumerate(lines, start=1):
        match = header_pattern.match(line)

        if match:
            # Save previous section if exists
            if current_section_title is not None:
                sections.append(Section(
                    title=current_section_title,
                    content="\n".join(current_content_lines).strip(),
                    level=current_section_level,
                    start_line=current_section_start
                ))
            elif current_content_lines and any(l.strip() for l in current_content_lines):
                # Content before first header becomes intro section
                sections.append(Section(
                    title="(Introduction)",
                    content="\n".join(current_content_lines).strip(),
                    level=0,
                    start_line=1
                ))

            # Start new section
            current_section_level = len(match.group(1))
            current_section_title = match.group(2).strip()
            current_section_start = line_num
            current_content_lines = []
        else:
            current_content_lines.append(line)

    # Don't forget the last section
    if current_section_title is not None:
        sections.append(Section(
            title=current_section_title,
            content="\n".join(current_content_lines).strip(),
            level=current_section_level,
            start_line=current_section_start
        ))
    elif current_content_lines and any(l.strip() for l in current_content_lines):
        # Only content, no headers at all
        sections.append(Section(
            title="(Introduction)",
            content="\n".join(current_content_lines).strip(),
            level=0,
            start_line=1
        ))

    return sections


def extract_claims(sections: List[Section]) -> List[Claim]:
    """
    Extract capability claims from document sections.

    Identifies statements about Claude capabilities, API syntax,
    and numeric limits that could become outdated.

    Args:
        sections: List of Section objects to analyze.

    Returns:
        List of Claim objects representing extracted claims.
    """
    claims: List[Claim] = []

    # Patterns that indicate capability claims
    claim_patterns = [
        # "Claude can/supports/has..."
        re.compile(r"[Cc]laude\s+(can|supports?|has|is able to|provides?)\s+.+", re.IGNORECASE),
        # API parameter mentions
        re.compile(r"[Uu]se\s+the\s+[`'\"]?\w+[`'\"]?\s+parameter", re.IGNORECASE),
        re.compile(r"[Tt]he\s+[`'\"]?\w+[`'\"]?\s+parameter\s+", re.IGNORECASE),
        # Numeric limits (tokens, requests, etc.)
        re.compile(r"(?:maximum|max|limit|up to)\s+(?:of\s+)?[\d,]+k?\s*(?:tokens?|requests?|characters?)", re.IGNORECASE),
        re.compile(r"[\d,]+k?\s*(?:tokens?|requests?|characters?)\s+(?:limit|maximum|max|per)", re.IGNORECASE),
        # Context window mentions
        re.compile(r"context\s+window\s+(?:of\s+|is\s+)?[\d,]+k?", re.IGNORECASE),
        # Rate limits
        re.compile(r"rate\s+limit\s+(?:of\s+|is\s+)?[\d,]+", re.IGNORECASE),
        # API supports/allows
        re.compile(r"[Tt]he\s+API\s+(supports?|allows?|provides?|accepts?)\s+", re.IGNORECASE),
        # Model capabilities
        re.compile(r"(?:vision|image|document|audio)\s+capabilit", re.IGNORECASE),
        # Streaming/async mentions
        re.compile(r"supports?\s+(?:streaming|async|synchronous)", re.IGNORECASE),
        # Output limits
        re.compile(r"(?:output|response)\s+(?:is\s+)?(?:limited to|maximum|max)\s+[\d,]+", re.IGNORECASE),
    ]

    for section in sections:
        # Split content into sentences for finer-grained claims
        sentences = re.split(r"(?<=[.!?])\s+", section.content)
        current_line = section.start_line + 1  # +1 for header line

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            # Check if sentence matches any claim pattern
            for pattern in claim_patterns:
                if pattern.search(sentence):
                    claims.append(Claim(
                        text=sentence,
                        section_title=section.title,
                        line_number=current_line
                    ))
                    break  # Only add once per sentence

            # Approximate line tracking
            current_line += sentence.count("\n") + 1

    return claims
