# ABOUTME: Report generator for drift analysis results.
# ABOUTME: Produces markdown reports with status summaries and recommendations.

"""
Report Generator Module
=======================

This module is the final stage of the drift detection pipeline. It takes
the analysis results and formats them into a human-readable markdown report.

Pipeline Stage: DriftResults → [REPORT GENERATOR] → Markdown Report

The report includes:
1. Header with source file and generation timestamp
2. Summary counts (how many current, outdated, etc.)
3. Detailed results table with all analyzed claims
4. Recommended updates section for outdated claims
5. Lists of potentially stale and unverifiable claims

Design Principles:
- Actionable: Focus on what needs to be done (updates first)
- Scannable: Summary at top, details below
- Complete: Include all information needed to fix issues
- Portable: Plain markdown works everywhere (GitHub, editors, etc.)

The report format is designed to be:
- Readable in a terminal (plain text)
- Renderable in GitHub/GitLab (formatted markdown)
- Parseable by scripts (consistent structure)
"""

# =============================================================================
# IMPORTS
# =============================================================================

from __future__ import annotations

# dataclass: Creates data container classes with auto-generated methods.
from dataclasses import dataclass, field

# datetime: For capturing when the report was generated.
# We include timestamps to track when analysis was done.
from datetime import datetime


# Import our custom types from the drift detector module.
# DriftResult: The analysis result for a single claim.
# DriftStatus: The enum of possible statuses (CURRENT, OUTDATED, etc.)
from analyzer.changelog_analyzer import ChangelogImpact
from analyzer.drift_detector import CitedEvidence, DriftResult, DriftStatus


def _render_evidence(evidence: list[CitedEvidence]) -> list[str]:
    """Render cited evidence as markdown blockquotes with provenance."""
    lines: list[str] = []
    for ev in evidence:
        lines.append(f"> {ev.cited_text}")
        start, end = ev.char_range
        lines.append(f"> — *{ev.document_title}* ({ev.document_url}) [chars {start}–{end}]")
        lines.append("")
    return lines


def _render_changelog_impacts(impacts: list[ChangelogImpact]) -> list[str]:
    """Render recent-changelog impacts grouped by severity."""
    if not impacts:
        return []
    lines: list[str] = ["## Recent Changelog Impact", ""]
    severity_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    sorted_impacts = sorted(impacts, key=lambda i: severity_order.get(i.severity, 3))
    for imp in sorted_impacts:
        lines.append(f"### [{imp.severity}] {imp.entry_title} ({imp.entry_date})")
        lines.append("")
        lines.append(f"**Affected claim:** {imp.claim_text}")
        lines.append("")
        lines.append(f"**Why it matters:** {imp.explanation}")
        lines.append("")
        lines.append(f"**Source:** {imp.entry_url}")
        lines.append("")
    return lines


# =============================================================================
# DRIFT REPORT DATA CLASS
# =============================================================================

@dataclass
class DriftReport:
    """
    Complete drift analysis report.

    This dataclass holds all the data needed to generate the final report.
    It includes both raw data (results list) and computed data (summary counts).

    The to_markdown() method converts this data into a formatted markdown string
    that can be printed to stdout or saved to a file.

    Attributes:
        source_file: Name/path of the file that was analyzed.
                     Shown in the report header for reference.

        generated_at: Timestamp when the report was created.
                      Helps track when the analysis was done.

        results: List of all DriftResult objects from the analysis.
                 Contains the full details for each claim.

        summary: Dictionary with counts of each status type.
                 Keys: 'current', 'potentially_stale', 'outdated', 'unverifiable'
                 Values: Count of claims with that status
    """
    source_file: str                 # Path to the analyzed file
    generated_at: datetime           # When the report was generated
    results: list[DriftResult]       # All analysis results
    summary: dict[str, int]          # Count of each status type
    changelog_impacts: list[ChangelogImpact] = field(default_factory=list)

    def to_markdown(self) -> str:
        """
        Convert report to markdown format.

        This method generates a complete markdown document from the report data.
        The output is designed to be both human-readable and renderable in
        markdown viewers like GitHub or VS Code.

        Structure:
        1. Title and metadata (file name, timestamp)
        2. Summary section with status counts
        3. Results table with all claims
        4. Recommended updates (outdated claims with suggested fixes)
        5. Potentially stale claims (needs manual review)
        6. Unverifiable claims (couldn't find docs to verify)

        Returns:
            A complete markdown document as a string.
            Includes headers, tables, lists, and formatted text.

        Example output (abbreviated):
            # Drift Analysis Report

            **Source File:** training.md
            **Generated:** 2024-01-15 10:30:45

            ## Summary

            Total claims analyzed: **15**

            - Current: 10
            - Outdated: 3
            ...
        """
        # We build the report as a list of lines, then join them at the end.
        # This is more efficient and cleaner than string concatenation.
        lines = []

        # =====================================================================
        # HEADER SECTION
        # =====================================================================

        # Main title using markdown H1 (single #)
        lines.append("# Drift Analysis Report")
        lines.append("")  # Empty line for spacing

        # Metadata: source file and timestamp
        # Using **bold** for labels
        lines.append(f"**Source File:** {self.source_file}")

        # strftime() formats the datetime as a string.
        # %Y-%m-%d = year-month-day (2024-01-15)
        # %H:%M:%S = hour:minute:second (10:30:45)
        lines.append(f"**Generated:** {self.generated_at.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        # =====================================================================
        # SUMMARY SECTION
        # =====================================================================

        # H2 header for summary
        lines.append("## Summary")
        lines.append("")

        # Calculate total claims by summing all values in the summary dict.
        # sum() adds up all the numbers in the dictionary's values.
        total = sum(self.summary.values())
        lines.append(f"Total claims analyzed: **{total}**")
        lines.append("")

        # List each status count.
        # .get(key, default) returns the value for key, or default if not found.
        # Using 0 as default ensures we show "0" instead of crashing.
        lines.append(f"- Current: {self.summary.get('current', 0)}")
        lines.append(f"- Potentially Stale: {self.summary.get('potentially_stale', 0)}")
        lines.append(f"- Outdated: {self.summary.get('outdated', 0)}")
        lines.append(f"- Unverifiable: {self.summary.get('unverifiable', 0)}")
        lines.append("")

        # Handle empty results case
        if not self.results:
            lines.append("*No claims were analyzed.*")
            if self.changelog_impacts:
                lines.extend(_render_changelog_impacts(self.changelog_impacts))
            return "\n".join(lines)

        # Recent changelog impacts render before the per-claim breakdown so
        # reviewers see the most time-sensitive drift at the top of the report.
        if self.changelog_impacts:
            lines.extend(_render_changelog_impacts(self.changelog_impacts))

        # =====================================================================
        # RESULTS TABLE
        # =====================================================================

        # H2 header for results
        lines.append("## Analysis Results")
        lines.append("")

        # Markdown table header row.
        # | Column1 | Column2 | creates a table row.
        lines.append("| Section | Claim | Status | Notes |")

        # Table separator row (required in markdown tables).
        # The dashes define column alignment.
        lines.append("|---------|-------|--------|-------|")

        # Add a row for each result
        for result in self.results:
            # Truncate long claims to keep the table readable.
            # [:60] takes the first 60 characters.
            claim_display = result.claim_text[:60]

            # Add ellipsis if we truncated
            if len(result.claim_text) > 60:
                claim_display += "..."

            # Escape pipe characters (|) because they're table delimiters.
            # If the claim contains |, it would break the table structure.
            # replace() substitutes all occurrences.
            claim_display = claim_display.replace("|", "\\|")

            # Similarly escape and truncate the reasoning
            reasoning = result.reasoning.replace("|", "\\|")[:80]

            # Build the table row.
            # result.status.value gets the string value from the enum.
            lines.append(
                f"| {result.section_title} | {claim_display} | "
                f"{result.status.value} | {reasoning} |"
            )

        lines.append("")  # Spacing after table

        # =====================================================================
        # RECOMMENDED UPDATES SECTION
        # =====================================================================

        # Filter to get only outdated results.
        # List comprehension: [item for item in list if condition]
        outdated_results = [r for r in self.results if r.status == DriftStatus.OUTDATED]

        # Only show this section if there are outdated claims
        if outdated_results:
            lines.append("## Recommended Updates")
            lines.append("")

            # enumerate() with start=1 gives us 1-based numbering.
            # This is more natural for humans (item 1, 2, 3 vs 0, 1, 2).
            for i, result in enumerate(outdated_results, 1):
                # H3 header for each update (numbered)
                lines.append(f"### {i}. Line {result.line_number}: {result.section_title}")
                lines.append("")

                # Show the current (outdated) claim text
                lines.append(f"**Current claim:** {result.claim_text}")
                lines.append("")

                # Show the suggested replacement if available
                if result.suggested_update:
                    lines.append(f"**Suggested update:** {result.suggested_update}")
                    lines.append("")

                # Show the reference documentation URL if available
                if result.source_reference:
                    lines.append(f"**Reference:** {result.source_reference}")
                    lines.append("")

                # Show cited evidence spans — verified pointers into the live doc
                if result.evidence:
                    lines.extend(_render_evidence(result.evidence))

        # =====================================================================
        # POTENTIALLY STALE SECTION
        # =====================================================================

        # Filter for potentially stale results
        stale_results = [
            r for r in self.results
            if r.status == DriftStatus.POTENTIALLY_STALE
        ]

        # Only show section if there are stale claims
        if stale_results:
            lines.append("## Potentially Stale (Manual Review Recommended)")
            lines.append("")

            # Simple bullet list of claims
            for result in stale_results:
                # Truncate to 80 chars for readability
                lines.append(f"- Line {result.line_number}: {result.claim_text[:80]}")

            lines.append("")

        # =====================================================================
        # UNVERIFIABLE SECTION
        # =====================================================================

        # Filter for unverifiable results
        unverifiable_results = [
            r for r in self.results
            if r.status == DriftStatus.UNVERIFIABLE
        ]

        # Only show section if there are unverifiable claims
        if unverifiable_results:
            lines.append("## Unverifiable Claims")
            lines.append("")

            # Explanatory note in italics
            lines.append("*These claims could not be verified against current documentation:*")
            lines.append("")

            # Simple bullet list
            for result in unverifiable_results:
                lines.append(f"- Line {result.line_number}: {result.claim_text[:80]}")

            lines.append("")

        # =====================================================================
        # FINALIZE AND RETURN
        # =====================================================================

        # Join all lines with newline characters to create the final document.
        # "\n".join(list) is the standard Python idiom for joining strings.
        return "\n".join(lines)


# =============================================================================
# REPORT GENERATION FUNCTION
# =============================================================================

def generate_report(
    results: list[DriftResult],
    source_file: str,
    changelog_impacts: list[ChangelogImpact] | None = None,
) -> DriftReport:
    """
    Generate a drift report from analysis results.

    This function takes the raw analysis results and creates a DriftReport
    object that includes computed summary statistics. The report object
    can then be converted to markdown using its to_markdown() method.

    This separation of concerns (generate data structure vs format output)
    makes it easier to:
    1. Test the report generation logic
    2. Add alternative output formats (HTML, JSON) in the future
    3. Access the structured data programmatically

    Args:
        results: List of DriftResult objects from analysis.
                 Can be empty if no claims were found/analyzed.
        source_file: Name of the source file that was analyzed.
                     Used in the report header.

    Returns:
        DriftReport containing summary and all results.

    Example:
        >>> results = [DriftResult(...), DriftResult(...)]
        >>> report = generate_report(results, "training.md")
        >>> print(report.summary)
        {'current': 5, 'potentially_stale': 2, 'outdated': 1, 'unverifiable': 0}
        >>> print(report.to_markdown())
        # Drift Analysis Report
        ...
    """
    # Initialize summary counts dictionary.
    # All counts start at zero.
    summary = {
        "current": 0,
        "potentially_stale": 0,
        "outdated": 0,
        "unverifiable": 0
    }

    # Count results by status.
    # We iterate through all results and increment the appropriate counter.
    for result in results:
        # Check which status the result has and increment that counter.
        # We use separate if statements instead of a dictionary lookup
        # because the enum values and dict keys don't match exactly
        # (e.g., DriftStatus.CURRENT vs "current").

        if result.status == DriftStatus.CURRENT:
            summary["current"] += 1

        elif result.status == DriftStatus.POTENTIALLY_STALE:
            summary["potentially_stale"] += 1

        elif result.status == DriftStatus.OUTDATED:
            summary["outdated"] += 1

        elif result.status == DriftStatus.UNVERIFIABLE:
            summary["unverifiable"] += 1

    # Create and return the DriftReport dataclass instance.
    # datetime.now() captures the current time for the report timestamp.
    return DriftReport(
        source_file=source_file,
        generated_at=datetime.now(),
        results=results,
        summary=summary,
        changelog_impacts=changelog_impacts or [],
    )
