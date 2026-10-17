# ABOUTME: Shared fixtures for the end-to-end suite against live services.
# ABOUTME: Fails loudly when the Anthropic API key these tests need is missing.

from __future__ import annotations

import os

import pytest


@pytest.fixture
def anthropic_api_key() -> str:
    """Require a real Anthropic API key; fail with a clear message without one."""
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        pytest.fail(
            "ANTHROPIC_API_KEY is not set. The E2E suite calls the real Claude API; "
            "export a key before running `uv run pytest tests_e2e`.",
            pytrace=False,
        )
    return key
