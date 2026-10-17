# MCP Server Claude Doc monitor

Training content drift detection system

**Stack**: Python, Anthropic SDK, GitHub Actions

## Commands

- **Install**: `uv sync --dev`
- **Test**: `uv run pytest`
- **Lint**: `uv run ruff check .`
- **Format**: `uv run ruff format .`
- **Type check**: `uv run mypy analyzer/ mcp_server/ cli.py config.py --ignore-missing-imports`

Test command: `uv sync --dev && uv run pytest && uv run ruff check . && uv run mypy analyzer/ mcp_server/ cli.py config.py --ignore-missing-imports`

## Where things live

- **Conference information** (conferences, CFPs, deadlines, attendance, contacts, speaking record, travel): read it from `peopleforrester/conference-knowledge` (`events/cfp_pipeline.yaml`, `events/registry.yaml`, `speaking/`, `travel/`). Don't keep a copy here; to change it, file an `agent-task` issue on that repo.
