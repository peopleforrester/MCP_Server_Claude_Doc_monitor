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

from __future__ import annotations

# asyncio: Python's built-in async I/O library.
# We use asyncio.run() to run our async functions from the sync CLI entry point.
# Async allows concurrent operations (like fetching multiple URLs at once).
import asyncio
import logging

# sys: System-specific parameters and functions.
# We use sys.exit() to set the exit code on error.
import sys

# anthropic: The official SDK for calling the API.
import anthropic

# tomllib: Standard library TOML parser (Python 3.11+).
# Used to read the version from pyproject.toml as the single source of truth.
import tomllib

# Path: Object-oriented filesystem paths.
# Used for input file and config file handling.
from pathlib import Path


# click: Third-party library for building command-line interfaces.
# It provides decorators for defining commands, arguments, and options.
# Much cleaner than argparse for most use cases.
import click

# =============================================================================
# VERSION
# =============================================================================

def _read_version() -> str:
    """Read project version from pyproject.toml.

    This avoids duplicating the version string in multiple files.
    pyproject.toml is the single source of truth for the version.
    """
    pyproject_path = Path(__file__).parent / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)
    return data["project"]["version"]


__version__ = _read_version()

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

# Claude-based extraction (default path); regex extract_claims remains available via --fast.
from analyzer.claim_extractor import extract_claims_with_llm

# Drift detection: Analyze claims using Claude.
# - analyze_claim: Compare one claim against docs
# - DriftResult: Data class for analysis results
from analyzer.drift_detector import analyze_claim, DriftResult

# Opt-in batch processing path: trades latency for ~10x cost savings via 50%
# batch discount + 1h prompt cache on system prompt and doc corpus.
from analyzer.batch_runner import analyze_claims_batch

from tqdm.asyncio import tqdm_asyncio

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
    config_path: Path | None = None
) -> list[DocSection]:
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
    # Get configured doc sources (topic name → URL mapping)
    doc_sources = get_doc_sources(config_path)
    topics = list(doc_sources.keys())

    async def fetch_topic(topic: str) -> list[DocSection]:
        """Fetch docs for a single topic, swallowing errors as empty lists."""
        try:
            return await fetch_current_docs(topic, config_path)
        except Exception as e:
            if verbose:
                click.echo(f"  Warning: Could not fetch {topic} docs: {e}", err=True)
            return []

    # Fetch all topics concurrently with a progress bar when verbose.
    if verbose:
        results = await tqdm_asyncio.gather(
            *(fetch_topic(t) for t in topics),
            desc="Fetching docs",
            unit="topic",
        )
    else:
        results = await asyncio.gather(*(fetch_topic(t) for t in topics))

    # Flatten the list of lists
    all_docs: list[DocSection] = []
    for docs in results:
        all_docs.extend(docs)

    # Print final count if verbose
    if verbose:
        click.echo(f"Fetched {len(all_docs)} documentation sections.")

    return all_docs


async def analyze_claims(
    claims: list[Claim],
    docs: list[DocSection],
    verbose: bool = False,
    config_path: Path | None = None
) -> list[DriftResult]:
    """
    Analyze all claims against documentation using Claude.

    This function processes claims concurrently using asyncio.gather()
    with a semaphore to respect API rate limits. Claims are analyzed
    independently against the fetched documentation.

    Progress Indicator:
    When verbose=True, shows progress as each claim completes.

    Args:
        claims: List of Claim objects extracted from the input document.
        docs: List of DocSection objects to compare claims against.
        verbose: If True, print progress information to stderr.
        config_path: Optional path to custom config file.

    Returns:
        List of DriftResult objects, one for each claim analyzed.
        Results are in the same order as input claims.
        Claims that fail analysis are excluded from results.

    Example:
        >>> results = await analyze_claims(claims, docs, verbose=True)
        Analyzing 15 claims (5 concurrent)...
          [7%] Analyzed: Claude can process images and generate descr...
          [13%] Analyzed: The context window is 200k tokens...
          ...
    """
    # Semaphore limits concurrent API calls to avoid rate limiting.
    # 5 concurrent requests is a conservative limit for the API.
    max_concurrent = 5
    semaphore = asyncio.Semaphore(max_concurrent)

    # Create a single API client to reuse across all claim analyses.
    # This avoids creating a new HTTP connection pool per claim.
    api_client = anthropic.AsyncAnthropic()

    async def analyze_single(claim: Claim) -> DriftResult | None:
        """Analyze a single claim with semaphore-limited concurrency."""
        async with semaphore:
            try:
                return await analyze_claim(claim, docs, config_path, client=api_client)
            except Exception as e:
                if verbose:
                    click.echo(f"  Warning: Could not analyze claim: {e}", err=True)
                return None

    # Run all analyses concurrently (limited by semaphore), with tqdm progress bar.
    if verbose:
        all_results = await tqdm_asyncio.gather(
            *(analyze_single(claim) for claim in claims),
            desc=f"Analyzing claims (x{max_concurrent})",
            unit="claim",
        )
    else:
        all_results = await asyncio.gather(
            *(analyze_single(claim) for claim in claims)
        )

    # Filter out None results from failed analyses
    results = [r for r in all_results if r is not None]

    return results


async def run_analysis(
    input_file: Path,
    verbose: bool = False,
    config_path: Path | None = None,
    fast: bool = False,
    batch: bool = False,
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

    # Extract capability claims from the sections.
    # Default: Claude-based extractor (higher recall, cached by content hash).
    # --fast: regex extractor (zero API cost, lower recall).
    if fast:
        if verbose:
            click.echo("Extracting claims (regex, --fast mode)...")
        claims: list[Claim] = extract_claims(sections)
    else:
        if verbose:
            click.echo("Extracting claims (Claude, cached by content hash)...")
        claims = list(await extract_claims_with_llm(sections, config_path=config_path))

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

    # Analyze each claim. --batch trades latency for ~10x cost savings.
    if batch:
        if verbose:
            click.echo(f"Submitting {len(claims)} claims to the Batches API...")
        results = await analyze_claims_batch(
            claims, docs, config_path=config_path,
            progress_cb=(lambda b: click.echo(f"  batch status: {b.processing_status}")) if verbose else None,
        )
    else:
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
@click.option(
    "--fast",
    is_flag=True,
    help="Use regex-based claim extraction (no LLM call, lower recall)"
)
@click.option(
    "--batch",
    is_flag=True,
    help="Submit analysis via Anthropic Batches API (~50% cheaper, up to 1h latency)"
)
def cli(
    input_file: Path,
    output: Path | None,
    config: Path | None,
    verbose: bool,
    fast: bool,
    batch: bool,
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

    # Verbose mode: surface INFO logs (e.g., cache hit metrics from drift_detector).
    if verbose:
        logging.basicConfig(level=logging.INFO, format="  [%(name)s] %(message)s")

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
        report_content = asyncio.run(
            run_analysis(input_file, verbose, config, fast=fast, batch=batch)
        )

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
