# ABOUTME: Unit tests for the drift report generator.
# ABOUTME: Tests markdown report generation from drift results.

from datetime import datetime
from typing import List

from analyzer.report_generator import (
    generate_report,
    DriftReport,
)
from analyzer.drift_detector import DriftResult, DriftStatus


class TestGenerateReport:
    """Tests for the generate_report function."""

    def test_generate_returns_drift_report(self) -> None:
        """Should return a DriftReport object."""
        results = [
            DriftResult(
                claim_text="Claude supports 100k tokens.",
                section_title="Features",
                line_number=5,
                status=DriftStatus.OUTDATED,
                reasoning="Now supports 200k.",
                source_reference="https://docs.anthropic.com/models",
                suggested_update="Change to 200k tokens."
            )
        ]

        report = generate_report(results, "test-doc.md")

        assert isinstance(report, DriftReport)

    def test_report_includes_timestamp(self) -> None:
        """Report should include generation timestamp."""
        results = [
            DriftResult(
                claim_text="Test claim.",
                section_title="Test",
                line_number=1,
                status=DriftStatus.CURRENT,
                reasoning="All good.",
                source_reference=None,
                suggested_update=None
            )
        ]

        report = generate_report(results, "test.md")

        assert report.generated_at is not None
        # Timestamp should be recent (within last minute)
        now = datetime.now()
        diff = now - report.generated_at
        assert diff.total_seconds() < 60

    def test_report_includes_source_file(self) -> None:
        """Report should reference the analyzed source file."""
        results: List[DriftResult] = []

        report = generate_report(results, "my-training-doc.md")

        assert report.source_file == "my-training-doc.md"

    def test_report_includes_summary_counts(self) -> None:
        """Report should include counts by status."""
        results = [
            DriftResult("Claim 1", "Sec", 1, DriftStatus.CURRENT, "OK", None, None),
            DriftResult("Claim 2", "Sec", 2, DriftStatus.OUTDATED, "Old", "url", "Fix"),
            DriftResult("Claim 3", "Sec", 3, DriftStatus.OUTDATED, "Old", "url", "Fix"),
            DriftResult("Claim 4", "Sec", 4, DriftStatus.UNVERIFIABLE, "?", None, None),
        ]

        report = generate_report(results, "test.md")

        assert report.summary["current"] == 1
        assert report.summary["outdated"] == 2
        assert report.summary["unverifiable"] == 1

    def test_report_markdown_has_header(self) -> None:
        """Markdown output should have a header."""
        results: List[DriftResult] = []

        report = generate_report(results, "test.md")
        markdown = report.to_markdown()

        assert "# Drift Analysis Report" in markdown

    def test_report_markdown_has_table(self) -> None:
        """Markdown output should include results table."""
        results = [
            DriftResult(
                claim_text="Test claim about tokens.",
                section_title="Features",
                line_number=10,
                status=DriftStatus.OUTDATED,
                reasoning="Outdated info.",
                source_reference="https://example.com",
                suggested_update="Update this."
            )
        ]

        report = generate_report(results, "test.md")
        markdown = report.to_markdown()

        assert "| Section |" in markdown
        assert "| Claim |" in markdown or "Claim" in markdown
        assert "| Status |" in markdown
        assert "OUTDATED" in markdown

    def test_report_markdown_has_recommended_updates(self) -> None:
        """Markdown should include recommended updates section."""
        results = [
            DriftResult(
                claim_text="Old claim.",
                section_title="API",
                line_number=15,
                status=DriftStatus.OUTDATED,
                reasoning="Changed.",
                source_reference="https://docs.example.com",
                suggested_update="New claim text."
            )
        ]

        report = generate_report(results, "test.md")
        markdown = report.to_markdown()

        assert "Recommended Updates" in markdown or "recommended" in markdown.lower()
        assert "New claim text" in markdown

    def test_report_handles_empty_results(self) -> None:
        """Should handle empty results gracefully."""
        results: List[DriftResult] = []

        report = generate_report(results, "test.md")
        markdown = report.to_markdown()

        assert "No claims" in markdown.lower() or "0" in markdown

    def test_report_includes_line_references(self) -> None:
        """Updates should include line number references."""
        results = [
            DriftResult(
                claim_text="Outdated info.",
                section_title="Section",
                line_number=42,
                status=DriftStatus.OUTDATED,
                reasoning="Changed.",
                source_reference="https://example.com",
                suggested_update="Updated info."
            )
        ]

        report = generate_report(results, "test.md")
        markdown = report.to_markdown()

        assert "42" in markdown or "Line 42" in markdown


class TestDriftReportDataClass:
    """Tests for the DriftReport data structure."""

    def test_drift_report_has_required_fields(self) -> None:
        """DriftReport should have all required fields."""
        report = DriftReport(
            source_file="test.md",
            generated_at=datetime.now(),
            results=[],
            summary={"current": 0, "outdated": 0, "potentially_stale": 0, "unverifiable": 0}
        )

        assert report.source_file == "test.md"
        assert report.generated_at is not None
        assert report.results == []
        assert isinstance(report.summary, dict)

    def test_drift_report_to_markdown_returns_string(self) -> None:
        """to_markdown should return a string."""
        report = DriftReport(
            source_file="test.md",
            generated_at=datetime.now(),
            results=[],
            summary={"current": 0, "outdated": 0, "potentially_stale": 0, "unverifiable": 0}
        )

        markdown = report.to_markdown()

        assert isinstance(markdown, str)
        assert len(markdown) > 0
