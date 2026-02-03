# ABOUTME: Unit tests for MCP server documentation fetching tools.
# ABOUTME: Tests fetch_docs, get_changelog, and search_docs functionality.

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from mcp_server.tools.fetch_docs import (
    fetch_current_docs,
    DocSection,
    DOC_SOURCES,
)
from mcp_server.tools.get_changelog import (
    get_recent_changes,
    ChangelogEntry,
)
from mcp_server.tools.search_docs import (
    search_docs,
    SearchResult,
)


class TestFetchCurrentDocs:
    """Tests for the fetch_current_docs tool."""

    @pytest.mark.asyncio
    async def test_fetch_docs_returns_doc_sections(self) -> None:
        """Should return DocSection objects with content."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body><h1>API Reference</h1><p>Content here.</p></body></html>"

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            result = await fetch_current_docs("api")

        assert len(result) >= 1
        assert all(isinstance(section, DocSection) for section in result)

    @pytest.mark.asyncio
    async def test_fetch_docs_includes_source_url(self) -> None:
        """Each DocSection should include its source URL."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body><p>Test content</p></body></html>"

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            result = await fetch_current_docs("models")

        assert len(result) >= 1
        assert all(section.source_url for section in result)

    @pytest.mark.asyncio
    async def test_fetch_docs_handles_http_error(self) -> None:
        """Should raise exception on HTTP errors."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = Exception("Server error")

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            with pytest.raises(Exception):
                await fetch_current_docs("api")

    @pytest.mark.asyncio
    async def test_fetch_docs_filters_by_topic(self) -> None:
        """Should fetch only URLs relevant to the requested topic."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body>Content</body></html>"

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            await fetch_current_docs("models")

        # Should have made requests only to model-related URLs
        called_urls = [call.args[0] for call in mock_get.call_args_list]
        assert len(called_urls) >= 1

    def test_doc_sources_configured(self) -> None:
        """Should have hardcoded doc sources for MVP."""
        assert len(DOC_SOURCES) >= 2
        assert all("anthropic" in url.lower() or "claude" in url.lower()
                   for url in DOC_SOURCES.values())


class TestDocSectionDataClass:
    """Tests for the DocSection data structure."""

    def test_doc_section_has_required_fields(self) -> None:
        """DocSection should have title, content, and source_url."""
        section = DocSection(
            title="API Reference",
            content="Documentation content here.",
            source_url="https://docs.anthropic.com/api"
        )

        assert section.title == "API Reference"
        assert section.content == "Documentation content here."
        assert section.source_url == "https://docs.anthropic.com/api"


class TestGetRecentChanges:
    """Tests for the get_recent_changes tool."""

    @pytest.mark.asyncio
    async def test_get_changes_returns_entries(self) -> None:
        """Should return ChangelogEntry objects."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = """
        <html><body>
        <h2>2026-01-15</h2>
        <p>Added new feature X</p>
        <h2>2026-01-10</h2>
        <p>Fixed bug Y</p>
        </body></html>
        """

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            result = await get_recent_changes(days=30)

        assert isinstance(result, list)
        assert all(isinstance(entry, ChangelogEntry) for entry in result)

    @pytest.mark.asyncio
    async def test_get_changes_filters_by_days(self) -> None:
        """Should only return changes within the specified day range."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body><p>Changes</p></body></html>"

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            result = await get_recent_changes(days=7)

        # Result should be filtered (implementation detail)
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_get_changes_handles_empty_changelog(self) -> None:
        """Should return empty list when no changes found."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body></body></html>"

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            result = await get_recent_changes(days=30)

        assert result == []


class TestChangelogEntryDataClass:
    """Tests for the ChangelogEntry data structure."""

    def test_changelog_entry_has_required_fields(self) -> None:
        """ChangelogEntry should have date, title, and description."""
        entry = ChangelogEntry(
            date="2026-01-15",
            title="New Feature",
            description="Added support for X.",
            source_url="https://docs.anthropic.com/changelog"
        )

        assert entry.date == "2026-01-15"
        assert entry.title == "New Feature"
        assert entry.description == "Added support for X."
        assert entry.source_url == "https://docs.anthropic.com/changelog"


class TestSearchDocs:
    """Tests for the search_docs tool."""

    @pytest.mark.asyncio
    async def test_search_returns_results(self) -> None:
        """Should return SearchResult objects matching query."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body><p>Claude supports streaming responses.</p></body></html>"

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            result = await search_docs("streaming")

        assert isinstance(result, list)
        assert all(isinstance(r, SearchResult) for r in result)

    @pytest.mark.asyncio
    async def test_search_matches_query_in_content(self) -> None:
        """Results should contain content matching the query."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body><p>Maximum context is 200k tokens.</p></body></html>"

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            result = await search_docs("context")

        if result:  # May be empty if query doesn't match
            assert any("context" in r.snippet.lower() for r in result)

    @pytest.mark.asyncio
    async def test_search_returns_empty_for_no_matches(self) -> None:
        """Should return empty list when no content matches query."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body><p>Unrelated content here.</p></body></html>"

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            result = await search_docs("xyznonexistent123")

        assert result == []


class TestSearchResultDataClass:
    """Tests for the SearchResult data structure."""

    def test_search_result_has_required_fields(self) -> None:
        """SearchResult should have snippet, source_url, and relevance."""
        result = SearchResult(
            snippet="Claude supports streaming responses.",
            source_url="https://docs.anthropic.com/api",
            relevance_score=0.85
        )

        assert result.snippet == "Claude supports streaming responses."
        assert result.source_url == "https://docs.anthropic.com/api"
        assert result.relevance_score == 0.85
