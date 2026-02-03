# ABOUTME: Report generator for drift analysis results.
# ABOUTME: Produces markdown reports with status summaries and recommendations.

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List

from analyzer.drift_detector import DriftResult, DriftStatus


@dataclass
class DriftReport:
    """Complete drift analysis report."""

    source_file: str
    generated_at: datetime
    results: List[DriftResult]
    summary: Dict[str, int]

    def to_markdown(self) -> str:
        """Convert report to markdown format."""
        lines = []

        # Header
        lines.append("# Drift Analysis Report")
        lines.append("")
        lines.append(f"**Source File:** {self.source_file}")
        lines.append(f"**Generated:** {self.generated_at.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        # Summary
        lines.append("## Summary")
        lines.append("")
        total = sum(self.summary.values())
        lines.append(f"Total claims analyzed: **{total}**")
        lines.append("")
        lines.append(f"- Current: {self.summary.get('current', 0)}")
        lines.append(f"- Potentially Stale: {self.summary.get('potentially_stale', 0)}")
        lines.append(f"- Outdated: {self.summary.get('outdated', 0)}")
        lines.append(f"- Unverifiable: {self.summary.get('unverifiable', 0)}")
        lines.append("")

        if not self.results:
            lines.append("*No claims were analyzed.*")
            return "\n".join(lines)

        # Results table
        lines.append("## Analysis Results")
        lines.append("")
        lines.append("| Section | Claim | Status | Notes |")
        lines.append("|---------|-------|--------|-------|")

        for result in self.results:
            # Truncate long claims for table display
            claim_display = result.claim_text[:60]
            if len(result.claim_text) > 60:
                claim_display += "..."

            # Escape pipe characters in content
            claim_display = claim_display.replace("|", "\\|")
            reasoning = result.reasoning.replace("|", "\\|")[:80]

            lines.append(
                f"| {result.section_title} | {claim_display} | "
                f"{result.status.value} | {reasoning} |"
            )

        lines.append("")

        # Recommended updates section
        outdated_results = [r for r in self.results if r.status == DriftStatus.OUTDATED]
        if outdated_results:
            lines.append("## Recommended Updates")
            lines.append("")

            for i, result in enumerate(outdated_results, 1):
                lines.append(f"### {i}. Line {result.line_number}: {result.section_title}")
                lines.append("")
                lines.append(f"**Current claim:** {result.claim_text}")
                lines.append("")
                if result.suggested_update:
                    lines.append(f"**Suggested update:** {result.suggested_update}")
                    lines.append("")
                if result.source_reference:
                    lines.append(f"**Reference:** {result.source_reference}")
                    lines.append("")

        # Potentially stale section
        stale_results = [
            r for r in self.results
            if r.status == DriftStatus.POTENTIALLY_STALE
        ]
        if stale_results:
            lines.append("## Potentially Stale (Manual Review Recommended)")
            lines.append("")
            for result in stale_results:
                lines.append(f"- Line {result.line_number}: {result.claim_text[:80]}")
            lines.append("")

        # Unverifiable section
        unverifiable_results = [
            r for r in self.results
            if r.status == DriftStatus.UNVERIFIABLE
        ]
        if unverifiable_results:
            lines.append("## Unverifiable Claims")
            lines.append("")
            lines.append("*These claims could not be verified against current documentation:*")
            lines.append("")
            for result in unverifiable_results:
                lines.append(f"- Line {result.line_number}: {result.claim_text[:80]}")
            lines.append("")

        return "\n".join(lines)


def generate_report(
    results: List[DriftResult],
    source_file: str
) -> DriftReport:
    """
    Generate a drift report from analysis results.

    Args:
        results: List of DriftResult objects from analysis.
        source_file: Name of the source file that was analyzed.

    Returns:
        DriftReport containing summary and formatted output.
    """
    # Calculate summary counts
    summary = {
        "current": 0,
        "potentially_stale": 0,
        "outdated": 0,
        "unverifiable": 0
    }

    for result in results:
        if result.status == DriftStatus.CURRENT:
            summary["current"] += 1
        elif result.status == DriftStatus.POTENTIALLY_STALE:
            summary["potentially_stale"] += 1
        elif result.status == DriftStatus.OUTDATED:
            summary["outdated"] += 1
        elif result.status == DriftStatus.UNVERIFIABLE:
            summary["unverifiable"] += 1

    return DriftReport(
        source_file=source_file,
        generated_at=datetime.now(),
        results=results,
        summary=summary
    )
