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

## 2026-10-19 · question 255: how ANTHROPIC_API_KEY reaches the API tests

Question 255 (issue #30): how should `ANTHROPIC_API_KEY` reach the environment
that runs the tests calling the real Claude API (two calls per run,
claude-sonnet-5 on one ~12k-char doc page)?

Answer: add it as a GitHub Actions repo secret and run the E2E suite in a CI
workflow (that also means a CI workflow change for Michael). This follows the
2026-10-14 rule that provider-key jobs run on CI, and the Engineering_Journal
and llm-coding-workflow convention; the gate env keeps no secret.

Decided by the coordinator under Michael's standing rules, not by Michael.

What it changes: the two API tests from the first draft of #28 come back as
their own suite, `tests_api/`, outside both pytest's default `testpaths` and
the E2E command, so neither the Test command nor the keyless heavy gate ever
needs the key. The E2E command stays `uv sync --dev && uv run pytest tests_e2e`.
`tests_api/` fails with a clear message when the key is missing. Creating the
`ANTHROPIC_API_KEY` repo secret and adding the CI workflow that runs
`uv run pytest tests_e2e tests_api` with it are left to Michael (secrets and CI
workflows wait for him). Until they land, `uv run pytest tests_api` with the key
exported replaces the by-hand CLI check in the 2026-10-18 entry above.
