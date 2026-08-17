# MCP Server Claude Doc monitor

Training content drift detection system

**Stack**: Python, Anthropic SDK, GitHub Actions

## Commands

- **Install**: `uv sync --dev`
- **Test**: `uv run pytest`
- **Lint**: `uv run ruff check .`
- **Format**: `uv run ruff format .`
- **Type check**: `uv run mypy analyzer/ mcp_server/ cli.py config.py --ignore-missing-imports`
