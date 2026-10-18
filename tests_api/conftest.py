# ABOUTME: Shared fixtures for the API suite, which calls the real Claude API.
# ABOUTME: Fails loudly when the ANTHROPIC_API_KEY these tests need is missing.

from __future__ import annotations

import os

import pytest


@pytest.fixture
def anthropic_api_key() -> str:
    """Require a real Anthropic API key; fail with a clear message without one."""
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        pytest.fail(
            "ANTHROPIC_API_KEY is not set. The API suite calls the real Claude API; "
            "in CI it comes from the ANTHROPIC_API_KEY Actions secret, and by hand "
            "export a key before running `uv run pytest tests_api`.",
            pytrace=False,
        )
    return key
