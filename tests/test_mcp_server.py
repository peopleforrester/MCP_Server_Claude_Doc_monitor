# ABOUTME: Tests for the FastMCP server wiring — tools, resources, and entry point.
# ABOUTME: Verifies registration and invocation without starting a real transport.

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_server.server import mcp


@pytest.mark.asyncio
async def test_mcp_server_name() -> None:
    """Server must identify itself so clients show a useful name."""
    assert mcp.name == "DocMonitor"


@pytest.mark.asyncio
async def test_mcp_server_registers_expected_tools() -> None:
    """The three core tools must be registered under stable names."""
    tools = await mcp.list_tools()
    names = {t.name for t in tools}
    assert {"check_drift", "search_docs", "get_changelog"}.issubset(names)


@pytest.mark.asyncio
async def test_check_drift_tool_describes_input() -> None:
    """check_drift must take a markdown string input — surfaced to the LLM."""
    tools = await mcp.list_tools()
    check_drift = next(t for t in tools if t.name == "check_drift")
    schema_props = check_drift.inputSchema.get("properties", {})
    assert "markdown" in schema_props


@pytest.mark.asyncio
async def test_search_docs_tool_describes_input() -> None:
    """search_docs must take a query string."""
    tools = await mcp.list_tools()
    search = next(t for t in tools if t.name == "search_docs")
    schema_props = search.inputSchema.get("properties", {})
    assert "query" in schema_props


@pytest.mark.asyncio
async def test_get_changelog_tool_describes_days() -> None:
    """get_changelog must accept a days lookback."""
    tools = await mcp.list_tools()
    changelog = next(t for t in tools if t.name == "get_changelog")
    schema_props = changelog.inputSchema.get("properties", {})
    assert "days" in schema_props


@pytest.mark.asyncio
async def test_docs_resource_registered() -> None:
    """docs://{topic} must be registered as a resource template."""
    templates = await mcp.list_resource_templates()
    uris = {str(t.uriTemplate) for t in templates}
    assert any("docs://" in uri for uri in uris)


@pytest.mark.asyncio
async def test_check_drift_calls_analysis_pipeline() -> None:
    """check_drift tool must route through the extraction + analysis pipeline."""
    from mcp_server import server as server_module

    fake_docs = [MagicMock(title="D", content="c", source_url="https://x")]
    fake_result = MagicMock(
        claim_text="c",
        section_title="s",
        line_number=1,
        status=MagicMock(value="CURRENT"),
        reasoning="ok",
        source_reference=None,
        suggested_update=None,
        evidence=[],
    )

    with patch.object(server_module, "parse_sections", return_value=[MagicMock()]), \
         patch.object(server_module, "extract_claims_with_llm", new=AsyncMock(return_value=[MagicMock(text="c", section_title="s", line_number=1)])), \
         patch.object(server_module, "_fetch_all_docs", new=AsyncMock(return_value=fake_docs)), \
         patch.object(server_module, "analyze_claims_batch", new=AsyncMock(return_value=[fake_result])):

        result = await server_module.check_drift_impl("# Test\nClaude can stream.")

    assert result["summary"]["total"] == 1
    assert len(result["claims"]) == 1
    assert result["claims"][0]["status"] == "CURRENT"
