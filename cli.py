# ABOUTME: Command-line interface for the content freshness system.
# ABOUTME: Orchestrates the analysis pipeline and outputs drift reports.

"""
Command-Line Interface Module
=============================

This module provides the CLI entry point for the Content Freshness System.
It orchestrates the entire analysis pipeline:

    [Input File] → [Parse] → [Extract Claims] → [Fetch Docs] → [Analyze] → [Report]

The CLI is built using Click, a popular Python library for creating
command-line interfaces. Click provides:
- Argument and option parsing
- Help text generation
- Input validation
- Error handling

Usage:
    uv run python cli.py training.md                    # Basic usage
    uv run python cli.py training.md -o report.md       # Save to file
    uv run python cli.py training.md -v                 # Verbose mode
    uv run python cli.py training.md -c custom.json     # Custom config
    uv run python cli.py --version                      # Show version

The CLI follows Unix conventions:
- Exit code 0 = success
- Exit code 1 = error
- Verbose output goes to stderr
- Report goes to stdout (or file with -o)
"""

# =============================================================================
# IMPORTS
# =============================================================================

# asyncio: Python's built-in async I/O library.
# We use asyncio.run() to run our async functions from the sync CLI entry point.
# Async allows concurrent operations (like fetching multiple URLs at once).
import asyncio

# sys: System-specific parameters and functions.
# We use sys.exit() to set the exit code on error.
import sys

# Path: Object-oriented filesystem paths.
# Used for input file and config file handling.
from pathlib import Path

# Type hints for function signatures.
# - List[X]: A list containing items of type X
# - Optional[X]: Either X or None
from typing import List, Optional

# click: Third-party library for building command-line interfaces.
# It provides decorators for defining commands, arguments, and options.
# Much cleaner than argparse for most use cases.
import click

# =============================================================================
# VERSION
# =============================================================================

# Version string for the --version flag.
# This should be updated when releasing new versions.
# Following semantic versioning: MAJOR.MINOR.PATCH
__version__ = "1.0.2"

# =============================================================================
# LOCAL IMPORTS
# =============================================================================

# Import functions from our analyzer modules.
# These are the building blocks of the analysis pipeline.

# Input handling: Parse markdown and extract claims.
# - load_markdown_file: Read the input file
# - parse_sections: Split into sections by headers
# - extract_claims: Find capability statements
# - Claim: Data class for extracted claims
from analyzer.input_handler import load_markdown_file, parse_sections, extract_claims, Claim

# Drift detection: Analyze claims using Claude.
# - analyze_claim: Compare one claim against docs
# - DriftResult: Data class for analysis results
from analyzer.drift_detector import analyze_claim, DriftResult

# Report generation: Format results as markdown.
# - generate_report: Create a DriftReport from results
from analyzer.report_generator import generate_report

# Documentation fetching: Get current Anthropic docs.
# - fetch_current_docs: Async fetch documentation pages
# - DocSection: Data class for doc content
from mcp_server.tools.fetch_docs import fetch_current_docs, DocSection

# Configuration: Get configured doc sources.
# - get_doc_sources: Get the URL mapping from config
from config import get_doc_sources


# =============================================================================
# ASYNC HELPER FUNCTIONS
# =============================================================================

async def fetch_reference_docs(
    verbose: bool = False,
    config_path: Optional[Path] = None
) -> List[DocSection]:
    """
    Fetch all reference documentation from configured sources.

    This function fetches documentation from all configured sources
    (like api-messages, models-overview, etc.) and returns them as
    a combined list. These docs are the "source of truth" for
    checking if claims are current.

    Progress Indicator:
    When verbose=True, prints progress percentage as each doc source
    is fetched. This helps users know the system is working, especially
    when fetching many pages.

    Args:
        verbose: If True, print progress information to stderr.
                 Defaults to False for quiet operation.
        config_path: Optional path to custom config file.
                     If None, uses default config or config.json.

    Returns:
        List of DocSection objects containing all fetched documentation.
        May be shorter than the number of sources if some fail to fetch.

    Example:
        >>> docs = await fetch_reference_docs(verbose=True)
        Fetching reference documentation...
          [5%] Fetching api-getting-started docs...
          [11%] Fetching api-messages docs...
          ...
        Fetched 19 documentation sections.
    """
    # Print initial message if verbose
    if verbose:
        # click.echo() is like print() but works better with Click's output handling
        click.echo("Fetching reference documentation...")

    # Initialize the result list
    all_docs: List[DocSection] = []

    # Get configured doc sources (topic name → URL mapping)
    doc_sources = get_doc_sources(config_path)

    # Convert to list of topic names for indexed iteration.
    # We need indices for progress calculation.
    topics = list(doc_sources.keys())

    # Fetch documentation for each topic
    for i, topic in enumerate(topics):
        # Show progress if verbose mode is enabled.
        # Progress = (completed + 1) / total * 100
        if verbose:
            progress = (i + 1) / len(topics) * 100
            # :.0f formats the float with 0 decimal places
            click.echo(f"  [{progress:.0f}%] Fetching {topic} docs...")

        try:
            # Fetch docs for this topic.
            # await pauses until the fetch completes.
            docs = await fetch_current_docs(topic, config_path)

            # Add fetched docs to our collection.
            # extend() adds all items from docs to all_docs.
            all_docs.extend(docs)

        except Exception as e:
            # Handle fetch errors gracefully.
            # We log the error but continue with other topics.
            # This makes the system more resilient.
            if verbose:
                # err=True prints to stderr instead of stdout
                click.echo(f"  Warning: Could not fetch {topic} docs: {e}", err=True)

    # Print final count if verbose
    if verbose:
        click.echo(f"Fetched {len(all_docs)} documentation sections.")

    return all_docs


async def analyze_claims(
    claims: List[Claim],
    docs: List[DocSection],
    verbose: bool = False,
    config_path: Optional[Path] = None
) -> List[DriftResult]:
    """
    Analyze all claims against documentation using Claude.

    This function iterates through each claim and sends it to Claude
    for analysis against the fetched documentation. Each claim is
    analyzed independently.

    Progress Indicator:
    When verbose=True, shows progress percentage and a preview of
    each claim being analyzed. This is important because API calls
    can be slow (1-3 seconds each).

    Note: Currently processes claims sequentially. For better performance,
    could be modified to process claims concurrently with asyncio.gather().
    However, this would need to respect API rate limits.

    Args:
        claims: List of Claim objects extracted from the input document.
        docs: List of DocSection objects to compare claims against.
        verbose: If True, print progress information to stderr.
        config_path: Optional path to custom config file.

    Returns:
        List of DriftResult objects, one for each claim analyzed.
        Results are in the same order as input claims.

    Example:
        >>> results = await analyze_claims(claims, docs, verbose=True)
        Analyzing 15 claims...
          [7%] Analyzing: Claude can process images and generate descr...
          [13%] Analyzing: The context window is 200k tokens...
          ...
    """
    # Print initial message if verbose
    if verbose:
        click.echo(f"Analyzing {len(claims)} claims...")

    # Initialize results list
    results: List[DriftResult] = []

    # Get total count for progress calculation
    total = len(claims)

    # Analyze each claim
    for i, claim in enumerate(claims):
        # Show progress if verbose
        if verbose:
            progress = (i + 1) / total * 100

            # Show first 50 characters of claim text with ellipsis.
            # [:50] takes first 50 chars, + "..." indicates truncation.
            click.echo(f"  [{progress:.0f}%] Analyzing: {claim.text[:50]}...")

        try:
            # Send claim to Claude for analysis.
            # await pauses until the API response arrives.
            result = await analyze_claim(claim, docs, config_path)

            # Add result to our collection
            results.append(result)

        except Exception as e:
            # Handle analysis errors gracefully.
            # We log and skip problematic claims rather than failing entirely.
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

    This is the main async function that orchestrates the entire analysis:
    1. Load and parse the input markdown file
    2. Extract capability claims from the content
    3. Fetch current documentation from Anthropic
    4. Analyze each claim against the documentation
    5. Generate a formatted report

    The function is async because steps 3 and 4 involve network I/O
    that benefits from async execution.

    Args:
        input_file: Path to the markdown file to analyze.
                    Should contain training content with capability claims.
        verbose: Whether to print progress information to stderr.
        config_path: Optional path to config file with custom settings.

    Returns:
        Markdown-formatted drift report as a string.
        Ready to be printed or saved to a file.

    Raises:
        FileNotFoundError: If the input file doesn't exist.
        SystemExit: If no documentation could be fetched.
    """
    # =========================================================================
    # STEP 1: LOAD AND PARSE INPUT FILE
    # =========================================================================

    if verbose:
        click.echo(f"Loading {input_file}...")

    # Read the markdown file content
    content = load_markdown_file(input_file)

    # Split content into sections by headers
    sections = parse_sections(content)

    # Extract capability claims from the sections
    claims = extract_claims(sections)

    if verbose:
        click.echo(f"Found {len(sections)} sections, {len(claims)} claims to analyze.")

    # =========================================================================
    # STEP 2: HANDLE EMPTY CLAIMS CASE
    # =========================================================================

    # If no claims found, generate an empty report
    if not claims:
        if verbose:
            click.echo("No capability claims found in document.")

        # Generate report with empty results list.
        # str(input_file) converts Path to string for the report.
        report = generate_report([], str(input_file))

        # Return the markdown representation
        return report.to_markdown()

    # =========================================================================
    # STEP 3: FETCH REFERENCE DOCUMENTATION
    # =========================================================================

    # Fetch all configured documentation sources.
    # This is async because it involves multiple HTTP requests.
    docs = await fetch_reference_docs(verbose, config_path)

    # Check if we got any documentation
    if not docs:
        # Can't proceed without documentation to compare against.
        # Print error and exit with non-zero code.
        click.echo("Error: Could not fetch any reference documentation.", err=True)
        sys.exit(1)

    # =========================================================================
    # STEP 4: ANALYZE CLAIMS
    # =========================================================================

    # Analyze each claim against the documentation.
    # This is async because each analysis involves an API call to Claude.
    results = await analyze_claims(claims, docs, verbose, config_path)

    # =========================================================================
    # STEP 5: GENERATE REPORT
    # =========================================================================

    if verbose:
        click.echo("Generating report...")

    # Create the drift report from analysis results
    report = generate_report(results, str(input_file))

    # Return the markdown-formatted report
    return report.to_markdown()


# =============================================================================
# CLI COMMAND DEFINITION
# =============================================================================

# @click.command() makes this function a Click command.
# Click will handle argument parsing and call this function with the parsed values.
@click.command()

# @click.version_option adds --version flag.
# version: The version string to display
# prog_name: Name shown in version output
@click.version_option(version=__version__, prog_name="content-freshness-system")

# @click.argument defines a required positional argument.
# "input_file" becomes the parameter name
# type=click.Path(...) validates that it's a valid file path
# exists=True ensures the file exists
# path_type=Path converts it to a Path object
@click.argument("input_file", type=click.Path(exists=True, path_type=Path))

# @click.option defines optional flags.
# "-o", "--output" means you can use either -o or --output
# type=click.Path(...) validates the path format
# help is shown in --help output
@click.option(
    "-o", "--output",
    type=click.Path(path_type=Path),
    help="Output file path (default: stdout)"
)

# Config file option
@click.option(
    "-c", "--config",
    type=click.Path(exists=True, path_type=Path),
    help="Path to config file (default: config.json in current directory)"
)

# Verbose flag - is_flag=True makes it a boolean flag (no value needed)
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

    This is the main CLI entry point. Click calls this function with
    the parsed command-line arguments.

    INPUT_FILE is the markdown file containing training content to analyze.
    The file should contain capability claims about Claude that you want
    to verify against current documentation.

    Use --config to specify custom documentation sources via a JSON file.
    See config.json for the expected format.

    \b
    Examples:
      freshness-check training.md
      freshness-check training.md -o report.md
      freshness-check training.md -v -c custom_config.json

    The docstring above is shown in --help output.
    The \\b tells Click not to wrap the following text.
    """
    # =========================================================================
    # CONFIG FILE HANDLING
    # =========================================================================

    # If no config specified, check for default config.json in current directory
    if config is None:
        default_config = Path("config.json")

        # Only use it if it exists
        if default_config.exists():
            config = default_config

    # Log which config we're using if verbose
    if verbose and config:
        click.echo(f"Using config: {config}")

    # =========================================================================
    # RUN ANALYSIS
    # =========================================================================

    try:
        # Run the async analysis using asyncio.run().
        # asyncio.run() creates an event loop, runs the coroutine,
        # and cleans up when done. It bridges sync Click to async code.
        report_content = asyncio.run(run_analysis(input_file, verbose, config))

        # =====================================================================
        # OUTPUT HANDLING
        # =====================================================================

        if output:
            # Write to file if output path specified.
            # Path.write_text() writes string content to a file.
            output.write_text(report_content)

            if verbose:
                click.echo(f"Report written to {output}")
        else:
            # Print to stdout if no output file specified.
            # This allows piping: cli.py input.md > report.md
            click.echo(report_content)

    except FileNotFoundError as e:
        # Handle file not found errors (should be rare since Click validates)
        click.echo(f"Error: File not found - {e}", err=True)
        sys.exit(1)

    except Exception as e:
        # Handle any other errors
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


# =============================================================================
# ENTRY POINTS
# =============================================================================

def main() -> None:
    """
    Entry point for the CLI.

    This function is called when running the package as a script
    or using the 'freshness-check' console script defined in pyproject.toml.

    It simply delegates to the Click command.
    """
    cli()


# This block runs when the file is executed directly (not imported).
# python cli.py → __name__ == "__main__" → call main()
if __name__ == "__main__":
    main()
