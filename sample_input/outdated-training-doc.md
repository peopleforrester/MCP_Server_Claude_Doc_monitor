# Introduction to Claude API

This training document covers the fundamentals of working with Anthropic's Claude API.

## Getting Started

Claude is Anthropic's AI assistant, designed to be helpful, harmless, and honest. The API provides programmatic access to Claude's capabilities.

## Model Selection

### Available Models

Claude comes in several variants:

- **Claude Instant**: The fastest model, ideal for simple tasks. Claude Instant supports up to 100k tokens.
- **Claude 2**: The balanced model for most use cases.
- **Claude 2.1**: Enhanced version with improved accuracy.

For production workloads, we recommend starting with Claude 2 and upgrading to Claude 2.1 if needed.

## Context Windows

Claude supports a maximum context window of 100k tokens. This is significantly larger than many other models.

When working with long documents, Claude can process up to 100,000 tokens in a single request.

## API Usage

### Basic Request Structure

To make an API call, use the `/v1/complete` endpoint with your prompt in the `prompt` parameter.

Use the `human_prompt` and `assistant_prompt` format for conversations:

```
Human: Hello!
Assistant: Hi there!
```

### System Prompts

Use the `system` parameter to set the system prompt in your API calls.

### Parameters

Key parameters for the completion API:
- `max_tokens_to_sample`: Maximum output length (default: 256)
- `temperature`: Controls randomness (0.0 to 1.0)
- `stop_sequences`: List of strings that stop generation

The API supports streaming responses via the `stream` parameter.

## Rate Limits

The API has a rate limit of 60 requests per minute for the free tier.

For enterprise customers, rate limits are 1000 requests per minute.

## Vision Capabilities

Claude can analyze images. The API supports vision capabilities for image analysis and understanding.

Pass images using base64 encoding in the `image` parameter.

## Best Practices

1. Keep prompts clear and specific
2. Use system prompts to set context
3. Claude supports up to 4096 tokens of output per response
4. Use streaming for long responses

## Pricing

Claude API pricing is based on tokens:
- Input: $11.02 per million tokens
- Output: $32.68 per million tokens

Pricing varies by model tier.
