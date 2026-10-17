# MCP Server Claude Doc monitor

Training content drift detection system

**Stack**: Python, Anthropic SDK, GitHub Actions

## Commands

- **Install**: `uv sync --dev`
- **Test**: `uv run pytest`
- **E2E (live services)**: `uv run pytest tests_e2e`
- **Lint**: `uv run ruff check .`
- **Format**: `uv run ruff format .`
- **Type check**: `uv run mypy analyzer/ mcp_server/ cli.py config.py --ignore-missing-imports`

Test command: `uv sync --dev && uv run pytest && uv run ruff check . && uv run mypy analyzer/ mcp_server/ cli.py config.py --ignore-missing-imports`

E2E command: `uv sync --dev && uv run pytest tests_e2e`

The E2E suite (`tests_e2e/`, outside pytest's default `testpaths`) runs against live services: it fetches and parses the real docs and release notes on platform.claude.com, and it analyzes a claim with the real Claude API. It needs network access and `ANTHROPIC_API_KEY`, and fails with a clear message when the key is missing. Each run makes two small API calls.

## Where things live

- **Conference information** (conferences, CFPs, deadlines, attendance, contacts, speaking record, travel): read it from `peopleforrester/conference-knowledge` (`events/cfp_pipeline.yaml`, `events/registry.yaml`, `speaking/`, `travel/`). Don't keep a copy here; to change it, file an `agent-task` issue on that repo.
