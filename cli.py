# ABOUTME: Command-line interface for the content freshness system.
# ABOUTME: Orchestrates the analysis pipeline and outputs drift reports.

import asyncio
import sys
from pathlib import Path
from typing import List, Optional

import click

__version__ = "1.0.1"

from analyzer.input_handler import load_markdown_file, parse_sections, extract_claims, Claim
from analyzer.drift_detector import analyze_claim, DriftResult
from analyzer.report_generator import generate_report
from mcp_server.tools.fetch_docs import fetch_current_docs, DocSection
from config import get_doc_sources


async def fetch_reference_docs(
    verbose: bool = False,
    config_path: Optional[Path] = None
) -> List[DocSection]:
    """Fetch all reference documentation."""
    if verbose:
        click.echo("Fetching reference documentation...")

    all_docs: List[DocSection] = []
    doc_sources = get_doc_sources(config_path)
    topics = list(doc_sources.keys())

    for i, topic in enumerate(topics):
        if verbose:
            progress = (i + 1) / len(topics) * 100
            click.echo(f"  [{progress:.0f}%] Fetching {topic} docs...")

        try:
            docs = await fetch_current_docs(topic, config_path)
            all_docs.extend(docs)
        except Exception as e:
            if verbose:
                click.echo(f"  Warning: Could not fetch {topic} docs: {e}", err=True)

    if verbose:
        click.echo(f"Fetched {len(all_docs)} documentation sections.")

    return all_docs


async def analyze_claims(
    claims: List[Claim],
    docs: List[DocSection],
    verbose: bool = False,
    config_path: Optional[Path] = None
) -> List[DriftResult]:
    """Analyze all claims against documentation."""
    if verbose:
        click.echo(f"Analyzing {len(claims)} claims...")

    results: List[DriftResult] = []
    total = len(claims)

    for i, claim in enumerate(claims):
        if verbose:
            progress = (i + 1) / total * 100
            click.echo(f"  [{progress:.0f}%] Analyzing: {claim.text[:50]}...")

        try:
            result = await analyze_claim(claim, docs, config_path)
            results.append(result)
        except Exception as e:
            if verbose:
                click.echo(f"  Warning: Could not analyze claim: {e}", err=True)

    return results


async def run_analysis(
    input_file: Path,
    verbose: bool = False,
    config_path: Optional[Path] = None
) -> str:
    """
    Run the complete analysis pipeline.

    Args:
        input_file: Path to the markdown file to analyze.
        verbose: Whether to print progress information.
        config_path: Optional path to config file.

    Returns:
        Markdown-formatted drift report.
    """
    # Load and parse input file
    if verbose:
        click.echo(f"Loading {input_file}...")

    content = load_markdown_file(input_file)
    sections = parse_sections(content)
    claims = extract_claims(sections)

    if verbose:
        click.echo(f"Found {len(sections)} sections, {len(claims)} claims to analyze.")

    if not claims:
        if verbose:
            click.echo("No capability claims found in document.")
        report = generate_report([], str(input_file))
        return report.to_markdown()

    # Fetch reference documentation
    docs = await fetch_reference_docs(verbose, config_path)

    if not docs:
        click.echo("Error: Could not fetch any reference documentation.", err=True)
        sys.exit(1)

    # Analyze claims
    results = await analyze_claims(claims, docs, verbose, config_path)

    # Generate report
    if verbose:
        click.echo("Generating report...")

    report = generate_report(results, str(input_file))
    return report.to_markdown()


@click.command()
@click.version_option(version=__version__, prog_name="content-freshness-system")
@click.argument("input_file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "-o", "--output",
    type=click.Path(path_type=Path),
    help="Output file path (default: stdout)"
)
@click.option(
    "-c", "--config",
    type=click.Path(exists=True, path_type=Path),
    help="Path to config file (default: config.json in current directory)"
)
@click.option(
    "-v", "--verbose",
    is_flag=True,
    help="Show detailed progress information"
)
def cli(
    input_file: Path,
    output: Optional[Path],
    config: Optional[Path],
    verbose: bool
) -> None:
    """
    Analyze training content for drift from current Claude documentation.

    INPUT_FILE is the markdown file containing training content to analyze.

    Use --config to specify custom documentation sources.
    """
    # Use default config.json if exists and no config specified
    if config is None:
        default_config = Path("config.json")
        if default_config.exists():
            config = default_config

    if verbose and config:
        click.echo(f"Using config: {config}")

    try:
        # Run the async analysis
        report_content = asyncio.run(run_analysis(input_file, verbose, config))

        # Output the report
        if output:
            output.write_text(report_content)
            if verbose:
                click.echo(f"Report written to {output}")
        else:
            click.echo(report_content)

    except FileNotFoundError as e:
        click.echo(f"Error: File not found - {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


def main() -> None:
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
