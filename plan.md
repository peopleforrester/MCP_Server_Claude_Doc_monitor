# Enhancement Plan — Content Freshness System v1.1.0

**Created:** 2026-04-23
**Branch:** staging → main
**Status:** Awaiting approval before Phase 1 execution

## Intent

Take the project from "working CLI with stale regex extractor" to "the tool you'd actually recommend for keeping Claude training materials accurate." Measured by: accuracy of drift detection, trust (cited evidence), cost per run, and whether the stated `mcp_server/` purpose is fulfilled.

## Architecture Decisions

1. **Ordering principle** — each phase locks in an interface the next one builds on. No prompt churn, no rework.
2. **Regex stays as fallback** — `--fast` flag preserves the old extractor so users with zero budget can still run.
3. **Batch mode is opt-in** — sync remains default for interactive use; `--batch` is for large corpora.
4. **Caching keyed by content hash** — extraction results cached per-file by SHA256; doc fetches cached per-URL with 1-hour TTL.
5. **MCP transport** — `streamable-http` only. Skip legacy SSE.
6. **Phases commit independently** on staging; merge to main after Phase 7 validation.

## Data Model Changes

```python
# analyzer/claim_extractor.py (new)
@dataclass
class ExtractedClaim:
    text: str
    section: str
    line: int
    category: Literal["capability", "parameter", "limit", "pricing", "availability"]
    severity_hint: Literal["low", "medium", "high"]

# analyzer/drift_detector.py (additions)
@dataclass
class CitedEvidence:
    cited_text: str
    document_title: str
    document_url: str
    char_range: tuple[int, int]

@dataclass
class DriftResult:  # existing — extended
    # ... existing fields ...
    evidence: list[CitedEvidence] = field(default_factory=list)
```

---

## Phase 1 — Claude-Based Claim Extraction

**Why:** Regex is the wrong tool. It misses paraphrased claims, captures boilerplate noise, can't distinguish a claim about deprecated features from one about current behavior.

**Files:** `analyzer/claim_extractor.py` (new), `analyzer/input_handler.py` (keep regex path), `cli.py`

### Steps

**1.1 — Data model + module skeleton (TDD)**
- Write `tests/test_claim_extractor.py` with failing test: `extract_claims_with_llm()` returns `list[ExtractedClaim]` for a fixture markdown doc
- Implement `analyzer/claim_extractor.py` with dataclass and stub function raising `NotImplementedError`

**1.2 — Claude extraction, no cache**
- Write test: mock `AsyncAnthropic.messages.create`, assert prompt contains section text, assert structured response parsed into `ExtractedClaim` objects
- Implement using `effort: "low"`, structured JSON output, batched sections per API call (one call per doc, not per section)

**1.3 — File-hash cache layer**
- Write test: call extractor twice on same content, assert second call hits cache (no API call)
- Implement cache at `~/.cache/freshness-check/extractions/{sha256}.json` with schema version field

**1.4 — CLI wiring with --fast fallback**
- Write test: `--fast` flag uses regex path, default uses LLM path
- Add flag to `cli.py`, route through corresponding extractor

**1.5 — Progress indicator**
- Add `tqdm` progress bar during extraction (per user's global progress-indicator rule)

**Commit point:** "Add Claude-based claim extraction with hash-keyed caching"

### Prompt for Phase 1 execution

```text
Implement Phase 1 of plan.md: Claude-based claim extraction.

Follow strict TDD:
1. Start by writing tests/test_claim_extractor.py with failing tests for:
   - extract_claims_with_llm() signature and return type
   - Cache hit on second call with same content
   - Structured parsing of fixture response
2. Create analyzer/claim_extractor.py with:
   - ExtractedClaim dataclass (text, section, line, category, severity_hint)
   - async extract_claims_with_llm(sections: list[Section], client: AsyncAnthropic) -> list[ExtractedClaim]
   - Cache at ~/.cache/freshness-check/extractions/{sha256}.json with version field
3. Wire into cli.py with --fast flag preserving regex path as fallback
4. Add tqdm progress indicator
5. Run: uv run pytest, uv run ruff check ., uv run mypy
6. Commit on staging with message describing the addition

Use effort="low" for extraction (recall task, not reasoning).
Batch all sections from one file into one API call.
Do not modify analyzer/drift_detector.py or report_generator.py in this phase.
```

---

## Phase 2 — Citations-Powered Drift Analysis

**Why:** Turns "possibly stale, see note" into "stale — the live doc says X at char 4523–4612, your training says Y." Biggest accuracy+trust unlock.

**Files:** `analyzer/drift_detector.py`, `analyzer/report_generator.py`, `tests/test_drift_analyzer.py`, `tests/test_report_generator.py`

### Steps

**2.1 — Document-block formatter**
- Write test: `_build_document_blocks(docs)` returns list with `type: document`, `source.type: text`, `citations.enabled: true`
- Implement, handle chunking for docs >80KB (safety margin below 100KB limit)

**2.2 — Citation extraction from response**
- Write test: given a fixture response with citations, `analyze_claim()` returns `DriftResult` with populated `evidence: list[CitedEvidence]`
- Implement parsing of `content[i].citations[*]` from Anthropic response

**2.3 — Report renderer for citations**
- Write test: report markdown contains blockquote with cited text and source URL for flagged claims
- Update `report_generator.to_markdown()` to render evidence under each flagged claim

**2.4 — Doc-chunking fallback**
- Write test: a 500KB doc produces multiple document blocks, citations across chunks are merged
- Implement with sensible boundary detection (split on `\n\n`)

**Commit point:** "Use Citations API for verified drift evidence"

### Prompt for Phase 2 execution

```text
Implement Phase 2 of plan.md: Citations API integration.

TDD order:
1. Extend tests/test_drift_analyzer.py with tests for:
   - _build_document_blocks returns proper document content blocks with citations enabled
   - Fixture response with citations produces populated evidence list
   - Doc >80KB splits into multiple blocks
2. Extend tests/test_report_generator.py with test for citation rendering
3. Update analyzer/drift_detector.py:
   - Add CitedEvidence dataclass
   - Extend DriftResult with evidence field
   - Refactor analyze_claim() to pass docs as document content blocks with citations.enabled=true
   - Parse citations from response.content[i].citations
4. Update analyzer/report_generator.py to render evidence as blockquotes
5. Run full test suite, ruff, mypy
6. Commit on staging

Preserve backward compat of DriftResult (evidence defaults to empty list).
```

---

## Phase 3 — Prompt Caching + Batch Mode

**Why:** Cost. System prompt + doc corpus is ~20–50KB and identical across all claims. Cached read at 0.1× × 50% batch discount ≈ 10× cheaper per run.

**Files:** `analyzer/drift_detector.py`, `cli.py`, new `analyzer/batch_runner.py`, tests

### Steps

**3.1 — Prompt caching on system prompt + doc blocks**
- Write test: assert `cache_control: {type: ephemeral, ttl: 3600}` appears on system prompt and last doc block
- Add cache_control to the request structure

**3.2 — Cache metrics logging**
- Write test: verbose mode logs cache_creation_input_tokens and cache_read_input_tokens after each call
- Implement logging in `analyze_claims()`

**3.3 — Batch submission path**
- Write test: `batch_runner.submit_claims(claims, docs)` returns batch_id, uses `client.messages.batches.create`
- Implement, preserve custom_id mapping back to Claim objects

**3.4 — Batch polling with progress**
- Write test: poll loop calls `batches.retrieve` until status="ended", tqdm updates by processed count
- Implement with reasonable polling interval (30s) and timeout (2h)

**3.5 — `--batch` CLI flag**
- Write test: `--batch` routes through `batch_runner` instead of sync path
- Wire through, produce same report output

**Commit point:** "Add prompt caching and opt-in batch processing mode"

### Prompt for Phase 3 execution

```text
Implement Phase 3 of plan.md: prompt caching + batch mode.

TDD order:
1. Add prompt caching test to tests/test_drift_analyzer.py:
   - Assert cache_control on system prompt and final doc block
   - Assert 1-hour TTL (ephemeral, 3600s)
2. Create tests/test_batch_runner.py with tests for:
   - submit_claims returns batch_id
   - custom_id mapping preserved
   - poll_until_complete handles status transitions
3. Create analyzer/batch_runner.py with:
   - async submit_claims(claims, docs, client) -> str (batch_id)
   - async poll_until_complete(batch_id, client, progress_cb) -> dict[custom_id, DriftResult]
4. Update cli.py with --batch flag
5. Add cache metrics to verbose output
6. Run tests + lint + type check
7. Commit on staging

Use ephemeral 1-hour cache (ttl=3600). Poll every 30s, time out at 2h.
```

---

## Phase 4 — Wire Up the Actual MCP Server

**Why:** The directory is named `mcp_server/` and it currently isn't one. Fulfills the stated purpose.

**Files:** `mcp_server/server.py` (new), `mcp_server/__init__.py`, `pyproject.toml`, tests

### Steps

**4.1 — FastMCP skeleton**
- Write test using mcp test client: server starts, lists three tools
- Create `mcp_server/server.py` with `FastMCP("DocMonitor")` and `main()` entrypoint

**4.2 — `check_drift` tool**
- Write test: tool accepts markdown string, returns JSON with claim analyses
- Register `@mcp.tool() async def check_drift(markdown: str) -> dict`

**4.3 — `search_docs` tool**
- Write test: returns ranked matches for query
- Wrap existing `search_docs` utility

**4.4 — `get_changelog` tool**
- Write test: returns entries filtered by days
- Wrap existing `get_changelog` utility

**4.5 — `docs://{topic}` resource**
- Write test: reading resource returns current doc content for topic
- Register `@mcp.resource("docs://{topic}")`

**4.6 — Entry point + docs**
- Add `freshness-mcp = mcp_server.server:main` to pyproject.toml scripts
- Add README section on MCP setup

**Commit point:** "Wire up MCP server with check_drift, search_docs, get_changelog tools"

### Prompt for Phase 4 execution

```text
Implement Phase 4 of plan.md: MCP server wiring.

TDD order:
1. Add mcp dependency: uv add "mcp[cli]"
2. Create tests/test_mcp_server.py using mcp's test client:
   - Server starts, lists check_drift, search_docs, get_changelog
   - Each tool invokes and returns expected shape
   - docs://{topic} resource returns content
3. Create mcp_server/server.py:
   - FastMCP("DocMonitor")
   - @mcp.tool() async def check_drift(markdown: str) -> dict
   - @mcp.tool() async def search_docs(query: str) -> list[dict]
   - @mcp.tool() async def get_changelog(days: int = 30) -> list[dict]
   - @mcp.resource("docs://{topic}") async def get_doc(topic: str) -> str
   - def main(): mcp.run(transport="streamable-http")
4. Update mcp_server/__init__.py to export server
5. Add freshness-mcp entry point to pyproject.toml
6. Update README.md with MCP setup instructions
7. Run tests, commit on staging
```

---

## Phase 5 — Token Counting + Dry-Run

**Why:** Users should know cost before paying. Small phase, high UX value. Satisfies user's "progress indicator" global rule for long operations.

**Files:** `cli.py`, `analyzer/cost_estimator.py` (new), tests

### Steps

**5.1 — Cost estimation function**
- Write test: given claims + docs, returns `{sync_cost_usd, batch_cost_usd, input_tokens, output_tokens_estimate}`
- Implement using `client.messages.count_tokens()`, multiply by current pricing from config

**5.2 — `--dry-run` flag**
- Write test: with `--dry-run`, extraction runs, estimation prints, no analysis API calls made
- Wire into cli.py

**5.3 — `--estimate-cost` flag**
- Write test: runs analysis but prints estimate first, prompts for confirmation
- Wire into cli.py

**Commit point:** "Add cost estimation and --dry-run mode"

### Prompt for Phase 5 execution

```text
Implement Phase 5 of plan.md: cost estimation.

TDD order:
1. Write tests/test_cost_estimator.py with tests for:
   - estimate_cost returns dict with sync_cost_usd, batch_cost_usd, tokens
   - Uses count_tokens API (mock it)
2. Create analyzer/cost_estimator.py with estimate_cost(claims, docs, model) function
3. Add pricing constants sourced from config (current Opus/Sonnet/Haiku prices)
4. Add --dry-run and --estimate-cost flags to cli.py
5. Run tests, commit on staging
```

---

## Phase 6 — Changelog Cross-Reference

**Why:** Drift detection should catch "Claude just deprecated X last week and your training still teaches X." Changelog tool exists but isn't wired into the pipeline.

**Files:** `analyzer/changelog_analyzer.py` (new), `cli.py`, `analyzer/report_generator.py`, tests

### Steps

**6.1 — Changelog-to-claims analysis**
- Write test: given claims + recent changelog entries, returns list of (claim, changelog_entry, relevance) tuples
- Implement with single Claude call using cached prompt

**6.2 — Pipeline integration**
- Write test: after drift analysis, changelog cross-check runs, report contains "Recent Changelog Impact" section
- Wire into `cli.py`, add `--skip-changelog` to disable

**6.3 — Report section**
- Write test: report renders changelog impacts grouped by severity
- Update `report_generator.py`

**Commit point:** "Cross-reference claims against recent changelog entries"

### Prompt for Phase 6 execution

```text
Implement Phase 6 of plan.md: changelog cross-reference.

TDD order:
1. Write tests/test_changelog_analyzer.py
2. Create analyzer/changelog_analyzer.py with:
   - async analyze_changelog_impact(claims, entries, client) -> list[ChangelogImpact]
3. Wire into cli.py after drift analysis
4. Add --skip-changelog flag
5. Update report_generator.py with new section
6. Run tests, commit on staging
```

---

## Phase 7 — Tests, Docs, Release

**Files:** `README.md`, `pyproject.toml`, full integration test, CHANGELOG

### Steps

**7.1 — End-to-end integration test**
- Fixture training doc with 5 known-stale + 5 known-current claims
- Full pipeline run (mocked APIs), assert report matches expected

**7.2 — README update**
- Document MCP server setup
- Document `--batch`, `--dry-run`, `--fast` flags
- Document citation output format
- Add "How it works" architecture diagram

**7.3 — Version bump**
- `pyproject.toml`: 1.0.3 → 1.1.0
- Add `CHANGELOG.md` entry

**7.4 — Merge staging → main**
- Verify all tests pass on staging
- Open PR staging → main
- Merge after approval

**Commit point:** "Release v1.1.0"

---

## Test Strategy

- **Unit tests first** for every new function (TDD)
- **Integration tests** per phase (end-to-end with mocked APIs)
- **Golden-file tests** for report output to catch formatting regressions
- **Never mock in unit tests what integration tests don't cover with real fixtures**

## Exit Criteria

- All 7 phases committed on staging
- Full test suite passing (target: 120+ tests)
- Ruff + mypy clean
- Manual smoke test: run against a known training doc, verify report quality
- Merged to main as v1.1.0

## Risks Flagged

1. **Smart extraction latency** — cache mitigates, keep `--fast` fallback
2. **Doc >100KB citation limit** — Phase 2 chunks; fallback to Files API if ugly
3. **Batch 1-hour wait** — opt-in only, default stays sync
4. **MCP test complexity** — use `mcp` SDK's test client, avoid real transport in tests
5. **Scope** — commit per phase; clean stopping points if we pause
