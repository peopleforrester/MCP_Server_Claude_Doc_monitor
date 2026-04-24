# Todo — v1.1.0 Enhancement

**See plan.md for context and code-gen prompts.**

## Phase 1 — Claude-Based Claim Extraction ✅
- [x] 1.1 Write failing tests for `ExtractedClaim` + `extract_claims_with_llm()`
- [x] 1.2 Implement LLM extraction with batched sections per call
- [x] 1.3 Add SHA256-keyed cache at `~/.cache/freshness-check/extractions/`
- [x] 1.4 Wire `--fast` CLI flag preserving regex path
- [x] 1.5 Add tqdm progress indicator (tqdm.asyncio for doc fetch + analyze)
- [x] Commit: "Add Claude-based claim extraction with hash-keyed caching"

## Phase 2 — Citations-Powered Analysis ✅
- [x] 2.1 Document-block formatter with citations enabled
- [x] 2.2 Citation parsing → `CitedEvidence` list on `DriftResult`
- [x] 2.3 Report renderer for cited evidence as blockquotes
- [x] 2.4 Chunking for docs >80KB (paragraph-boundary splits)
- [x] Commit: "Use Citations API for verified drift evidence"

## Phase 3 — Prompt Caching + Batch Mode ✅
- [x] 3.1 Add `cache_control` (ephemeral, 1h) to system prompt + last doc block
- [x] 3.2 Log cache metrics at INFO in verbose mode
- [x] 3.3 Implement `batch_runner.build_batch_requests()` + `analyze_claims_batch()`
- [x] 3.4 Implement `poll_until_complete()` with progress_cb
- [x] 3.5 Wire `--batch` CLI flag
- [x] Commit: "Add prompt caching and opt-in batch processing mode"

## Phase 4 — MCP Server Wiring ✅
- [x] 4.1 Add `mcp[cli]` dependency + FastMCP skeleton
- [x] 4.2 Register `check_drift` tool
- [x] 4.3 Register `search_docs` tool
- [x] 4.4 Register `get_changelog` tool
- [x] 4.5 Register `docs://{topic}` resource
- [x] 4.6 Add `freshness-mcp` entry point + README section
- [x] Commit: "Wire up MCP server with tools and resources"

## Phase 5 — Token Counting + Dry-Run ✅
- [x] 5.1 `cost_estimator.estimate_cost()` using `count_tokens` API
- [x] 5.2 `--dry-run` flag
- [ ] 5.3 `--estimate-cost` flag with confirmation prompt (dropped — `--dry-run` then re-run covers the same workflow)
- [x] Commit: "Add cost estimation and --dry-run mode"

## Phase 6 — Changelog Cross-Reference ✅
- [x] 6.1 `changelog_analyzer.analyze_changelog_impact()` — single Claude call across all claims × entries
- [x] 6.2 Pipeline integration + `--skip-changelog` flag
- [x] 6.3 Report section for changelog impacts (sorted HIGH → MEDIUM → LOW)
- [x] Commit: "Cross-reference claims against recent changelog entries"

## Phase 7 — Release
- [ ] 7.1 End-to-end integration test with fixture doc
- [ ] 7.2 Update README (MCP setup, flags, citation format)
- [ ] 7.3 Bump version 1.0.3 → 1.1.0, CHANGELOG entry
- [ ] 7.4 Merge staging → main, tag v1.1.0

## Verification
- Test baseline before Phase 1: 84 tests passing
- Target after Phase 7: 120+ tests passing
- Ruff + mypy clean at every commit
