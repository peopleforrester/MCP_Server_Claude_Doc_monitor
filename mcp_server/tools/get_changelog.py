# ABOUTME: Tool for fetching recent changes from Anthropic changelog.
# ABOUTME: Retrieves and parses changelog entries within a date range.

"""
Changelog Fetcher Module
========================

This module fetches recent changes from the Anthropic changelog page.
It's useful for identifying what has changed recently in Claude's capabilities,
which can inform which claims might need review.

Use Case: If the changelog shows a recent update to context windows, you might
want to specifically check any claims about context window sizes.

Process:
1. Fetch the changelog HTML page
2. Parse it to extract dated entries
3. Filter entries by the requested date range
4. Return structured ChangelogEntry objects

Key Components:
- ChangelogEntry: Data class representing one changelog entry
- ChangelogParser: Custom HTML parser for changelog-specific structure
- get_recent_changes: Main async function to fetch and filter entries

The Anthropic changelog typically has entries like:
    ## 2024-01-15
    ### New Feature
    Description of the new feature...

Our parser looks for these patterns to extract structured data.
"""

# =============================================================================
# IMPORTS
# =============================================================================

from __future__ import annotations

# re: Regular expression module for pattern matching.
# Used to extract dates from changelog entry headers.
import re

# dataclass: Decorator for creating data container classes.
from dataclasses import dataclass

# datetime, timedelta: For date calculations.
# - datetime: Represents a specific moment in time
# - timedelta: Represents a duration (e.g., "30 days")
from datetime import datetime, timedelta

# Path: Object-oriented filesystem paths for the config_path parameter.
from pathlib import Path


# HTMLParser: Base class for parsing HTML documents.
from html.parser import HTMLParser

# httpx: Modern async HTTP client for Python.
import httpx

# Import configuration functions from our config module.
from config import get_changelog_url, get_fetch_timeout, DEFAULT_CONFIG


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class ChangelogEntry:
    """
    Represents a changelog entry.

    Each entry corresponds to one update announcement on the changelog page.
    The Anthropic changelog typically organizes updates by date with
    titles describing what changed.

    Attributes:
        date: The date of the entry in YYYY-MM-DD format.
              Example: "2024-01-15"
              Parsed from the changelog's h2 date headers.

        title: A short title describing the change.
               Example: "Extended Context Window"
               Parsed from h3/h4 subheadings under the date.

        description: Longer description of the change.
                     Contains the details of what was updated.
                     Parsed from paragraph text under the title.

        source_url: URL to the changelog page.
                    Used for verification and reference.
    """
    date: str            # Date in YYYY-MM-DD format
    title: str           # Entry title
    description: str     # Entry description/details
    source_url: str      # Origin URL for reference


# =============================================================================
# BACKWARDS COMPATIBILITY
# =============================================================================

# Expose CHANGELOG_URL directly for backwards compatibility.
# Old code might do: from get_changelog import CHANGELOG_URL
CHANGELOG_URL = DEFAULT_CONFIG["changelog_url"]


# =============================================================================
# CHANGELOG PARSER
# =============================================================================

class ChangelogParser(HTMLParser):
    """
    Parser for extracting changelog entries from HTML.

    This specialized parser understands the structure of the Anthropic
    changelog page. It expects a format like:

        <h2>2024-01-15</h2>          <- Date header
        <h3>New Feature</h3>          <- Entry title
        <p>Description here...</p>    <- Entry description

    The parser collects entries as it encounters this pattern.

    State Machine:
    - Initial state: Looking for h2 date header
    - After h2: Collecting entry data until next h2
    - h3/h4 become titles, p becomes description

    Implementation Notes:
    - We track state with in_date/in_content booleans
    - current_entry dict collects data for one entry
    - entries list accumulates completed entries
    """

    def __init__(self) -> None:
        """
        Initialize the changelog parser.

        Sets up state variables for tracking the parsing progress.
        """
        super().__init__()

        # List of completed entries (each is a dict with date, title, description)
        self.entries: list[dict] = []

        # Current entry being built (empty dict when not in an entry)
        self.current_entry: dict = {}

        # State flags
        self.in_date = False         # Inside an h2 (date header)
        self.in_content = False      # Inside an h3/h4/p (entry content)

        # Collector for text content of current element
        self.current_text: list[str] = []

        # Tags to skip (navigation, scripts, etc.)
        self.skip_tags = {"script", "style", "nav", "footer"}
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:
        """
        Handle opening tags to track entry structure.

        The key insight is that h2 tags mark dates (new entries),
        and h3/h4/p tags contain the entry content.

        Args:
            tag: The tag name in lowercase.
            attrs: List of (name, value) attribute tuples.
        """
        # Track skip tags (non-content elements)
        if tag in self.skip_tags:
            self.skip_depth += 1

        # h2 marks a new date/entry
        if tag == "h2":
            # Save the previous entry if we have one
            if self.current_entry:
                self.entries.append(self.current_entry)

            # Start a new entry
            self.current_entry = {}
            self.in_date = True
            self.current_text = []

        # h3 and h4 mark entry titles
        elif tag in ("h3", "h4") and self.current_entry:
            self.in_content = True
            self.current_text = []

        # p tags contain description text
        elif tag == "p" and self.current_entry:
            self.in_content = True

    def handle_endtag(self, tag: str) -> None:
        """
        Handle closing tags to finalize collected content.

        When we hit a closing tag, we need to process whatever
        text we collected between the opening and closing tags.

        Args:
            tag: The tag name in lowercase.
        """
        # Track skip tag depth
        if tag in self.skip_tags:
            self.skip_depth -= 1

        # End of date header - extract the date
        if tag == "h2" and self.in_date:
            self.in_date = False

            # Join collected text pieces
            text = " ".join(self.current_text).strip()

            # Try to find a YYYY-MM-DD date pattern in the text.
            # re.search() finds the first match anywhere in the string.
            # The pattern \d{4}-\d{2}-\d{2} matches dates like "2024-01-15".
            date_match = re.search(r"\d{4}-\d{2}-\d{2}", text)

            if date_match:
                # Found a properly formatted date
                self.current_entry["date"] = date_match.group()
            else:
                # No standard date format - use first 10 chars as fallback
                # This handles cases like "January 15, 2024"
                self.current_entry["date"] = text[:10] if text else ""

        # End of title (h3/h4)
        elif tag in ("h3", "h4") and self.in_content:
            self.in_content = False

            # Join collected text
            text = " ".join(self.current_text).strip()

            # Only set title if we don't have one yet
            # (first h3/h4 after the date becomes the title)
            if text and "title" not in self.current_entry:
                self.current_entry["title"] = text

        # End of paragraph - append to description
        elif tag == "p" and self.in_content:
            self.in_content = False

            text = " ".join(self.current_text).strip()

            if text:
                # Get existing description (or empty string)
                existing = self.current_entry.get("description", "")

                # Append new text with space separator.
                # strip() removes leading/trailing whitespace from the result.
                self.current_entry["description"] = (existing + " " + text).strip()

    def handle_data(self, data: str) -> None:
        """
        Handle text content between tags.

        We collect text when we're inside relevant elements
        (date headers, titles, paragraphs).

        Args:
            data: The text content.
        """
        # Skip content inside skip tags
        if self.skip_depth > 0:
            return

        # Collect text when inside date or content elements
        if self.in_date or self.in_content:
            text = data.strip()
            if text:
                self.current_text.append(text)

    def get_entries(self) -> list[dict]:
        """
        Get all parsed entries.

        Call this after feeding all HTML to get the complete list of entries.
        Don't forget to handle the last entry which might not have been
        appended yet (no h2 after it to trigger the append).

        Returns:
            List of entry dictionaries, each with date, title, description.
        """
        # Don't forget the last entry
        # (there's no h2 after the last entry to trigger the append)
        if self.current_entry:
            self.entries.append(self.current_entry)

        return self.entries


# =============================================================================
# DATE FILTERING HELPER
# =============================================================================

def _is_within_days(date_str: str, days: int) -> bool:
    """
    Check if a date string is within the specified number of days.

    This is used to filter changelog entries to only include recent ones.
    "Recent" is defined as within `days` days of the current date.

    Args:
        date_str: A date string in YYYY-MM-DD format.
                  Example: "2024-01-15"
        days: Number of days to look back.
              Example: 30 means include entries from the last 30 days.

    Returns:
        True if the date is within the range (recent enough).
        False if the date is older than the cutoff.
        True if the date can't be parsed (to avoid excluding valid entries).

    Example:
        # If today is 2024-02-01 and days=30:
        >>> _is_within_days("2024-01-15", 30)  # 17 days ago
        True
        >>> _is_within_days("2023-12-01", 30)  # 62 days ago
        False
    """
    try:
        # Parse the date string into a datetime object.
        # strptime() parses a string according to a format:
        # %Y = 4-digit year, %m = 2-digit month, %d = 2-digit day
        entry_date = datetime.strptime(date_str, "%Y-%m-%d")

        # Calculate the cutoff date.
        # datetime.now() gets the current date/time.
        # timedelta(days=N) represents a duration of N days.
        # Subtracting gives us the date N days ago.
        cutoff = datetime.now() - timedelta(days=days)

        # Check if the entry date is at or after the cutoff.
        # >= returns True if entry_date is more recent than cutoff.
        return entry_date >= cutoff

    except ValueError:
        # ValueError is raised if the date string doesn't match the format.
        # Include entries with unparseable dates to avoid losing data.
        # The caller can handle filtering if needed.
        return True


# =============================================================================
# MAIN FETCH FUNCTION
# =============================================================================

async def get_recent_changes(
    days: int = 30,
    config_path: Path | None = None
) -> list[ChangelogEntry]:
    """
    Fetch recent changes from the Anthropic changelog.

    This function fetches the changelog page, parses it for entries,
    and returns only entries from the last N days.

    Use this to identify what has changed recently in Claude's capabilities,
    which can help prioritize which claims to review.

    Args:
        days: Number of days to look back for changes.
              Default: 30 (last month)
        config_path: Optional path to config file with custom settings.

    Returns:
        List of ChangelogEntry objects for recent changes.
        Sorted from newest to oldest (order from the webpage).
        May be empty if no recent changes or if parsing fails.

    Example:
        >>> changes = await get_recent_changes(days=7)
        >>> for change in changes:
        ...     print(f"{change.date}: {change.title}")
        2024-01-15: Extended Context Window
        2024-01-12: Vision API Updates
    """
    # Get configured URLs and timeout
    changelog_url = get_changelog_url(config_path)
    timeout = get_fetch_timeout(config_path)

    # Create async HTTP client.
    # 'async with' ensures proper cleanup when done.
    async with httpx.AsyncClient(
        timeout=float(timeout),
        follow_redirects=True,
        headers={"User-Agent": "ContentFreshnessSystem/1.0"}
    ) as client:
        # Fetch the changelog page.
        # await pauses until the response arrives.
        response = await client.get(changelog_url)

        # Raise exception for HTTP errors (4xx, 5xx responses)
        response.raise_for_status()

        # Parse the HTML content
        parser = ChangelogParser()

        # feed() processes the HTML and populates parser.entries
        parser.feed(response.text)

        # Process parsed entries into ChangelogEntry objects
        entries = []

        for entry_dict in parser.get_entries():
            # Skip entries without a date (invalid entries)
            if not entry_dict.get("date"):
                continue

            # Filter by date range
            # .get() returns None if the key doesn't exist
            if not _is_within_days(entry_dict.get("date", ""), days):
                continue

            # Create ChangelogEntry object.
            # .get(key, default) returns default if key not found.
            entries.append(ChangelogEntry(
                date=entry_dict.get("date", ""),
                title=entry_dict.get("title", "Update"),  # Default title
                description=entry_dict.get("description", ""),
                source_url=changelog_url
            ))

        return entries
