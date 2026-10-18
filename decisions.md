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

## 2026-10-19 · question 256: README testing section wording

Question 256 (issue #31): may the README (public prose) be edited to refresh
the test count to 151 and to mention the E2E suite (`uv run pytest tests_e2e`)
in the project structure and the Development section, once #28 lands?

Answer: Approve the wording above; apply it after #28's branch lands (default).
Decided by the coordinator under Michael's standing rules, not by Michael.

What it changes: README.md now lists `tests/` as 151 unit and integration
tests (mocked; no network), adds `tests_e2e/`, and shows `uv run pytest
tests_e2e` in the Development section. One factual deviation from the approved
wording: it said the E2E suite covers the Claude API and needs
`ANTHROPIC_API_KEY`, but #28 landed with a keyless suite (see the 2026-10-18
entry above), so the README describes it as live docs and release notes,
needing network and no API key.
