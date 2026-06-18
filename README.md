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

# Install dependencies (use --dev to include the test/lint toolchain)
uv sync --dev

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

### Flag Reference

| Flag | Purpose |
|------|---------|
| `-o, --output FILE` | Write report to file instead of stdout. |
| `-c, --config FILE` | Use a custom config file. |
| `-v, --verbose` | Show progress bars, cache-hit metrics, and warnings. |
| `--fast` | Use regex-based claim extraction (zero API cost, lower recall). Default is LLM extraction, cached by content SHA256. |
| `--batch` | Submit analysis via the Batches API (~50% cheaper, up to 1h latency). |
| `--dry-run` | Estimate input tokens and cost via `count_tokens`, then exit without running the analysis. |
| `--skip-changelog` | Skip the recent-changelog cross-reference pass. |

### Citation-Backed Evidence

Outdated claims in the report include blockquoted excerpts from the live docs with title, URL, and exact character range, using the Anthropic Citations API. Example:

```markdown
### 1. Line 42: API Limits

**Current claim:** Context is 100k tokens.
**Suggested update:** Context is 200k tokens.
**Reference:** https://platform.claude.com/docs/about-claude/models

> Claude supports a 200,000 token context window.
> — *Models Overview* (https://platform.claude.com/docs/about-claude/models) [chars 42–90]
```

## MCP Server

The same drift-detection logic is exposed as an MCP server so Claude Code, Claude Desktop, or any other MCP-compatible client can invoke it.

```bash
# Run the server over stdio (default)
uv run python -m mcp_server.server
```

Tools exposed:

| Tool | Purpose |
|------|---------|
| `check_drift(markdown)` | Analyze a training-content markdown string and return per-claim drift status with cited evidence. |
| `search_docs(query)` | Keyword-search the configured Claude docs; returns ranked snippets. |
| `get_changelog(days)` | Return changelog entries from the last *N* days. |

Resources exposed:

| URI template | Returns |
|--------------|---------|
| `docs://{topic}` | Current content for a doc topic (e.g. `docs://models`). |

### Registering with Claude Code

Add to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "freshness": {
      "command": "uv",
      "args": ["--directory", "/path/to/MCP_Server_Claude_Doc_monitor", "run", "python", "-m", "mcp_server.server"],
      "env": {"ANTHROPIC_API_KEY": "your-api-key-here"}
    }
  }
}
```

## Configuration

The system uses a JSON configuration file to specify documentation sources and settings. By default, it looks for `config.json` in the current directory.

### Config File Format

```json
{
  "doc_sources": {
    "api-getting-started": "https://platform.claude.com/docs/en/api/getting-started",
    "models-overview": "https://platform.claude.com/docs/en/about-claude/models/overview",
    "api-messages": "https://platform.claude.com/docs/en/api/messages",
    "vision": "https://platform.claude.com/docs/en/build-with-claude/vision",
    "context-windows": "https://platform.claude.com/docs/en/build-with-claude/context-windows",
    "api-rate-limits": "https://platform.claude.com/docs/en/api/rate-limits"
  },
  "changelog_url": "https://platform.claude.com/docs/en/release-notes/overview",
  "fetch_timeout": 45,
  "analysis_model": "claude-sonnet-4-6"
}
```

> The repository ships a full `config.json` (and a matching `config.example.json`) covering ~20 documentation sources. The snippet above is abbreviated.

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
    "api": "https://platform.claude.com/docs/en/api/getting-started",
    "custom-topic": "https://platform.claude.com/docs/en/your-custom-page"
  }
}
```

### Using a Custom Config

```bash
# Create custom config
cat > my-config.json << 'EOF'
{
  "doc_sources": {
    "api": "https://platform.claude.com/docs/en/api/getting-started"
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
├── config.example.json     # Annotated configuration template
├── config.py               # Configuration loader
├── cli.py                  # Command-line interface
├── analyzer/
│   ├── input_handler.py    # Parse markdown and extract claims (regex path)
│   ├── claim_extractor.py  # Claude-based claim extraction (default, SHA256-cached)
│   ├── drift_detector.py   # Claude-powered analysis with Citations API
│   ├── batch_runner.py     # Batches API submission and polling
│   ├── cost_estimator.py   # Token/cost estimation via count_tokens
│   ├── changelog_analyzer.py # Recent-changelog impact cross-reference
│   └── report_generator.py # Generate drift reports
├── mcp_server/
│   ├── server.py           # FastMCP server (stdio) exposing the tools below
│   └── tools/
│       ├── fetch_docs.py   # Doc fetching from configured URLs
│       ├── get_changelog.py# Changelog retrieval
│       └── search_docs.py  # Search across documentation
├── tests/                  # 128 unit and integration tests
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
