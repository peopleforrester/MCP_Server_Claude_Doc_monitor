# Todo — v1.1.0 Enhancement

**See plan.md for context and code-gen prompts.**

## Phase 1 — Claude-Based Claim Extraction
- [ ] 1.1 Write failing tests for `ExtractedClaim` + `extract_claims_with_llm()`
- [ ] 1.2 Implement LLM extraction with batched sections per call
- [ ] 1.3 Add SHA256-keyed cache at `~/.cache/freshness-check/extractions/`
- [ ] 1.4 Wire `--fast` CLI flag preserving regex path
- [ ] 1.5 Add tqdm progress indicator
- [ ] Commit: "Add Claude-based claim extraction with hash-keyed caching"

## Phase 2 — Citations-Powered Analysis
- [ ] 2.1 Document-block formatter with citations enabled
- [ ] 2.2 Citation parsing → `CitedEvidence` list on `DriftResult`
- [ ] 2.3 Report renderer for cited evidence as blockquotes
- [ ] 2.4 Chunking for docs >80KB
- [ ] Commit: "Use Citations API for verified drift evidence"

## Phase 3 — Prompt Caching + Batch Mode
- [ ] 3.1 Add `cache_control` (ephemeral, 3600s) to system prompt + last doc block
- [ ] 3.2 Log cache metrics in verbose mode
- [ ] 3.3 Implement `batch_runner.submit_claims()`
- [ ] 3.4 Implement `poll_until_complete()` with tqdm
- [ ] 3.5 Wire `--batch` CLI flag
- [ ] Commit: "Add prompt caching and opt-in batch processing mode"

## Phase 4 — MCP Server Wiring
- [ ] 4.1 Add `mcp[cli]` dependency + FastMCP skeleton
- [ ] 4.2 Register `check_drift` tool
- [ ] 4.3 Register `search_docs` tool
- [ ] 4.4 Register `get_changelog` tool
- [ ] 4.5 Register `docs://{topic}` resource
- [ ] 4.6 Add `freshness-mcp` entry point + README section
- [ ] Commit: "Wire up MCP server with tools and resources"

## Phase 5 — Token Counting + Dry-Run
- [ ] 5.1 `cost_estimator.estimate_cost()` using `count_tokens` API
- [ ] 5.2 `--dry-run` flag
- [ ] 5.3 `--estimate-cost` flag with confirmation prompt
- [ ] Commit: "Add cost estimation and --dry-run mode"

## Phase 6 — Changelog Cross-Reference
- [ ] 6.1 `changelog_analyzer.analyze_changelog_impact()`
- [ ] 6.2 Pipeline integration + `--skip-changelog` flag
- [ ] 6.3 Report section for changelog impacts
- [ ] Commit: "Cross-reference claims against recent changelog entries"

## Phase 7 — Release
- [ ] 7.1 End-to-end integration test with fixture doc
- [ ] 7.2 Update README (MCP setup, flags, citation format)
- [ ] 7.3 Bump version 1.0.3 → 1.1.0, CHANGELOG entry
- [ ] 7.4 Merge staging → main, tag v1.1.0

## Verification
- Test baseline before Phase 1: 84 tests passing
- Target after Phase 7: 120+ tests passing
- Ruff + mypy clean at every commit
