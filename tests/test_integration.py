# ABOUTME: Integration tests for the content freshness pipeline.
# ABOUTME: Tests the full analysis workflow with transport-level HTTP mocking.

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

import httpx
from anthropic.types import TextBlock
from click.testing import CliRunner

from cli import cli


def _make_html_page(content: str) -> str:
    """Create a minimal HTML page wrapping the given text content."""
    return f"<html><head><title>Test Doc</title></head><body><p>{content}</p></body></html>"


def _make_claude_response(status: str, reasoning: str,
                          source_ref: str = "https://docs.anthropic.com/test",
                          suggested_update: str = None) -> MagicMock:
    """Create a mock Claude API response with proper TextBlock spec."""
    response_json = json.dumps({
        "status": status,
        "reasoning": reasoning,
        "source_reference": source_ref,
        "suggested_update": suggested_update,
    })
    mock_message = MagicMock()
    mock_message.content = [MagicMock(spec=TextBlock, text=response_json)]
    return mock_message


class TestPipelineIntegration:
    """Integration tests that exercise the full analysis pipeline.

    These tests mock HTTP at the transport level (httpx responses)
    and the Claude API, but let the real parsing, extraction, and
    report generation code run end-to-end.

    Note: These are sync tests because Click's CliRunner calls the sync
    cli() function, which internally uses asyncio.run(). Using async
    tests would conflict with the nested event loop.
    """

    def test_full_pipeline_produces_report(self, tmp_path: Path) -> None:
        """Full pipeline should parse input, fetch docs, analyze, and generate report."""
        # Create a training document with a claim
        input_file = tmp_path / "training.md"
        input_file.write_text(
            "# Claude Features\n"
            "Claude supports a 200k token context window.\n"
        )

        # Create a minimal config with one doc source
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({
            "doc_sources": {
                "models": "https://docs.anthropic.com/en/docs/about-claude/models"
            }
        }))

        # Mock httpx to return a doc page
        mock_http_response = MagicMock()
        mock_http_response.status_code = 200
        mock_http_response.text = _make_html_page(
            "Claude has a 200,000 token context window for all models."
        )
        mock_http_response.raise_for_status = MagicMock()

        # Mock Claude API to return analysis
        mock_claude_response = _make_claude_response(
            status="CURRENT",
            reasoning="The claim matches current documentation.",
            source_ref="https://docs.anthropic.com/en/docs/about-claude/models",
        )

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock,
                    return_value=mock_http_response), \
             patch("anthropic.AsyncAnthropic") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_claude_response)
            mock_client_class.return_value = mock_client

            runner = CliRunner()
            result = runner.invoke(cli, [
                str(input_file), "-c", str(config_file), "-v"
            ])

        assert result.exit_code == 0, f"CLI failed with output: {result.output}"
        assert "Drift Analysis Report" in result.output

    def test_pipeline_handles_outdated_claim(self, tmp_path: Path) -> None:
        """Pipeline should detect and report outdated claims."""
        input_file = tmp_path / "training.md"
        input_file.write_text(
            "# API Limits\n"
            "The maximum context window is 100k tokens.\n"
        )

        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({
            "doc_sources": {
                "models": "https://docs.anthropic.com/en/docs/about-claude/models"
            }
        }))

        mock_http_response = MagicMock()
        mock_http_response.status_code = 200
        mock_http_response.text = _make_html_page(
            "Claude now supports a 200k token context window."
        )
        mock_http_response.raise_for_status = MagicMock()

        mock_claude_response = _make_claude_response(
            status="OUTDATED",
            reasoning="Context window has increased from 100k to 200k.",
            suggested_update="Update to 200k tokens.",
        )

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock,
                    return_value=mock_http_response), \
             patch("anthropic.AsyncAnthropic") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_claude_response)
            mock_client_class.return_value = mock_client

            runner = CliRunner()
            result = runner.invoke(cli, [str(input_file), "-c", str(config_file)])

        assert result.exit_code == 0, f"CLI failed with output: {result.output}"
        assert "OUTDATED" in result.output

    def test_pipeline_writes_output_file(self, tmp_path: Path) -> None:
        """Pipeline should write report to output file when -o is specified."""
        input_file = tmp_path / "training.md"
        input_file.write_text(
            "# Features\n"
            "Claude can process images and generate descriptions.\n"
        )
        output_file = tmp_path / "report.md"

        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({
            "doc_sources": {
                "vision": "https://docs.anthropic.com/en/docs/build-with-claude/vision"
            }
        }))

        mock_http_response = MagicMock()
        mock_http_response.status_code = 200
        mock_http_response.text = _make_html_page(
            "Claude has vision capabilities for analyzing images."
        )
        mock_http_response.raise_for_status = MagicMock()

        mock_claude_response = _make_claude_response(
            status="CURRENT",
            reasoning="Vision capability is confirmed.",
        )

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock,
                    return_value=mock_http_response), \
             patch("anthropic.AsyncAnthropic") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_claude_response)
            mock_client_class.return_value = mock_client

            runner = CliRunner()
            result = runner.invoke(cli, [
                str(input_file), "-o", str(output_file), "-c", str(config_file)
            ])

        assert result.exit_code == 0, f"CLI failed with output: {result.output}"
        assert output_file.exists()
        report_content = output_file.read_text()
        assert "Drift Analysis Report" in report_content

    def test_pipeline_with_no_claims(self, tmp_path: Path) -> None:
        """Pipeline should handle documents with no extractable claims."""
        input_file = tmp_path / "training.md"
        input_file.write_text(
            "# Introduction\n"
            "This is a general overview document with no specific claims.\n"
            "It contains background information only.\n"
        )

        runner = CliRunner()
        result = runner.invoke(cli, [str(input_file)])

        assert result.exit_code == 0
        # Should still produce a report (empty analysis)
        assert "Drift Analysis Report" in result.output or "Report" in result.output

    def test_pipeline_handles_http_failure(self, tmp_path: Path) -> None:
        """Pipeline should handle HTTP errors when fetching docs."""
        input_file = tmp_path / "training.md"
        input_file.write_text(
            "# Features\n"
            "Claude supports streaming responses.\n"
        )

        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({
            "doc_sources": {
                "streaming": "https://docs.anthropic.com/en/docs/build-with-claude/streaming"
            }
        }))

        # Simulate HTTP failure
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock,
                    side_effect=httpx.HTTPError("Connection failed")):
            runner = CliRunner()
            result = runner.invoke(cli, [str(input_file), "-c", str(config_file), "-v"])

        # Should exit with error since no docs could be fetched
        assert result.exit_code != 0
