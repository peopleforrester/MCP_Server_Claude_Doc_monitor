# ABOUTME: Tool for fetching recent changes from Anthropic changelog.
# ABOUTME: Retrieves and parses changelog entries within a date range.

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional
from html.parser import HTMLParser

import httpx

from config import get_changelog_url, get_fetch_timeout, DEFAULT_CONFIG


@dataclass
class ChangelogEntry:
    """Represents a changelog entry."""

    date: str
    title: str
    description: str
    source_url: str


# For backwards compatibility
CHANGELOG_URL = DEFAULT_CONFIG["changelog_url"]


class ChangelogParser(HTMLParser):
    """Parser for extracting changelog entries from HTML."""

    def __init__(self) -> None:
        super().__init__()
        self.entries: List[dict] = []
        self.current_entry: dict = {}
        self.in_date = False
        self.in_content = False
        self.current_text: List[str] = []
        self.skip_tags = {"script", "style", "nav", "footer"}
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in self.skip_tags:
            self.skip_depth += 1
        if tag == "h2":
            # New entry starts with h2 date header
            if self.current_entry:
                self.entries.append(self.current_entry)
            self.current_entry = {}
            self.in_date = True
            self.current_text = []
        elif tag in ("h3", "h4") and self.current_entry:
            self.in_content = True
            self.current_text = []
        elif tag == "p" and self.current_entry:
            self.in_content = True

    def handle_endtag(self, tag: str) -> None:
        if tag in self.skip_tags:
            self.skip_depth -= 1
        if tag == "h2" and self.in_date:
            self.in_date = False
            text = " ".join(self.current_text).strip()
            # Try to parse as date
            date_match = re.search(r"\d{4}-\d{2}-\d{2}", text)
            if date_match:
                self.current_entry["date"] = date_match.group()
            else:
                self.current_entry["date"] = text[:10] if text else ""
        elif tag in ("h3", "h4") and self.in_content:
            self.in_content = False
            text = " ".join(self.current_text).strip()
            if text and "title" not in self.current_entry:
                self.current_entry["title"] = text
        elif tag == "p" and self.in_content:
            self.in_content = False
            text = " ".join(self.current_text).strip()
            if text:
                existing = self.current_entry.get("description", "")
                self.current_entry["description"] = (existing + " " + text).strip()

    def handle_data(self, data: str) -> None:
        if self.skip_depth > 0:
            return
        if self.in_date or self.in_content:
            text = data.strip()
            if text:
                self.current_text.append(text)

    def get_entries(self) -> List[dict]:
        # Don't forget the last entry
        if self.current_entry:
            self.entries.append(self.current_entry)
        return self.entries


def _is_within_days(date_str: str, days: int) -> bool:
    """Check if a date string is within the specified number of days."""
    try:
        entry_date = datetime.strptime(date_str, "%Y-%m-%d")
        cutoff = datetime.now() - timedelta(days=days)
        return entry_date >= cutoff
    except ValueError:
        # If we can't parse the date, include it
        return True


async def get_recent_changes(
    days: int = 30,
    config_path: Optional[Path] = None
) -> List[ChangelogEntry]:
    """
    Fetch recent changes from the Anthropic changelog.

    Args:
        days: Number of days to look back for changes.
        config_path: Optional path to config file.

    Returns:
        List of ChangelogEntry objects for recent changes.
    """
    changelog_url = get_changelog_url(config_path)
    timeout = get_fetch_timeout(config_path)

    async with httpx.AsyncClient(
        timeout=float(timeout),
        follow_redirects=True,
        headers={"User-Agent": "ContentFreshnessSystem/1.0"}
    ) as client:
        response = await client.get(changelog_url)
        response.raise_for_status()

        parser = ChangelogParser()
        parser.feed(response.text)

        entries = []
        for entry_dict in parser.get_entries():
            if not entry_dict.get("date"):
                continue

            # Filter by date range
            if not _is_within_days(entry_dict.get("date", ""), days):
                continue

            entries.append(ChangelogEntry(
                date=entry_dict.get("date", ""),
                title=entry_dict.get("title", "Update"),
                description=entry_dict.get("description", ""),
                source_url=changelog_url
            ))

        return entries
