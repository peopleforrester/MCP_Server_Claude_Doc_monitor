# Content Freshness System

[![CI](https://github.com/peopleforrester/MCP_Server_Claude_Doc_monitor/actions/workflows/ci.yml/badge.svg)](https://github.com/peopleforrester/MCP_Server_Claude_Doc_monitor/actions/workflows/ci.yml)

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
- **Doc Fetcher**: Fetches current Claude documentation from configurable URLs
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

# Use custom config file
uv run python cli.py training-content.md -c my-config.json

# Analyze the sample document
uv run python cli.py sample_input/outdated-training-doc.md -v
```

## Configuration

The system uses a JSON configuration file to specify documentation sources and settings. By default, it looks for `config.json` in the current directory.

### Config File Format

```json
{
  "doc_sources": {
    "api": "https://docs.anthropic.com/en/api/getting-started",
    "models": "https://docs.anthropic.com/en/docs/about-claude/models",
    "messages": "https://docs.anthropic.com/en/api/messages",
    "vision": "https://docs.anthropic.com/en/docs/build-with-claude/vision",
    "context": "https://docs.anthropic.com/en/docs/build-with-claude/context-windows",
    "rate-limits": "https://docs.anthropic.com/en/api/rate-limits"
  },
  "changelog_url": "https://docs.anthropic.com/en/docs/resources/changelog",
  "fetch_timeout": 30,
  "analysis_model": "claude-sonnet-4-20250514"
}
```

### Configuration Options

| Option | Type | Description |
|--------|------|-------------|
| `doc_sources` | object | Map of topic names to documentation URLs |
| `changelog_url` | string | URL to the changelog page |
| `fetch_timeout` | integer | HTTP request timeout in seconds |
| `analysis_model` | string | Claude model to use for analysis |

### Adding Custom Documentation Sources

To monitor additional documentation pages, add entries to `doc_sources`:

```json
{
  "doc_sources": {
    "api": "https://docs.anthropic.com/en/api/getting-started",
    "custom-topic": "https://docs.anthropic.com/en/docs/your-custom-page"
  }
}
```

### Using a Custom Config

```bash
# Create custom config
cat > my-config.json << 'EOF'
{
  "doc_sources": {
    "api": "https://docs.anthropic.com/en/api/getting-started"
  },
  "fetch_timeout": 60
}
EOF

# Run with custom config
uv run python cli.py training-doc.md -c my-config.json
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
├── config.json             # Default configuration
├── config.py               # Configuration loader
├── cli.py                  # Command-line interface
├── analyzer/
│   ├── input_handler.py    # Parse markdown and extract claims
│   ├── drift_detector.py   # Claude-powered analysis
│   └── report_generator.py # Generate drift reports
├── mcp_server/
│   └── tools/
│       ├── fetch_docs.py   # Doc fetching from configured URLs
│       ├── get_changelog.py# Changelog retrieval
│       └── search_docs.py  # Search across documentation
├── tests/                  # 84 unit and integration tests
├── sample_input/           # Example training doc with outdated claims
└── sample_output/          # Example drift report
```

## Development

```bash
# Run tests
uv run pytest

# Run tests with verbose output
uv run pytest -v

# Run specific test file
uv run pytest tests/test_config.py
```

## License

Apache License 2.0 - See [LICENSE](LICENSE) for details.
