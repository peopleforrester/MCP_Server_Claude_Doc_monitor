# ABOUTME: Tool for fetching current Claude documentation from Anthropic.
# ABOUTME: Retrieves and parses documentation pages for comparison.

import re
from dataclasses import dataclass
from typing import List, Dict
from html.parser import HTMLParser

import httpx


@dataclass
class DocSection:
    """Represents a section of documentation."""

    title: str
    content: str
    source_url: str


# Hardcoded documentation sources for MVP
DOC_SOURCES: Dict[str, str] = {
    "api": "https://docs.anthropic.com/en/api/getting-started",
    "models": "https://docs.anthropic.com/en/docs/about-claude/models",
    "messages": "https://docs.anthropic.com/en/api/messages",
    "vision": "https://docs.anthropic.com/en/docs/build-with-claude/vision",
    "context": "https://docs.anthropic.com/en/docs/build-with-claude/context-windows",
    "rate-limits": "https://docs.anthropic.com/en/api/rate-limits",
}


class SimpleHTMLTextExtractor(HTMLParser):
    """Simple HTML parser to extract text content."""

    def __init__(self) -> None:
        super().__init__()
        self.text_parts: List[str] = []
        self.current_title: str = ""
        self.in_heading = False
        self.skip_tags = {"script", "style", "nav", "footer", "header"}
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in self.skip_tags:
            self.skip_depth += 1
        if tag in ("h1", "h2", "h3"):
            self.in_heading = True

    def handle_endtag(self, tag: str) -> None:
        if tag in self.skip_tags:
            self.skip_depth -= 1
        if tag in ("h1", "h2", "h3"):
            self.in_heading = False

    def handle_data(self, data: str) -> None:
        if self.skip_depth > 0:
            return
        text = data.strip()
        if text:
            if self.in_heading and not self.current_title:
                self.current_title = text
            self.text_parts.append(text)

    def get_text(self) -> str:
        return " ".join(self.text_parts)

    def get_title(self) -> str:
        return self.current_title or "Documentation"


def _get_relevant_urls(topic: str) -> List[str]:
    """Get URLs relevant to the requested topic."""
    topic_lower = topic.lower()

    # Direct match
    if topic_lower in DOC_SOURCES:
        return [DOC_SOURCES[topic_lower]]

    # Partial matches
    relevant = []
    for key, url in DOC_SOURCES.items():
        if topic_lower in key or key in topic_lower:
            relevant.append(url)

    # If no matches, return all sources
    return relevant if relevant else list(DOC_SOURCES.values())


async def fetch_current_docs(topic: str) -> List[DocSection]:
    """
    Fetch current Claude documentation for a given topic.

    Args:
        topic: The topic to fetch documentation for (e.g., "api", "models").

    Returns:
        List of DocSection objects containing the documentation.

    Raises:
        Exception: If HTTP request fails.
    """
    urls = _get_relevant_urls(topic)
    sections: List[DocSection] = []

    async with httpx.AsyncClient(
        timeout=30.0,
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
