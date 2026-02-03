# ABOUTME: Tool for fetching current Claude documentation from Anthropic.
# ABOUTME: Retrieves and parses documentation pages for comparison.

"""
Documentation Fetcher Module
============================

This module fetches current Claude documentation from docs.anthropic.com
and parses the HTML into structured text that can be used for drift analysis.

Pipeline Role: This provides the "source of truth" - the current official
documentation that claims are compared against.

Process:
1. Look up URLs for a given topic (e.g., "api-messages")
2. Fetch the HTML content using HTTP GET requests
3. Parse the HTML to extract text content
4. Return structured DocSection objects

Key Components:
- DocSection: Data class representing a documentation section
- EnhancedHTMLTextExtractor: Custom HTML parser for content extraction
- fetch_current_docs: Main async function to fetch documentation

Why HTML Parsing? Anthropic's documentation is rendered as HTML web pages.
We need to extract the useful text content while ignoring navigation,
scripts, styles, and other non-content elements. This is more complex
than it sounds because HTML can have many nested structures.

The parser handles:
- Headings (h1-h4) → Markdown ## headers
- Code blocks (<pre><code>) → Markdown ``` blocks
- Tables → Markdown tables with | delimiters
- Lists → Markdown - bullet points
- Paragraphs → Plain text with line breaks
"""

# =============================================================================
# IMPORTS
# =============================================================================

# dataclass: Decorator for creating data container classes.
from dataclasses import dataclass

# Path: Object-oriented filesystem paths for the config_path parameter.
from pathlib import Path

# Type hints for collections and optional values.
# - List[X]: A list containing items of type X
# - Dict[str, str]: A dictionary with string keys and string values
# - Optional[X]: Either X or None
from typing import List, Dict, Optional

# HTMLParser: Base class for parsing HTML documents.
# Part of Python's standard library. We subclass it to create a custom parser
# that extracts text content from HTML in a specific way.
from html.parser import HTMLParser

# httpx: Modern async-capable HTTP client for Python.
# We use it instead of requests because:
# 1. Native async/await support (important for concurrent fetching)
# 2. Better timeout handling
# 3. Modern API design
import httpx

# Import configuration functions from our config module.
# get_doc_sources: Returns the mapping of topic names to URLs
# get_fetch_timeout: Returns the timeout in seconds
# DEFAULT_CONFIG: The default configuration dict (for backwards compatibility)
from config import get_doc_sources, get_fetch_timeout, DEFAULT_CONFIG


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class DocSection:
    """
    Represents a section of documentation.

    This is the output format for fetched documentation. Each DocSection
    contains the extracted content from one documentation page.

    Attributes:
        title: The page title, extracted from the first heading.
               Example: "Messages API"

        content: The extracted text content of the page.
                 Formatted as markdown-ish text (headers, code blocks, etc.)

        source_url: The URL this content was fetched from.
                    Used for attribution and verification.
                    Example: "https://docs.anthropic.com/en/api/messages"
    """
    title: str       # Page title from first h1/h2
    content: str     # Extracted text content
    source_url: str  # Origin URL for reference


# =============================================================================
# BACKWARDS COMPATIBILITY
# =============================================================================

# For backwards compatibility, expose DOC_SOURCES directly from config.
# Old code might do: from fetch_docs import DOC_SOURCES
# This allows that to keep working while the actual config lives in config.py.
DOC_SOURCES: Dict[str, str] = DEFAULT_CONFIG["doc_sources"]


# =============================================================================
# HTML TEXT EXTRACTOR
# =============================================================================

class EnhancedHTMLTextExtractor(HTMLParser):
    """
    Enhanced HTML parser to extract text content with better structure.

    This class extends Python's HTMLParser to extract useful text content
    from HTML documentation pages. It handles various HTML elements and
    converts them to a markdown-like format for easier reading.

    How HTMLParser Works:
    1. You feed it HTML text using parser.feed(html_string)
    2. It calls handle_starttag() when it sees <tag>
    3. It calls handle_endtag() when it sees </tag>
    4. It calls handle_data() when it sees text between tags
    5. You collect/process the content in these handlers

    Our Strategy:
    - Skip non-content elements (script, style, nav, footer)
    - Convert structural elements to markdown equivalents
    - Collect text in text_parts list
    - Join and clean up at the end

    State Variables:
    - in_heading: Currently inside an h1-h4 tag
    - in_code: Currently inside a code/pre tag
    - in_table: Currently inside a table
    - skip_depth: Depth of nested skip tags (for proper counting)
    - tag_stack: Stack of currently open tags (for context)

    Why track tag_stack? HTML can be deeply nested. When we see text
    content, we might need to know if we're inside a table cell (td/th)
    to handle it specially. The stack lets us check our "path" in the tree.
    """

    def __init__(self) -> None:
        """
        Initialize the HTML text extractor.

        Sets up all state variables needed for parsing.
        super().__init__() calls the parent HTMLParser's __init__.
        """
        super().__init__()

        # Collected text parts - we'll join these at the end
        self.text_parts: List[str] = []

        # The page title, extracted from the first heading
        self.current_title: str = ""

        # =================================================================
        # STATE FLAGS
        # =================================================================
        # These booleans track what kind of element we're currently inside.
        # This affects how we handle text content.

        self.in_heading = False      # Inside h1, h2, h3, or h4
        self.in_code = False         # Inside code or pre tag
        self.in_table = False        # Inside a table
        self.in_table_header = False # Inside thead
        self.in_list = False         # Inside ul or ol
        self.in_list_item = False    # Inside li

        # Current table row cells - we collect these, then join them
        self.current_row: List[str] = []

        # =================================================================
        # SKIP TAG HANDLING
        # =================================================================
        # Some tags and their content should be completely ignored.
        # These are navigation, scripts, styles - not documentation content.
        self.skip_tags = {"script", "style", "nav", "footer", "header", "aside"}

        # Depth counter for nested skip tags.
        # Example: <nav><div>text</div></nav>
        # When we enter nav, skip_depth = 1. Inside, we ignore everything.
        # When we exit nav, skip_depth = 0 again.
        self.skip_depth = 0

        # Stack of currently open tags for context checking.
        # This is a simple list used as a stack (append/pop from end).
        self.tag_stack: List[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        """
        Handle an opening tag like <div>, <h1>, <p>, etc.

        This is called by HTMLParser whenever it encounters an opening tag.
        We use it to:
        1. Track tag nesting (push to stack)
        2. Enter skip mode for non-content tags
        3. Set state flags for special handling
        4. Add formatting markers (like "## " for headings)

        Args:
            tag: The tag name in lowercase (e.g., "div", "h1", "table")
            attrs: List of (name, value) tuples for attributes.
                   We don't use attributes in this implementation.
        """
        # Always track tag nesting
        self.tag_stack.append(tag)

        # Check if this is a skip tag (non-content element)
        if tag in self.skip_tags:
            self.skip_depth += 1
            return  # Don't process anything else for skip tags

        # If we're inside a skip tag, ignore everything
        if self.skip_depth > 0:
            return

        # =====================================================================
        # HANDLE CONTENT TAGS
        # =====================================================================

        # Headings (h1-h4) become markdown headers
        if tag in ("h1", "h2", "h3", "h4"):
            self.in_heading = True
            # Add markdown header prefix
            # \n\n ensures blank line before header for proper markdown
            self.text_parts.append("\n\n## ")

        # Code blocks - <pre> for block code, <code> for inline code
        elif tag in ("code", "pre"):
            self.in_code = True
            if tag == "pre":
                # Block code - markdown fenced code block
                self.text_parts.append("\n```\n")
            else:
                # Inline code - backticks
                self.text_parts.append("`")

        # Table handling
        elif tag == "table":
            self.in_table = True
            self.text_parts.append("\n")  # Line break before table
        elif tag == "thead":
            self.in_table_header = True
        elif tag == "tr":
            # Start a new row - clear the cell collector
            self.current_row = []
        elif tag in ("th", "td"):
            # Table cells - content is captured in handle_data
            pass  # Content captured in handle_data

        # List handling
        elif tag in ("ul", "ol"):
            self.in_list = True
            self.text_parts.append("\n")
        elif tag == "li":
            self.in_list_item = True
            # Markdown list item with dash prefix
            self.text_parts.append("\n- ")

        # Block elements that need line breaks
        elif tag in ("p", "div"):
            self.text_parts.append("\n")

        # Explicit line break
        elif tag == "br":
            self.text_parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        """
        Handle a closing tag like </div>, </h1>, </p>, etc.

        This is called by HTMLParser whenever it encounters a closing tag.
        We use it to:
        1. Update tag nesting (pop from stack)
        2. Exit skip mode when leaving skip tags
        3. Clear state flags
        4. Add closing formatting (like closing code blocks)

        Args:
            tag: The tag name in lowercase.
        """
        # Pop from tag stack if it matches (basic validation)
        if self.tag_stack and self.tag_stack[-1] == tag:
            self.tag_stack.pop()

        # Handle skip tag exit
        if tag in self.skip_tags:
            self.skip_depth -= 1
            return

        # If still inside skip tags, ignore
        if self.skip_depth > 0:
            return

        # =====================================================================
        # HANDLE CONTENT TAG CLOSINGS
        # =====================================================================

        # Headings - add newline after
        if tag in ("h1", "h2", "h3", "h4"):
            self.in_heading = False
            self.text_parts.append("\n")

        # Code blocks - close the markdown formatting
        elif tag in ("code", "pre"):
            self.in_code = False
            if tag == "pre":
                self.text_parts.append("\n```\n")
            else:
                self.text_parts.append("`")

        # Table end
        elif tag == "table":
            self.in_table = False
            self.text_parts.append("\n")
        elif tag == "thead":
            self.in_table_header = False
        elif tag == "tr":
            # End of table row - format and output the collected cells
            if self.current_row:
                # Join cells with | separator (markdown table format)
                self.text_parts.append(" | ".join(self.current_row))
                self.text_parts.append("\n")

                # Add separator row after header row
                if self.in_table_header:
                    # Create markdown table separator: ---|---|---
                    separator = "|".join(["---"] * len(self.current_row))
                    self.text_parts.append(separator)
                    self.text_parts.append("\n")

            # Clear for next row
            self.current_row = []

        # List end
        elif tag in ("ul", "ol"):
            self.in_list = False
        elif tag == "li":
            self.in_list_item = False

    def handle_data(self, data: str) -> None:
        """
        Handle text content between tags.

        This is called by HTMLParser for text nodes (the actual content).
        Most of the real content extraction happens here.

        Args:
            data: The text content (may include whitespace).
        """
        # Skip content inside skip tags
        if self.skip_depth > 0:
            return

        # Strip whitespace from the text
        text = data.strip()

        # Skip empty content
        if not text:
            return

        # Capture page title from first heading
        if self.in_heading and not self.current_title:
            self.current_title = text

        # Special handling for table cell content
        if self.in_table and self.current_row is not None:
            # Check if we're inside a table cell (td or th)
            # by looking at the tag stack
            if "tr" in self.tag_stack and ("td" in self.tag_stack or "th" in self.tag_stack):
                # Add to current row's cells
                self.current_row.append(text)
                return  # Don't add to text_parts (handled at row end)

        # Normal content - add to text parts
        self.text_parts.append(text)

    def get_text(self) -> str:
        """
        Get extracted text with cleaned up whitespace.

        After parsing is complete, call this to get the final extracted text.
        It joins all collected parts and cleans up excess whitespace.

        Returns:
            The extracted text content as a single string.
        """
        # Join all parts with spaces
        raw_text = " ".join(self.text_parts)

        # Clean up excessive whitespace while preserving structure.
        # Split into lines, clean each line, rejoin.
        lines = raw_text.split("\n")
        cleaned_lines = []

        for line in lines:
            # " ".join(line.split()) normalizes whitespace:
            # - Removes leading/trailing whitespace
            # - Collapses multiple spaces into one
            cleaned = " ".join(line.split())
            if cleaned:  # Only keep non-empty lines
                cleaned_lines.append(cleaned)

        return "\n".join(cleaned_lines)

    def get_title(self) -> str:
        """
        Get the extracted page title.

        Returns the title from the first heading encountered,
        or "Documentation" as a fallback.

        Returns:
            The page title as a string.
        """
        return self.current_title or "Documentation"


# =============================================================================
# BACKWARDS COMPATIBILITY ALIAS
# =============================================================================

# Old code might import SimpleHTMLTextExtractor.
# This alias ensures it still works.
SimpleHTMLTextExtractor = EnhancedHTMLTextExtractor


# =============================================================================
# URL RESOLUTION
# =============================================================================

def _get_relevant_urls(
    topic: str,
    config_path: Optional[Path] = None
) -> List[str]:
    """
    Get URLs relevant to the requested topic.

    This function maps topic names to their corresponding documentation URLs.
    It handles:
    1. Direct matches (topic exactly matches a key)
    2. Partial matches (topic is contained in a key, or vice versa)
    3. Fallback to all URLs if no matches found

    Args:
        topic: The topic to fetch documentation for.
               Examples: "api-messages", "models", "vision"
        config_path: Optional path to config file.

    Returns:
        List of documentation URLs relevant to the topic.

    Example:
        >>> _get_relevant_urls("api-messages")
        ['https://docs.anthropic.com/en/api/messages']

        >>> _get_relevant_urls("streaming")  # Partial match
        ['https://...api-messages-streaming', 'https://...streaming']

        >>> _get_relevant_urls("unknown-topic")  # Returns all URLs
        ['https://...', ...]
    """
    # Get configured doc sources
    doc_sources = get_doc_sources(config_path)

    # Convert topic to lowercase for case-insensitive matching
    topic_lower = topic.lower()

    # Try direct match first (most specific)
    if topic_lower in doc_sources:
        return [doc_sources[topic_lower]]

    # Try partial matches (topic contains key, or key contains topic)
    relevant = []
    for key, url in doc_sources.items():
        # Either the topic is part of the key, or the key is part of the topic
        if topic_lower in key or key in topic_lower:
            relevant.append(url)

    # If no matches found, return all sources as fallback
    # This ensures we always have some documentation to work with
    return relevant if relevant else list(doc_sources.values())


# =============================================================================
# MAIN FETCH FUNCTION
# =============================================================================

async def fetch_current_docs(
    topic: str,
    config_path: Optional[Path] = None
) -> List[DocSection]:
    """
    Fetch current Claude documentation for a given topic.

    This is the main entry point for fetching documentation. It:
    1. Resolves the topic to relevant URLs
    2. Fetches each URL using async HTTP requests
    3. Parses the HTML to extract text content
    4. Returns structured DocSection objects

    The function is async because HTTP requests can take time, and we
    want to allow concurrent operations in the calling code.

    Args:
        topic: The topic to fetch documentation for.
               Examples: "api-messages", "models", "vision"
        config_path: Optional path to config file with custom doc sources.

    Returns:
        List of DocSection objects containing the documentation.
        May be empty if no URLs could be fetched successfully.

    Raises:
        Exception: If an HTTP request fails (after raise_for_status).
                   The caller (cli.py) catches and handles these.

    Example:
        >>> docs = await fetch_current_docs("api-messages")
        >>> len(docs)
        1
        >>> docs[0].title
        'Messages API'
        >>> docs[0].content[:50]
        '## Messages Create a message with Claude...'
    """
    # Get list of relevant URLs for this topic
    urls = _get_relevant_urls(topic, config_path)

    # Get configured timeout
    timeout = get_fetch_timeout(config_path)

    # Collect results
    sections: List[DocSection] = []

    # Create an async HTTP client with configuration.
    # Using 'async with' ensures the client is properly closed when done.
    async with httpx.AsyncClient(
        timeout=float(timeout),      # Convert int to float for httpx
        follow_redirects=True,       # Automatically follow HTTP redirects
        headers={
            # Identify ourselves in the User-Agent header
            # This is good HTTP citizenship
            "User-Agent": "ContentFreshnessSystem/1.0"
        }
    ) as client:
        # Fetch each URL
        for url in urls:
            # await: Pause this coroutine until the HTTP response arrives.
            # This allows other async tasks to run while waiting.
            response = await client.get(url)

            # raise_for_status() raises an exception for 4xx/5xx responses.
            # This ensures we only process successful responses.
            response.raise_for_status()

            # Parse the HTML content.
            # Create a new parser instance for each page.
            parser = SimpleHTMLTextExtractor()

            # feed() processes the HTML and calls our handle_* methods.
            # response.text is the decoded response body as a string.
            parser.feed(response.text)

            # Extract the processed content
            content = parser.get_text()
            title = parser.get_title()

            # Only add if we got actual content
            if content:
                sections.append(DocSection(
                    title=title,
                    content=content,
                    source_url=url
                ))

    return sections
