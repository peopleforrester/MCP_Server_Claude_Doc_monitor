# ABOUTME: E2E tests that analyze a claim with the real Claude API and live docs.
# ABOUTME: Needs network access and ANTHROPIC_API_KEY; each test makes one small call.

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from analyzer.drift_detector import DriftStatus, analyze_claim
from analyzer.input_handler import Claim
from cli import cli
from config import get_doc_sources
from mcp_server.tools.fetch_docs import fetch_current_docs

# Phrased so the --fast regex extractor picks it up as a capability claim.
CLAIM = "Claude supports a 200k token context window."


async def test_live_claim_analysis_returns_result(anthropic_api_key: str) -> None:
    """A claim checked against a live doc page should get a valid drift result."""
    docs = await fetch_current_docs("context-windows")
    claim = Claim(text=CLAIM, section_title="Context", line_number=2)

    result = await analyze_claim(claim, docs)

    assert result.claim_text == CLAIM
    assert isinstance(result.status, DriftStatus)
    assert result.reasoning


def test_live_cli_pipeline_reports_claim(
    anthropic_api_key: str, tmp_path: Path
) -> None:
    """The CLI should fetch, analyze and report a claim end to end."""
    input_file = tmp_path / "training.md"
    input_file.write_text(f"# Context\n{CLAIM}\n")
    config_file = tmp_path / "config.json"
    config_file.write_text(
        json.dumps(
            {
                "doc_sources": {
                    "context-windows": get_doc_sources()["context-windows"]
                },
            }
        )
    )

    result = CliRunner().invoke(
        cli,
        [
            str(input_file),
            "-c",
            str(config_file),
            "--fast",
            "--skip-changelog",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Drift Analysis Report" in result.output
    # The claim only appears in the report if its analysis succeeded.
    assert CLAIM[:60] in result.output
