# ABOUTME: E2E tests that fetch and parse the live Claude documentation pages.
# ABOUTME: Needs network access to platform.claude.com; no API key.

from __future__ import annotations

import re

from config import get_doc_sources
from mcp_server.tools.fetch_docs import fetch_current_docs
from mcp_server.tools.get_changelog import get_recent_changes


async def test_live_doc_page_parses_to_content() -> None:
    """A configured doc page should fetch and parse into substantial text."""
    sections = await fetch_current_docs("context-windows")

    assert len(sections) == 1
    section = sections[0]
    assert section.source_url == get_doc_sources()["context-windows"]
    assert section.title
    assert len(section.content) > 1000
    assert "context window" in section.content.lower()


async def test_live_changelog_has_dated_entries() -> None:
    """The live release notes should parse into dated, described entries."""
    entries = await get_recent_changes(days=365)

    assert entries, "parsed no changelog entries from the past year"
    for entry in entries:
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", entry.date), entry
        assert entry.description, entry
