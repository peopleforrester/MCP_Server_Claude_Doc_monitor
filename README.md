# Content Freshness System

Claude-powered training content drift detection system.

## Overview

Training content about Claude goes stale as capabilities evolve. This system automates drift detection by comparing training materials against current documentation and changelogs.

## Architecture

```
[Training Doc] --> [Freshness Analyzer] --> [Drift Report]
                          ^
                [Claude Docs/Changelog]
```

## Components

- **Input Handler**: Parses training documents and extracts capability claims
- **Doc Fetcher**: Fetches current Claude documentation from docs.anthropic.com
- **Drift Analyzer**: Claude-powered comparison engine
- **Report Generator**: Produces actionable drift reports

## Setup

### Prerequisites

- Python 3.13+
- [uv](https://github.com/astral-sh/uv) package manager
- Anthropic API key

### Installation

```bash
# Clone the repository
git clone https://github.com/peopleforrester/MCP_Server_Claude_Doc_monitor.git
cd MCP_Server_Claude_Doc_monitor

# Install dependencies
uv sync

# Set your API key
export ANTHROPIC_API_KEY="your-api-key-here"

# Run tests to verify installation
uv run pytest
```

## Usage

```bash
# Basic usage - output to stdout
uv run python cli.py training-content.md

# Save report to file
uv run python cli.py training-content.md -o drift-report.md

# Verbose mode with progress indicators
uv run python cli.py training-content.md --verbose

# Analyze the sample document
uv run python cli.py sample_input/outdated-training-doc.md -v
```

## Example Output

See `sample_output/drift-report.md` for an example of the generated report format.

The report includes:
- Summary of claims by status (Current, Outdated, Potentially Stale, Unverifiable)
- Detailed analysis table
- Recommended updates with line references
- Source documentation links

## Drift Classifications

| Status | Meaning |
|--------|---------|
| CURRENT | Claim matches current documentation |
| OUTDATED | Claim contradicts current documentation |
| POTENTIALLY_STALE | May be outdated, needs manual review |
| UNVERIFIABLE | Cannot find documentation to verify |

## Project Structure

```
content-freshness-system/
├── analyzer/
│   ├── input_handler.py    # Parse markdown and extract claims
│   ├── drift_detector.py   # Claude-powered analysis
│   └── report_generator.py # Generate drift reports
├── mcp_server/
│   └── tools/
│       ├── fetch_docs.py   # Doc fetching from docs.anthropic.com
│       ├── get_changelog.py# Changelog retrieval
│       └── search_docs.py  # Search across documentation
├── tests/                  # 64 unit tests
├── sample_input/           # Example training doc with outdated claims
├── sample_output/          # Example drift report
└── cli.py                  # Command-line interface
```

## Development

```bash
# Run tests
uv run pytest

# Run tests with verbose output
uv run pytest -v

# Run specific test file
uv run pytest tests/test_input_handler.py
```

## License

TBD
