# Drift Analysis Report

**Source File:** sample_input/outdated-training-doc.md
**Generated:** 2026-02-02 20:04:10

## Summary

Total claims analyzed: **11**

- Current: 4
- Potentially Stale: 0
- Outdated: 5
- Unverifiable: 2

## Analysis Results

| Section | Claim | Status | Notes |
|---------|-------|--------|-------|
| Getting Started | The API provides programmatic access to Claude's capabilitie... | CURRENT | The claim is directly supported by the current documentation. The API overview e |
| Available Models | Claude Instant supports up to 100k tokens. | OUTDATED | The claim states that Claude Instant supports up to 100k tokens, but the current |
| Context Windows | Claude supports a maximum context window of 100k tokens. | OUTDATED | The claim states Claude supports a maximum context window of 100k tokens, but th |
| Context Windows | When working with long documents, Claude can process up to 1... | OUTDATED | The claim states Claude can process up to 100,000 tokens in a single request, bu |
| System Prompts | Use the `system` parameter to set the system prompt in your ... | CURRENT | The claim is accurate. The prompt caching documentation shows a clear example of |
| Parameters | Key parameters for the completion API:
- `max_tokens_to_samp... | OUTDATED | The claim describes parameters from an older completion API format. The current  |
| Rate Limits | The API has a rate limit of 60 requests per minute for the f... | UNVERIFIABLE | The documentation contains a rate limits page that discusses rate limits in gene |
| Rate Limits | For enterprise customers, rate limits are 1000 requests per ... | UNVERIFIABLE | The documentation contains information about rate limits in general but does not |
| Vision Capabilities | Claude can analyze images. | CURRENT | The documentation clearly confirms that Claude can analyze images. The 'Vision'  |
| Vision Capabilities | The API supports vision capabilities for image analysis and ... | CURRENT | The documentation clearly confirms that the API supports vision capabilities for |
| Best Practices | Claude supports up to 4096 tokens of output per response
4. | OUTDATED | The claim states Claude supports up to 4096 tokens of output per response, but t |

## Recommended Updates

### 1. Line 15: Available Models

**Current claim:** Claude Instant supports up to 100k tokens.

**Suggested update:** Claude Instant is no longer available. Current models include Claude Sonnet 4.5, Claude Haiku 4.5, and Claude Opus 4.5, which support context windows of 200K tokens (with 1M tokens available in beta for Haiku 4.5).

**Reference:** https://docs.anthropic.com/en/docs/about-claude/models

### 2. Line 22: Context Windows

**Current claim:** Claude supports a maximum context window of 100k tokens.

**Suggested update:** Claude supports context windows of 200K tokens for most models, with Claude Haiku 4.5 supporting up to 1M tokens (beta).

**Reference:** https://docs.anthropic.com/en/docs/about-claude/models

### 3. Line 24: Context Windows

**Current claim:** When working with long documents, Claude can process up to 100,000 tokens in a single request.

**Suggested update:** When working with long documents, Claude can process up to 200,000 tokens in a single request for most models, with Claude Haiku 4.5 supporting up to 1 million tokens (beta).

**Reference:** https://docs.anthropic.com/en/docs/about-claude/models

### 4. Line 45: Parameters

**Current claim:** Key parameters for the completion API:
- `max_tokens_to_sample`: Maximum output length (default: 256)
- `temperature`: Controls randomness (0.0 to 1.0)
- `stop_sequences`: List of strings that stop generation

The API supports streaming responses via the `stream` parameter.

**Suggested update:** Key parameters for the Messages API:
- `max_tokens`: Maximum output length (required parameter)
- `temperature`: Controls randomness (0.0 to 1.0)
- `stop_sequences`: List of strings that stop generation

The API supports streaming responses via the `stream` parameter set to true.

**Reference:** https://docs.anthropic.com/en/api/getting-started

### 5. Line 71: Best Practices

**Current claim:** Claude supports up to 4096 tokens of output per response
4.

**Suggested update:** Claude supports up to 64,000 tokens of output per response

**Reference:** https://docs.anthropic.com/en/docs/about-claude/models

## Unverifiable Claims

*These claims could not be verified against current documentation:*

- Line 54: The API has a rate limit of 60 requests per minute for the free tier.
- Line 55: For enterprise customers, rate limits are 1000 requests per minute.
