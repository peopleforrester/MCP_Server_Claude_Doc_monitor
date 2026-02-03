# ABOUTME: Configuration management for the content freshness system.
# ABOUTME: Loads doc sources and settings from JSON config files.

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Any


# Default configuration values
DEFAULT_CONFIG: Dict[str, Any] = {
    "doc_sources": {
        "api-getting-started": "https://docs.anthropic.com/en/api/getting-started",
        "api-messages": "https://docs.anthropic.com/en/api/messages",
        "api-messages-streaming": "https://docs.anthropic.com/en/api/messages-streaming",
        "api-rate-limits": "https://docs.anthropic.com/en/api/rate-limits",
        "api-errors": "https://docs.anthropic.com/en/api/errors",
        "api-versioning": "https://docs.anthropic.com/en/api/versioning",
        "models-overview": "https://docs.anthropic.com/en/docs/about-claude/models",
        "models-compare": "https://docs.anthropic.com/en/docs/about-claude/models/model-comparison",
        "context-windows": "https://docs.anthropic.com/en/docs/build-with-claude/context-windows",
        "vision": "https://docs.anthropic.com/en/docs/build-with-claude/vision",
        "pdf-support": "https://docs.anthropic.com/en/docs/build-with-claude/pdf-support",
        "prompt-caching": "https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching",
        "tool-use": "https://docs.anthropic.com/en/docs/build-with-claude/tool-use",
        "system-prompts": "https://docs.anthropic.com/en/docs/build-with-claude/system-prompts",
        "streaming": "https://docs.anthropic.com/en/docs/build-with-claude/streaming",
        "token-counting": "https://docs.anthropic.com/en/docs/build-with-claude/token-counting",
        "extended-thinking": "https://docs.anthropic.com/en/docs/build-with-claude/extended-thinking",
        "multilingual": "https://docs.anthropic.com/en/docs/build-with-claude/multilingual",
        "pricing": "https://docs.anthropic.com/en/docs/about-claude/pricing",
    },
    "changelog_url": "https://docs.anthropic.com/en/docs/resources/changelog",
    "fetch_timeout": 45,
    "analysis_model": "claude-sonnet-4-20250514",
}


@dataclass
class Config:
    """Configuration for the content freshness system."""

    doc_sources: Dict[str, str]
    changelog_url: str
    fetch_timeout: int
    analysis_model: str


def load_config(config_path: Optional[Path] = None) -> Config:
    """
    Load configuration from a JSON file.

    Args:
        config_path: Path to the config file. If None or file doesn't exist,
                     returns default configuration.

    Returns:
        Config object with loaded or default values.
    """
    config_data = DEFAULT_CONFIG.copy()

    if config_path and config_path.exists():
        try:
            with open(config_path) as f:
                user_config = json.load(f)

            # Merge user config with defaults
            if "doc_sources" in user_config:
                config_data["doc_sources"] = user_config["doc_sources"]
            if "changelog_url" in user_config:
                config_data["changelog_url"] = user_config["changelog_url"]
            if "fetch_timeout" in user_config:
                config_data["fetch_timeout"] = user_config["fetch_timeout"]
            if "analysis_model" in user_config:
                config_data["analysis_model"] = user_config["analysis_model"]

        except (json.JSONDecodeError, IOError):
            # Fall back to defaults on error
            pass

    return Config(
        doc_sources=config_data["doc_sources"],
        changelog_url=config_data["changelog_url"],
        fetch_timeout=config_data["fetch_timeout"],
        analysis_model=config_data["analysis_model"],
    )


# Module-level cached config
_cached_config: Optional[Config] = None
_cached_config_path: Optional[Path] = None


def _get_config(config_path: Optional[Path] = None) -> Config:
    """Get config, using cache when possible."""
    global _cached_config, _cached_config_path

    if config_path != _cached_config_path or _cached_config is None:
        _cached_config = load_config(config_path)
        _cached_config_path = config_path

    return _cached_config


def get_doc_sources(config_path: Optional[Path] = None) -> Dict[str, str]:
    """
    Get the configured documentation sources.

    Args:
        config_path: Optional path to config file.

    Returns:
        Dictionary mapping topic names to URLs.
    """
    return _get_config(config_path).doc_sources


def get_changelog_url(config_path: Optional[Path] = None) -> str:
    """
    Get the configured changelog URL.

    Args:
        config_path: Optional path to config file.

    Returns:
        Changelog URL string.
    """
    return _get_config(config_path).changelog_url


def get_fetch_timeout(config_path: Optional[Path] = None) -> int:
    """
    Get the configured fetch timeout in seconds.

    Args:
        config_path: Optional path to config file.

    Returns:
        Timeout value in seconds.
    """
    return _get_config(config_path).fetch_timeout


def get_analysis_model(config_path: Optional[Path] = None) -> str:
    """
    Get the configured Claude model for analysis.

    Args:
        config_path: Optional path to config file.

    Returns:
        Model identifier string.
    """
    return _get_config(config_path).analysis_model
