# Changelog

## 1.1.2 — 2026-07-04

### Fixed

- **`freshness-check` and `freshness-mcp` console scripts now install.** The
  project had `[project.scripts]` but no `[build-system]`, so uv never built
  or installed the package and the documented commands did not exist. Added
  a hatchling build backend with an explicit wheel manifest (`cli.py`,
  `config.py`, `analyzer/`, `mcp_server/` — no tests or samples in the
  wheel). `uv sync` now installs the project in editable mode with both
  entry points on PATH.
- **Version now read from package metadata.** `cli._read_version()` uses
  `importlib.metadata` instead of parsing `pyproject.toml` relative to
  `__file__`, which would have broken for non-editable installs.
  pyproject.toml remains the single source of truth.

### Changed

- README commands use the console scripts (`uv run freshness-check`,
  `uv run freshness-mcp`), including the Claude Code MCP registration.
- New `tests/test_packaging.py` guards the entry-point registration and
  metadata/pyproject version agreement (133 tests total).
- `pydantic-settings` 2.14.1 → 2.14.2 (supersedes dependabot PR #11).

## 1.1.1 — 2026-06-18

Maintenance release: dependency refresh and documentation/configuration
modernization. No behavior changes to the analysis pipeline.

### Changed

- **Dependency upgrades** — `anthropic` 0.89 → 0.111, `mcp[cli]` 1.27 → 1.28,
  `click` 8.3 → 8.4, `tqdm` 4.67 → 4.68; dev tools `mypy` 1.19 → 2.1,
  `pytest` 9.0 → 9.1, `pytest-asyncio` 1.3 → 1.4, `ruff` 0.15.0 → 0.15.18.
  Transitive security patches pulled through (`idna`, `python-multipart`).
  All 128 tests pass; `ruff` and `mypy` clean against the new versions.
- **Documentation source URLs** migrated from the retired `docs.anthropic.com`
  domain to `platform.claude.com` in `config.json` / `config.example.json`.
- **Default analysis model** corrected to `claude-sonnet-4-6` in the local
  `config.json` (the previous `claude-sonnet-4-20250514` was retired
  2026-06-15). `config.py`'s built-in default was already current.
- **README** refreshed to match the v1.1.0 architecture: current project
  structure (new `analyzer/` modules and `mcp_server/server.py`), accurate
  test count, and `platform.claude.com` config examples.

## 1.1.0 — 2026-04-24

Major enhancement release. The project delivers on its `mcp_server/` name
(now a real MCP server), replaces regex claim extraction with a Claude-based
pipeline, and grounds every drift finding in verified citations from the
Anthropic Citations API.

### Added

- **MCP server** (`freshness-mcp` entry point) exposing `check_drift`,
  `search_docs`, and `get_changelog` as MCP tools plus a `docs://{topic}`
  resource. Ready to register with Claude Code or Claude Desktop.
- **LLM-based claim extraction** with SHA256-keyed caching at
  `~/.cache/freshness-check/extractions/` — unchanged input is free on re-run.
- **Citations API integration** — outdated claims in the report now carry
  blockquoted source excerpts with title, URL, and character range.
- **Prompt caching** on the system prompt and doc corpus (1h ephemeral TTL)
  so claims 2..N pay ~10% of baseline input cost.
- **Batch processing mode** (`--batch`) submitting analysis via the Anthropic
  Batches API at 50% discount.
- **Cost estimation** (`--dry-run`) — pre-flight input-token counts and
  dollar costs via the free `count_tokens` endpoint.
- **Changelog cross-reference** — after drift analysis, the pipeline flags
  claims affected by recent changelog entries (HIGH/MEDIUM/LOW severity).
- **`--fast` flag** preserves the regex extractor as a zero-API-cost fallback.
- **`--skip-changelog` flag** to bypass the changelog cross-reference step.
- New modules: `analyzer/claim_extractor.py`, `analyzer/batch_runner.py`,
  `analyzer/cost_estimator.py`, `analyzer/changelog_analyzer.py`,
  `mcp_server/server.py`.
- Test suite grew from 84 → 128+ tests covering every new module.

### Changed

- Drift analysis now sends docs as Citations API document blocks; the
  response carries verified pointers that populate `DriftResult.evidence`.
- Report generator renders the new evidence blockquotes and a "Recent
  Changelog Impact" section sorted by severity.
- CLI replaces ad-hoc percentage echoes with tqdm progress bars on doc
  fetching and claim analysis.
- README rewritten with flag reference, citation-output example, and MCP
  server registration instructions.

### Dependencies

- Added: `mcp[cli]>=1.27.0`, `tqdm>=4.67.3`.

## 1.0.3 — 2026-04-06

Senior-review remediation: model ID correction (`claude-sonnet-4-6`), doc
URL migration to `platform.claude.com`, concurrent doc fetching, typing
modernization, CI action SHA updates. See commits `fdaddfb..e055519`.
