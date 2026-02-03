# ABOUTME: Tool for fetching current Claude documentation from Anthropic.
# ABOUTME: Retrieves and parses documentation pages for comparison.

from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Optional
from html.parser import HTMLParser

import httpx

from config import get_doc_sources, get_fetch_timeout, DEFAULT_CONFIG


@dataclass
class DocSection:
    """Represents a section of documentation."""

    title: str
    content: str
    source_url: str


# For backwards compatibility, expose DOC_SOURCES from config
DOC_SOURCES: Dict[str, str] = DEFAULT_CONFIG["doc_sources"]


class EnhancedHTMLTextExtractor(HTMLParser):
    """Enhanced HTML parser to extract text content with better structure."""

    def __init__(self) -> None:
        super().__init__()
        self.text_parts: List[str] = []
        self.current_title: str = ""
        self.in_heading = False
        self.in_code = False
        self.in_table = False
        self.in_table_header = False
        self.in_list = False
        self.in_list_item = False
        self.current_row: List[str] = []
        self.skip_tags = {"script", "style", "nav", "footer", "header", "aside"}
        self.skip_depth = 0
        self.tag_stack: List[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        self.tag_stack.append(tag)

        if tag in self.skip_tags:
            self.skip_depth += 1
            return

        if self.skip_depth > 0:
            return

        # Headings
        if tag in ("h1", "h2", "h3", "h4"):
            self.in_heading = True
            self.text_parts.append("\n\n## ")

        # Code blocks - important for API parameters
        elif tag in ("code", "pre"):
            self.in_code = True
            if tag == "pre":
                self.text_parts.append("\n```\n")
            else:
                self.text_parts.append("`")

        # Tables - important for specs and limits
        elif tag == "table":
            self.in_table = True
            self.text_parts.append("\n")
        elif tag == "thead":
            self.in_table_header = True
        elif tag == "tr":
            self.current_row = []
        elif tag in ("th", "td"):
            pass  # Content captured in handle_data

        # Lists - important for parameters and features
        elif tag in ("ul", "ol"):
            self.in_list = True
            self.text_parts.append("\n")
        elif tag == "li":
            self.in_list_item = True
            self.text_parts.append("\n- ")

        # Paragraphs and divs
        elif tag in ("p", "div"):
            self.text_parts.append("\n")

        # Line breaks
        elif tag == "br":
            self.text_parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if self.tag_stack and self.tag_stack[-1] == tag:
            self.tag_stack.pop()

        if tag in self.skip_tags:
            self.skip_depth -= 1
            return

        if self.skip_depth > 0:
            return

        # Headings
        if tag in ("h1", "h2", "h3", "h4"):
            self.in_heading = False
            self.text_parts.append("\n")

        # Code blocks
        elif tag in ("code", "pre"):
            self.in_code = False
            if tag == "pre":
                self.text_parts.append("\n```\n")
            else:
                self.text_parts.append("`")

        # Tables
        elif tag == "table":
            self.in_table = False
            self.text_parts.append("\n")
        elif tag == "thead":
            self.in_table_header = False
        elif tag == "tr":
            if self.current_row:
                self.text_parts.append(" | ".join(self.current_row))
                self.text_parts.append("\n")
                if self.in_table_header:
                    # Add markdown table separator
                    self.text_parts.append("|".join(["---"] * len(self.current_row)))
                    self.text_parts.append("\n")
            self.current_row = []

        # Lists
        elif tag in ("ul", "ol"):
            self.in_list = False
        elif tag == "li":
            self.in_list_item = False

    def handle_data(self, data: str) -> None:
        if self.skip_depth > 0:
            return

        text = data.strip()
        if not text:
            return

        # Capture page title from first heading
        if self.in_heading and not self.current_title:
            self.current_title = text

        # Table cell content
        if self.in_table and self.current_row is not None:
            if "tr" in self.tag_stack and ("td" in self.tag_stack or "th" in self.tag_stack):
                self.current_row.append(text)
                return

        self.text_parts.append(text)

    def get_text(self) -> str:
        """Get extracted text with cleaned up whitespace."""
        raw_text = " ".join(self.text_parts)
        # Clean up excessive whitespace while preserving structure
        lines = raw_text.split("\n")
        cleaned_lines = []
        for line in lines:
            cleaned = " ".join(line.split())
            if cleaned:
                cleaned_lines.append(cleaned)
        return "\n".join(cleaned_lines)

    def get_title(self) -> str:
        return self.current_title or "Documentation"


# Backwards compatibility alias
SimpleHTMLTextExtractor = EnhancedHTMLTextExtractor


def _get_relevant_urls(
    topic: str,
    config_path: Optional[Path] = None
) -> List[str]:
    """Get URLs relevant to the requested topic."""
    doc_sources = get_doc_sources(config_path)
    topic_lower = topic.lower()

    # Direct match
    if topic_lower in doc_sources:
        return [doc_sources[topic_lower]]

    # Partial matches
    relevant = []
    for key, url in doc_sources.items():
        if topic_lower in key or key in topic_lower:
            relevant.append(url)

    # If no matches, return all sources
    return relevant if relevant else list(doc_sources.values())


async def fetch_current_docs(
    topic: str,
    config_path: Optional[Path] = None
) -> List[DocSection]:
    """
    Fetch current Claude documentation for a given topic.

    Args:
        topic: The topic to fetch documentation for (e.g., "api", "models").
        config_path: Optional path to config file with custom doc sources.

    Returns:
        List of DocSection objects containing the documentation.

    Raises:
        Exception: If HTTP request fails.
    """
    urls = _get_relevant_urls(topic, config_path)
    timeout = get_fetch_timeout(config_path)
    sections: List[DocSection] = []

    async with httpx.AsyncClient(
        timeout=float(timeout),
        follow_redirects=True,
        headers={"User-Agent": "ContentFreshnessSystem/1.0"}
    ) as client:
        for url in urls:
            response = await client.get(url)
            response.raise_for_status()

            parser = SimpleHTMLTextExtractor()
            parser.feed(response.text)

            content = parser.get_text()
            title = parser.get_title()

            if content:
                sections.append(DocSection(
                    title=title,
                    content=content,
                    source_url=url
                ))

    return sections
