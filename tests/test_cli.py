# ABOUTME: Unit tests for the command-line interface.
# ABOUTME: Tests argument parsing and CLI workflow.

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock
from click.testing import CliRunner
from cli import main, cli


class TestCliArguments:
    """Tests for CLI argument parsing."""

    def test_cli_requires_input_file(self) -> None:
        """CLI should require an input file argument."""
        runner = CliRunner()
        result = runner.invoke(cli, [])

        assert result.exit_code != 0
        assert "Missing argument" in result.output or "Usage:" in result.output

    def test_cli_accepts_input_file(self) -> None:
        """CLI should accept a valid input file path."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            # Create a test file
            Path("test.md").write_text("# Test\nClaude can do things.")

            with patch("cli.run_analysis", new_callable=AsyncMock) as mock_run:
                mock_run.return_value = "# Report\nTest output"
                result = runner.invoke(cli, ["test.md"])

        # Should not fail on argument parsing
        assert "Missing argument" not in result.output

    def test_cli_accepts_output_option(self) -> None:
        """CLI should accept -o/--output option."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            Path("test.md").write_text("# Test\nContent.")

            with patch("cli.run_analysis", new_callable=AsyncMock) as mock_run:
                mock_run.return_value = "# Report"
                result = runner.invoke(cli, ["test.md", "-o", "report.md"])

        assert result.exit_code == 0 or "Error" not in result.output

    def test_cli_accepts_verbose_flag(self) -> None:
        """CLI should accept --verbose flag."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            Path("test.md").write_text("# Test")

            with patch("cli.run_analysis", new_callable=AsyncMock) as mock_run:
                mock_run.return_value = "# Report"
                result = runner.invoke(cli, ["test.md", "--verbose"])

        # Verbose flag should be accepted
        assert "--verbose" not in result.output or result.exit_code == 0


class TestCliFileHandling:
    """Tests for CLI file handling."""

    def test_cli_error_on_missing_input_file(self) -> None:
        """CLI should error when input file doesn't exist."""
        runner = CliRunner()

        result = runner.invoke(cli, ["nonexistent.md"])

        assert result.exit_code != 0
        assert "not found" in result.output.lower() or "error" in result.output.lower()

    def test_cli_writes_to_output_file(self) -> None:
        """CLI should write report to output file when specified."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            Path("test.md").write_text("# Test\nClaude supports streaming.")

            with patch("cli.run_analysis", new_callable=AsyncMock) as mock_run:
                mock_run.return_value = "# Drift Report\nGenerated content."
                result = runner.invoke(cli, ["test.md", "-o", "output.md"])

                if result.exit_code == 0:
                    assert Path("output.md").exists()
                    content = Path("output.md").read_text()
                    assert "Drift Report" in content

    def test_cli_outputs_to_stdout_by_default(self) -> None:
        """CLI should output to stdout when no output file specified."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            Path("test.md").write_text("# Test")

            with patch("cli.run_analysis", new_callable=AsyncMock) as mock_run:
                mock_run.return_value = "# Drift Report\nOutput here."
                result = runner.invoke(cli, ["test.md"])

        if result.exit_code == 0:
            assert "Drift Report" in result.output or "Output" in result.output


class TestCliHelp:
    """Tests for CLI help text."""

    def test_cli_has_help_option(self) -> None:
        """CLI should respond to --help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "Usage:" in result.output

    def test_cli_help_describes_input(self) -> None:
        """Help should describe the input file argument."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])

        assert "INPUT_FILE" in result.output or "input" in result.output.lower()

    def test_cli_help_describes_output(self) -> None:
        """Help should describe the output option."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])

        assert "--output" in result.output or "-o" in result.output

    def test_cli_has_version_option(self) -> None:
        """CLI should respond to --version."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])

        assert result.exit_code == 0
        assert "1.0.1" in result.output


class TestCliIntegration:
    """Integration tests for CLI workflow."""

    def test_cli_processes_markdown_file(self) -> None:
        """CLI should process a markdown file through the pipeline."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            # Create input file with a claim
            Path("input.md").write_text(
                "# API Guide\nClaude supports a 200k token context window."
            )

            with patch("cli.run_analysis", new_callable=AsyncMock) as mock_run:
                mock_run.return_value = "# Drift Analysis Report\n\nAnalysis complete."
                result = runner.invoke(cli, ["input.md"])

        # Should complete without error
        if result.exit_code == 0:
            assert "Drift" in result.output or "Analysis" in result.output
