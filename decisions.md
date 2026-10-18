<!-- ABOUTME: Append-only decision log for the MCP Server Claude Doc monitor repo. -->
<!-- ABOUTME: Never edit a prior entry; correct it with a new one. -->

## 2026-10-18 · Claude API analysis is a by-hand check, not part of the E2E command

The E2E command (`uv sync --dev && uv run pytest tests_e2e`, issue #28) runs
only the live tests that need no API key: fetching and parsing the real docs
and release notes on platform.claude.com.

A first draft also gated on two tests that analyze a claim with the real
Claude API. They need `ANTHROPIC_API_KEY`, which the heavy gate never holds,
and metered API calls are kept for media work, so the E2E command would stay
red. Following the precedent recorded on task-management-strategic-portal#7
(also applied in tools-knowledge#6, sageheart-knowledge#19 and
dragon_in_space#26), a suite the heavy gate cannot run comes out of the gated
command and becomes a documented by-hand check.

By-hand check, after changes to `analyzer/` or the CLI pipeline: with
`ANTHROPIC_API_KEY` exported, run
`uv run python cli.py sample_input/outdated-training-doc.md --fast --skip-changelog`
and confirm it exits 0 and the report lists analyzed claims with drift statuses.
