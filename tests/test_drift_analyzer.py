# ABOUTME: Unit tests for the drift analyzer module.
# ABOUTME: Tests Claude-powered claim comparison and classification.

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from anthropic.types import TextBlock
from analyzer.drift_detector import (
    analyze_claim,
    CitedEvidence,
    DriftResult,
    DriftStatus,
    _build_document_blocks,
    _chunk_content,
)
from analyzer.input_handler import Claim
from mcp_server.tools.fetch_docs import DocSection


class TestAnalyzeClaim:
    """Tests for the analyze_claim function."""

    @pytest.mark.asyncio
    async def test_analyze_returns_drift_result(self) -> None:
        """Should return a DriftResult object."""
        claim = Claim(
            text="Claude supports 100k token context.",
            section_title="Features",
            line_number=5
        )
        docs = [DocSection(
            title="Models",
            content="Claude supports 200k token context window.",
            source_url="https://docs.anthropic.com/models"
        )]

        mock_message = MagicMock()
        mock_message.content = [MagicMock(spec=TextBlock, text="""
{
    "status": "OUTDATED",
    "reasoning": "The claim states 100k tokens but current docs show 200k.",
    "source_reference": "https://docs.anthropic.com/models",
    "suggested_update": "Update to 200k tokens."
}
""")]

        with patch("anthropic.AsyncAnthropic") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_message)
            mock_client_class.return_value = mock_client

            result = await analyze_claim(claim, docs)

        assert isinstance(result, DriftResult)

    @pytest.mark.asyncio
    async def test_analyze_classifies_outdated(self) -> None:
        """Should classify outdated claims correctly."""
        claim = Claim(
            text="Maximum context is 100k tokens.",
            section_title="Limits",
            line_number=10
        )
        docs = [DocSection(
            title="Models",
            content="Claude now supports a 200k token context window.",
            source_url="https://docs.anthropic.com/models"
        )]

        mock_message = MagicMock()
        mock_message.content = [MagicMock(spec=TextBlock, text="""
{
    "status": "OUTDATED",
    "reasoning": "Context window has increased from 100k to 200k.",
    "source_reference": "https://docs.anthropic.com/models",
    "suggested_update": "Change 100k to 200k tokens."
}
""")]

        with patch("anthropic.AsyncAnthropic") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_message)
            mock_client_class.return_value = mock_client

            result = await analyze_claim(claim, docs)

        assert result.status == DriftStatus.OUTDATED

    @pytest.mark.asyncio
    async def test_analyze_classifies_current(self) -> None:
        """Should classify current claims correctly."""
        claim = Claim(
            text="Use the system parameter for system prompts.",
            section_title="API",
            line_number=5
        )
        docs = [DocSection(
            title="API Reference",
            content="Use the system parameter to set your system prompt.",
            source_url="https://docs.anthropic.com/api"
        )]

        mock_message = MagicMock()
        mock_message.content = [MagicMock(spec=TextBlock, text="""
{
    "status": "CURRENT",
    "reasoning": "The claim matches current documentation.",
    "source_reference": "https://docs.anthropic.com/api",
    "suggested_update": null
}
""")]

        with patch("anthropic.AsyncAnthropic") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_message)
            mock_client_class.return_value = mock_client

            result = await analyze_claim(claim, docs)

        assert result.status == DriftStatus.CURRENT

    @pytest.mark.asyncio
    async def test_analyze_classifies_unverifiable(self) -> None:
        """Should classify unverifiable claims when no docs match."""
        claim = Claim(
            text="Claude has a secret feature X.",
            section_title="Features",
            line_number=15
        )
        docs = [DocSection(
            title="Features",
            content="Claude supports vision and code analysis.",
            source_url="https://docs.anthropic.com/features"
        )]

        mock_message = MagicMock()
        mock_message.content = [MagicMock(spec=TextBlock, text="""
{
    "status": "UNVERIFIABLE",
    "reasoning": "Cannot find documentation about feature X.",
    "source_reference": null,
    "suggested_update": null
}
""")]

        with patch("anthropic.AsyncAnthropic") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_message)
            mock_client_class.return_value = mock_client

            result = await analyze_claim(claim, docs)

        assert result.status == DriftStatus.UNVERIFIABLE

    @pytest.mark.asyncio
    async def test_analyze_includes_reasoning(self) -> None:
        """Result should include reasoning for the classification."""
        claim = Claim(
            text="Claude can process images.",
            section_title="Vision",
            line_number=20
        )
        docs = [DocSection(
            title="Vision",
            content="Claude has vision capabilities for image analysis.",
            source_url="https://docs.anthropic.com/vision"
        )]

        mock_message = MagicMock()
        mock_message.content = [MagicMock(spec=TextBlock, text="""
{
    "status": "CURRENT",
    "reasoning": "Vision capability is confirmed in documentation.",
    "source_reference": "https://docs.anthropic.com/vision",
    "suggested_update": null
}
""")]

        with patch("anthropic.AsyncAnthropic") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_message)
            mock_client_class.return_value = mock_client

            result = await analyze_claim(claim, docs)

        assert result.reasoning
        assert len(result.reasoning) > 0

    @pytest.mark.asyncio
    async def test_analyze_includes_source_reference(self) -> None:
        """Result should include source reference when available."""
        claim = Claim(
            text="Rate limit is 60 requests per minute.",
            section_title="Limits",
            line_number=25
        )
        docs = [DocSection(
            title="Rate Limits",
            content="API rate limit is 60 requests per minute.",
            source_url="https://docs.anthropic.com/rate-limits"
        )]

        mock_message = MagicMock()
        mock_message.content = [MagicMock(spec=TextBlock, text="""
{
    "status": "CURRENT",
    "reasoning": "Rate limit matches documentation.",
    "source_reference": "https://docs.anthropic.com/rate-limits",
    "suggested_update": null
}
""")]

        with patch("anthropic.AsyncAnthropic") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_message)
            mock_client_class.return_value = mock_client

            result = await analyze_claim(claim, docs)

        assert result.source_reference is not None

    @pytest.mark.asyncio
    async def test_analyze_handles_api_error(self) -> None:
        """Should raise exception on API errors."""
        claim = Claim(
            text="Test claim.",
            section_title="Test",
            line_number=1
        )
        docs = [DocSection(
            title="Test",
            content="Test content.",
            source_url="https://example.com"
        )]

        with patch("anthropic.AsyncAnthropic") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(
                side_effect=Exception("API error")
            )
            mock_client_class.return_value = mock_client

            with pytest.raises(Exception):
                await analyze_claim(claim, docs)


class TestDriftResultDataClass:
    """Tests for the DriftResult data structure."""

    def test_drift_result_has_required_fields(self) -> None:
        """DriftResult should have all required fields."""
        result = DriftResult(
            claim_text="Test claim",
            section_title="Test Section",
            line_number=10,
            status=DriftStatus.OUTDATED,
            reasoning="The claim is outdated.",
            source_reference="https://example.com",
            suggested_update="Update the claim."
        )

        assert result.claim_text == "Test claim"
        assert result.section_title == "Test Section"
        assert result.line_number == 10
        assert result.status == DriftStatus.OUTDATED
        assert result.reasoning == "The claim is outdated."
        assert result.source_reference == "https://example.com"
        assert result.suggested_update == "Update the claim."


class TestDriftStatus:
    """Tests for the DriftStatus enum."""

    def test_drift_status_values(self) -> None:
        """DriftStatus should have all expected values."""
        assert DriftStatus.CURRENT.value == "CURRENT"
        assert DriftStatus.POTENTIALLY_STALE.value == "POTENTIALLY_STALE"
        assert DriftStatus.OUTDATED.value == "OUTDATED"
        assert DriftStatus.UNVERIFIABLE.value == "UNVERIFIABLE"


class TestDocumentBlocks:
    """Tests for the Citations-API document block builder."""

    def test_build_document_blocks_enables_citations(self) -> None:
        """Every document block must have citations.enabled=true."""
        docs = [
            DocSection(title="Doc A", content="Alpha.", source_url="https://x/a"),
            DocSection(title="Doc B", content="Bravo.", source_url="https://x/b"),
        ]
        blocks = _build_document_blocks(docs)

        assert len(blocks) == 2
        for block in blocks:
            assert block["type"] == "document"
            assert block["source"]["type"] == "text"
            assert block["source"]["media_type"] == "text/plain"
            assert block["citations"] == {"enabled": True}
            assert "title" in block

    def test_build_document_blocks_preserves_titles_and_urls(self) -> None:
        """Block metadata must map back to source docs for citation lookup."""
        docs = [DocSection(title="Models", content="Body.", source_url="https://x/models")]
        blocks = _build_document_blocks(docs)

        assert blocks[0]["title"] == "Models"
        assert blocks[0]["context"] == "https://x/models"

    def test_chunk_content_preserves_small_docs(self) -> None:
        """Docs under the chunk ceiling must produce a single chunk."""
        chunks = _chunk_content("short doc", max_chars=1000)
        assert chunks == ["short doc"]

    def test_chunk_content_splits_large_docs(self) -> None:
        """Docs over the chunk ceiling must split, preserving paragraph boundaries."""
        big = ("paragraph one.\n\n" * 500) + ("paragraph two.\n\n" * 500)
        chunks = _chunk_content(big, max_chars=8000)

        assert len(chunks) > 1
        assert all(len(c) <= 8000 for c in chunks)
        assert "".join(chunks).replace("\n\n", "\n\n") == big or sum(len(c) for c in chunks) >= len(big) - 10

    def test_large_doc_produces_multiple_document_blocks(self) -> None:
        """A single large DocSection must expand into multiple document blocks."""
        big_content = ("This is a paragraph.\n\n" * 5000)  # ~100KB
        docs = [DocSection(title="Big", content=big_content, source_url="https://x/big")]

        blocks = _build_document_blocks(docs)

        assert len(blocks) > 1
        # Every chunk must carry the same title + url for provenance
        assert all(b["title"].startswith("Big") for b in blocks)
        assert all(b["context"] == "https://x/big" for b in blocks)


class TestPromptCaching:
    """Tests that cache_control is applied to keep cost low across claims."""

    @pytest.mark.asyncio
    async def test_system_prompt_is_cached(self) -> None:
        """System prompt must be passed as a block list with 1h ephemeral cache_control."""
        claim = Claim(text="x", section_title="s", line_number=1)
        docs = [DocSection(title="T", content="c", source_url="https://x")]

        text_block = MagicMock(spec=TextBlock)
        text_block.text = '{"status": "CURRENT", "reasoning": "r", "source_reference": null, "suggested_update": null}'
        text_block.citations = None
        mock_message = MagicMock()
        mock_message.content = [text_block]

        with patch("anthropic.AsyncAnthropic") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_message)
            mock_client_class.return_value = mock_client

            await analyze_claim(claim, docs)

        kwargs = mock_client.messages.create.await_args.kwargs
        system = kwargs["system"]
        assert isinstance(system, list)
        assert system[-1]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}

    @pytest.mark.asyncio
    async def test_last_document_block_is_cached(self) -> None:
        """cache_control on the final doc block makes the whole corpus a single cacheable span."""
        claim = Claim(text="x", section_title="s", line_number=1)
        docs = [
            DocSection(title="A", content="alpha", source_url="https://x/a"),
            DocSection(title="B", content="bravo", source_url="https://x/b"),
        ]

        text_block = MagicMock(spec=TextBlock)
        text_block.text = '{"status": "CURRENT", "reasoning": "r", "source_reference": null, "suggested_update": null}'
        text_block.citations = None
        mock_message = MagicMock()
        mock_message.content = [text_block]

        with patch("anthropic.AsyncAnthropic") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_message)
            mock_client_class.return_value = mock_client

            await analyze_claim(claim, docs)

        kwargs = mock_client.messages.create.await_args.kwargs
        user_content = kwargs["messages"][0]["content"]
        doc_blocks = [b for b in user_content if b.get("type") == "document"]
        # Only the last doc block carries cache_control
        assert "cache_control" not in doc_blocks[0]
        assert doc_blocks[-1]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}


class TestCitationExtraction:
    """Tests for parsing citations from Anthropic responses."""

    @pytest.mark.asyncio
    async def test_analyze_captures_cited_evidence(self) -> None:
        """Citations on response text blocks must populate DriftResult.evidence."""
        claim = Claim(text="Context is 100k.", section_title="Limits", line_number=1)
        docs = [DocSection(title="Models", content="Context is 200k.", source_url="https://x/m")]

        # Build a response text block with a citation attached
        text_block_with_cite = MagicMock(spec=TextBlock)
        text_block_with_cite.text = (
            '{"status": "OUTDATED", "reasoning": "Docs say 200k.",'
            ' "source_reference": "https://x/m", "suggested_update": "200k"}'
        )
        citation = MagicMock()
        citation.type = "char_location"
        citation.cited_text = "Context is 200k."
        citation.document_title = "Models"
        citation.document_index = 0
        citation.start_char_index = 0
        citation.end_char_index = 16
        text_block_with_cite.citations = [citation]

        mock_message = MagicMock()
        mock_message.content = [text_block_with_cite]

        with patch("anthropic.AsyncAnthropic") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_message)
            mock_client_class.return_value = mock_client

            result = await analyze_claim(claim, docs)

        assert len(result.evidence) == 1
        ev = result.evidence[0]
        assert isinstance(ev, CitedEvidence)
        assert ev.cited_text == "Context is 200k."
        assert ev.document_title == "Models"
        assert ev.document_url == "https://x/m"
        assert ev.char_range == (0, 16)

    @pytest.mark.asyncio
    async def test_analyze_no_citations_returns_empty_evidence(self) -> None:
        """Response without citations must produce empty evidence list (not crash)."""
        claim = Claim(text="x", section_title="s", line_number=1)
        docs = [DocSection(title="T", content="c", source_url="https://x")]

        text_block = MagicMock(spec=TextBlock)
        text_block.text = (
            '{"status": "UNVERIFIABLE", "reasoning": "n/a",'
            ' "source_reference": null, "suggested_update": null}'
        )
        text_block.citations = None  # SDK sets to None when citations disabled

        mock_message = MagicMock()
        mock_message.content = [text_block]

        with patch("anthropic.AsyncAnthropic") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_message)
            mock_client_class.return_value = mock_client

            result = await analyze_claim(claim, docs)

        assert result.evidence == []
