# ABOUTME: Unit tests for the drift report generator.
# ABOUTME: Tests markdown report generation from drift results.

from __future__ import annotations

from datetime import datetime

from analyzer.report_generator import (
    generate_report,
    DriftReport,
)
from analyzer.changelog_analyzer import ChangelogImpact
from analyzer.drift_detector import CitedEvidence, DriftResult, DriftStatus


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
        results: list[DriftResult] = []

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
        results: list[DriftResult] = []

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
        results: list[DriftResult] = []

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


class TestCitationRendering:
    """Tests that CitedEvidence renders into the report for flagged claims."""

    def test_outdated_claim_renders_evidence_blockquote(self) -> None:
        """Outdated claims with evidence must show the cited text as a blockquote."""
        evidence = [
            CitedEvidence(
                cited_text="Claude supports a 200,000 token context window.",
                document_title="Models Overview",
                document_url="https://platform.claude.com/docs/models",
                char_range=(42, 90),
            )
        ]
        results = [
            DriftResult(
                claim_text="Context is 100k tokens.",
                section_title="Limits",
                line_number=5,
                status=DriftStatus.OUTDATED,
                reasoning="The docs say 200k.",
                source_reference="https://platform.claude.com/docs/models",
                suggested_update="Context is 200k tokens.",
                evidence=evidence,
            )
        ]

        markdown = generate_report(results, "test.md").to_markdown()

        # Blockquote-prefixed cited text
        assert "> Claude supports a 200,000 token context window." in markdown
        # Title and URL visible for provenance
        assert "Models Overview" in markdown
        assert "https://platform.claude.com/docs/models" in markdown

    def test_missing_evidence_omits_citation_section(self) -> None:
        """Claims without evidence should not emit a stray Evidence header."""
        results = [
            DriftResult(
                claim_text="A claim.",
                section_title="S",
                line_number=1,
                status=DriftStatus.OUTDATED,
                reasoning="r",
                source_reference=None,
                suggested_update="fix",
                evidence=[],
            )
        ]
        markdown = generate_report(results, "test.md").to_markdown()
        assert "Evidence" not in markdown


class TestChangelogImpactRendering:
    """Tests that ChangelogImpact entries surface prominently in the report."""

    def test_impacts_render_sorted_by_severity(self) -> None:
        """HIGH severity impacts must come before MEDIUM, then LOW."""
        impacts = [
            ChangelogImpact(
                claim_index=1, entry_index=0, severity="LOW",
                explanation="tangentially related",
                claim_text="Low claim", entry_title="Pricing update",
                entry_date="2026-04-01", entry_url="https://x/1",
            ),
            ChangelogImpact(
                claim_index=0, entry_index=1, severity="HIGH",
                explanation="feature retired",
                claim_text="High claim", entry_title="Model retired",
                entry_date="2026-04-19", entry_url="https://x/2",
            ),
        ]
        report = generate_report([], "test.md", changelog_impacts=impacts)
        markdown = report.to_markdown()

        assert "Recent Changelog Impact" in markdown
        # HIGH appears before LOW in rendered order
        high_pos = markdown.find("[HIGH]")
        low_pos = markdown.find("[LOW]")
        assert high_pos != -1 and low_pos != -1
        assert high_pos < low_pos
        # Source URLs included for provenance
        assert "https://x/1" in markdown
        assert "https://x/2" in markdown

    def test_empty_impacts_omits_section(self) -> None:
        """No impacts → no Recent Changelog Impact section in report."""
        results = [
            DriftResult(
                claim_text="c", section_title="s", line_number=1,
                status=DriftStatus.CURRENT, reasoning="r",
                source_reference=None, suggested_update=None,
            )
        ]
        markdown = generate_report(results, "test.md", changelog_impacts=[]).to_markdown()
        assert "Recent Changelog Impact" not in markdown
