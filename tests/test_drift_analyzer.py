# ABOUTME: Unit tests for the drift analyzer module.
# ABOUTME: Tests Claude-powered claim comparison and classification.

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from anthropic.types import TextBlock
from analyzer.drift_detector import (
    analyze_claim,
    DriftResult,
    DriftStatus,
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
