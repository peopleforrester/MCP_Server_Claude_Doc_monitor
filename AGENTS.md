# MCP Server Claude Doc monitor

Training content drift detection system

**Stack**: Python, Anthropic SDK, GitHub Actions

## Commands

- **Install**: `uv sync --dev`
- **Test**: `uv run pytest`
- **E2E (live docs)**: `uv run pytest tests_e2e`
- **API suite (needs `ANTHROPIC_API_KEY`)**: `uv run pytest tests_api`
- **Lint**: `uv run ruff check .`
- **Format**: `uv run ruff format .`
- **Type check**: `uv run mypy analyzer/ mcp_server/ cli.py config.py --ignore-missing-imports`

Test command: `uv sync --dev && uv run pytest && uv run ruff check . && uv run mypy analyzer/ mcp_server/ cli.py config.py --ignore-missing-imports`

E2E command: `uv sync --dev && uv run pytest tests_e2e`

The E2E suite (`tests_e2e/`, outside pytest's default `testpaths`) fetches and parses the real docs and release notes on platform.claude.com. It needs network access and no API key, and fails with a clear message when the pages can't be fetched.

Claude API analysis is not part of the E2E command, because the gate holds no provider API key (see decisions.md, question 255). It lives in the API suite (`tests_api/`, also outside `testpaths`): two tests that analyze a claim against a live doc page with the real Claude API, directly and through the CLI. It needs network access and `ANTHROPIC_API_KEY`, and fails with a clear message when the key is missing. It is meant to run in a GitHub Actions workflow that reads the key from the `ANTHROPIC_API_KEY` repo secret; until that workflow exists, run it by hand with the key exported: `uv run pytest tests_api`.

## Where things live

- **Conference information** (conferences, CFPs, deadlines, attendance, contacts, speaking record, travel): read it from `peopleforrester/conference-knowledge` (`events/cfp_pipeline.yaml`, `events/registry.yaml`, `speaking/`, `travel/`). Don't keep a copy here; to change it, file an `agent-task` issue on that repo.
