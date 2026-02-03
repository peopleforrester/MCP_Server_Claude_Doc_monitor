# Drift Analysis Report

**Source File:** sample_input/outdated-training-doc.md
**Generated:** 2026-02-02 19:30:00

## Summary

Total claims analyzed: **11**

- Current: 3
- Potentially Stale: 1
- Outdated: 6
- Unverifiable: 1

## Analysis Results

| Section | Claim | Status | Notes |
|---------|-------|--------|-------|
| Available Models | Claude Instant supports up to 100k tokens. | OUTDATED | Claude 3 models now support 200k tokens |
| Context Windows | Claude supports a maximum context window of 100k tokens. | OUTDATED | Context window increased to 200k tokens |
| Context Windows | Claude can process up to 100,000 tokens in a single request. | OUTDATED | Now supports 200,000 tokens |
| API Usage | To make an API call, use the `/v1/complete` endpoint... | OUTDATED | Endpoint changed to /v1/messages |
| System Prompts | Use the `system` parameter to set the system prompt... | CURRENT | Verified against current API docs |
| Parameters | max_tokens_to_sample: Maximum output length | OUTDATED | Parameter renamed to max_tokens |
| Rate Limits | rate limit of 60 requests per minute | POTENTIALLY_STALE | Rate limits vary by tier and model |
| Vision Capabilities | Claude can analyze images. | CURRENT | Vision capability confirmed |
| Vision Capabilities | Pass images using base64 encoding in the `image` parameter. | OUTDATED | Images now passed in content array |
| Best Practices | Claude supports up to 4096 tokens of output | CURRENT | Output limit confirmed |
| Pricing | Input: $11.02 per million tokens | UNVERIFIABLE | Pricing varies by model |

## Recommended Updates

### 1. Line 15: Available Models

**Current claim:** Claude Instant supports up to 100k tokens.

**Suggested update:** Claude 3 models support up to 200k tokens in context window.

**Reference:** https://docs.anthropic.com/en/docs/about-claude/models

### 2. Line 22: Context Windows

**Current claim:** Claude supports a maximum context window of 100k tokens.

**Suggested update:** Claude supports a maximum context window of 200k tokens.

**Reference:** https://docs.anthropic.com/en/docs/about-claude/models

### 3. Line 24: Context Windows

**Current claim:** When working with long documents, Claude can process up to 100,000 tokens in a single request.

**Suggested update:** Claude can process up to 200,000 tokens in a single request.

**Reference:** https://docs.anthropic.com/en/docs/about-claude/models

### 4. Line 29: API Usage

**Current claim:** To make an API call, use the `/v1/complete` endpoint with your prompt in the `prompt` parameter.

**Suggested update:** Use the `/v1/messages` endpoint with the messages array format.

**Reference:** https://docs.anthropic.com/en/api/messages

### 5. Line 44: Parameters

**Current claim:** max_tokens_to_sample: Maximum output length (default: 256)

**Suggested update:** Use `max_tokens` parameter to set maximum output length.

**Reference:** https://docs.anthropic.com/en/api/messages

### 6. Line 60: Vision Capabilities

**Current claim:** Pass images using base64 encoding in the `image` parameter.

**Suggested update:** Pass images as content blocks with type "image" containing base64 data or URL.

**Reference:** https://docs.anthropic.com/en/docs/build-with-claude/vision

## Potentially Stale (Manual Review Recommended)

- Line 50: The API has a rate limit of 60 requests per minute for the free tier.

## Unverifiable Claims

*These claims could not be verified against current documentation:*

- Line 66: Claude API pricing is based on tokens: Input: $11.02 per million tokens
