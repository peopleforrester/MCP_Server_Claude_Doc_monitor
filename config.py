# ABOUTME: Configuration management for the content freshness system.
# ABOUTME: Loads doc sources and settings from JSON config files.

"""
Configuration Module for Content Freshness System
==================================================

This module handles all configuration for the drift detection system. It provides:
1. Default configuration values that work out of the box
2. The ability to override defaults via a JSON config file
3. A caching mechanism to avoid re-reading config files repeatedly
4. Type-safe access to configuration values via getter functions

The configuration controls:
- doc_sources: URLs of Anthropic documentation pages to fetch and compare against
- changelog_url: URL of the Anthropic changelog for detecting recent changes
- fetch_timeout: How long to wait (in seconds) when fetching documentation
- analysis_model: Which Claude model to use for analyzing claims

Architecture Pattern: This module uses the "Configuration Object" pattern, where all
settings are centralized in a single place and accessed through a clean API.
"""

# =============================================================================
# IMPORTS
# =============================================================================

# json: Standard library module for parsing JSON files. We use it to read
# user configuration from config.json files.
import json

# logging: Standard library module for diagnostic output.
# Used to warn about config file issues without crashing.
import logging

# dataclass: A decorator that automatically generates __init__, __repr__, etc.
# for classes that are primarily used to store data. Makes our Config class cleaner.
from dataclasses import dataclass

# Path: Object-oriented filesystem path handling. Better than string manipulation
# for working with file paths across different operating systems.
from pathlib import Path

# Type hints: Dict, Optional, Any are used for type annotations which help
# catch bugs early and make the code self-documenting.
# - Dict[str, str]: A dictionary with string keys and string values
# - Optional[X]: Either X or None
# - Any: Any type (used when the type is complex or varies)
from typing import Dict, Optional, Any

# Module-level logger for configuration warnings and errors.
logger = logging.getLogger(__name__)

# =============================================================================
# DEFAULT CONFIGURATION
# =============================================================================

# DEFAULT_CONFIG is a dictionary containing all the default settings.
# This ensures the system works even without a config file.
# The Dict[str, Any] type hint means string keys with values of any type.
DEFAULT_CONFIG: Dict[str, Any] = {
    # doc_sources: Maps topic names (keys) to documentation URLs (values).
    # These are the official Anthropic documentation pages we'll fetch
    # and use as the "source of truth" when checking if claims are current.
    #
    # Naming convention: We use lowercase with hyphens to match URL patterns.
    # This makes it easy to map topics to URLs programmatically.
    "doc_sources": {
        # API Documentation - Core endpoint and usage documentation
        "api-getting-started": "https://docs.anthropic.com/en/api/getting-started",
        "api-messages": "https://docs.anthropic.com/en/api/messages",
        "api-messages-streaming": "https://docs.anthropic.com/en/api/messages-streaming",
        "api-rate-limits": "https://docs.anthropic.com/en/api/rate-limits",
        "api-errors": "https://docs.anthropic.com/en/api/errors",
        "api-versioning": "https://docs.anthropic.com/en/api/versioning",

        # Model Documentation - Information about Claude models and capabilities
        "models-overview": "https://docs.anthropic.com/en/docs/about-claude/models",
        "models-compare": "https://docs.anthropic.com/en/docs/about-claude/models/model-comparison",

        # Feature Documentation - Specific Claude features and how to use them
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

        # Pricing Information - Token costs and pricing tiers
        "pricing": "https://docs.anthropic.com/en/docs/about-claude/pricing",
    },

    # changelog_url: The Anthropic changelog page where they announce updates.
    # This can be used to check for recent changes that might affect claims.
    "changelog_url": "https://docs.anthropic.com/en/docs/resources/changelog",

    # fetch_timeout: Maximum time (in seconds) to wait when fetching a doc page.
    # 45 seconds is generous but prevents hanging on slow/unresponsive servers.
    "fetch_timeout": 45,

    # analysis_model: The Claude model identifier used for drift analysis.
    # claude-sonnet-4 is chosen for its balance of speed and accuracy.
    "analysis_model": "claude-sonnet-4-20250514",
}


# =============================================================================
# CONFIG DATA CLASS
# =============================================================================

# @dataclass is a decorator that auto-generates boilerplate code.
# It creates __init__(), __repr__(), __eq__() and more based on the class attributes.
# This makes it easy to create simple data containers without writing repetitive code.
@dataclass
class Config:
    """
    Configuration for the content freshness system.

    This dataclass holds all configuration values in a type-safe container.
    Using a dataclass instead of a raw dictionary provides:
    1. Type checking: IDE and mypy can verify correct usage
    2. Attribute access: config.doc_sources instead of config["doc_sources"]
    3. Immutability: Harder to accidentally modify configuration
    4. Documentation: Each field is clearly defined with its type

    Attributes:
        doc_sources: Mapping of topic names to their documentation URLs.
        changelog_url: URL to the Anthropic changelog page.
        fetch_timeout: Timeout in seconds for HTTP requests.
        analysis_model: Claude model ID to use for analysis.
    """

    # Each attribute declaration defines both the name and expected type.
    # Dict[str, str] means a dictionary with string keys and string values.
    doc_sources: Dict[str, str]

    # str type for simple string values
    changelog_url: str

    # int type for whole numbers (seconds)
    fetch_timeout: int

    # str type for the model identifier
    analysis_model: str


# =============================================================================
# CONFIGURATION LOADING
# =============================================================================

def load_config(config_path: Optional[Path] = None) -> Config:
    """
    Load configuration from a JSON file, merging with defaults.

    This function implements a common pattern called "configuration with defaults":
    1. Start with a copy of the default configuration
    2. If a config file is provided and exists, read it
    3. Override only the values that are specified in the file
    4. Return the merged configuration

    This approach ensures:
    - The system always works, even without a config file
    - Users only need to specify values they want to change
    - New config options can be added without breaking existing configs

    Args:
        config_path: Path to the config file. If None or file doesn't exist,
                     returns default configuration.

    Returns:
        Config object with loaded or default values.

    Example config.json:
        {
            "doc_sources": {"my-topic": "https://example.com/docs"},
            "fetch_timeout": 60
        }

    Note: If the config file has syntax errors, defaults are used silently.
    This prevents crashes but may hide configuration problems.
    """
    # Create a copy of defaults to avoid modifying the original.
    # dict.copy() creates a shallow copy - sufficient since we replace values, not mutate them.
    config_data = DEFAULT_CONFIG.copy()

    # Check if a config path was provided AND the file actually exists.
    # Using 'and' short-circuits: if config_path is None, exists() is never called.
    if config_path and config_path.exists():
        try:
            # Open and read the JSON file.
            # Using 'with' ensures the file is properly closed even if an error occurs.
            with open(config_path) as f:
                # json.load() reads from a file object and parses JSON into a Python dict.
                # This is different from json.loads() which parses a string.
                user_config = json.load(f)

            # Merge user config with defaults by selectively overwriting.
            # We check each key individually rather than doing a blind update
            # to maintain control over which keys are valid.

            # Check if user specified doc_sources
            if "doc_sources" in user_config:
                # Completely replace the default doc_sources with user's version.
                # We don't merge individual URLs because the user might want
                # to use a completely different set of documentation sources.
                config_data["doc_sources"] = user_config["doc_sources"]

            # Check and override other settings if specified
            if "changelog_url" in user_config:
                config_data["changelog_url"] = user_config["changelog_url"]

            if "fetch_timeout" in user_config:
                config_data["fetch_timeout"] = user_config["fetch_timeout"]

            if "analysis_model" in user_config:
                config_data["analysis_model"] = user_config["analysis_model"]

        except (json.JSONDecodeError, IOError) as e:
            # json.JSONDecodeError: The file exists but isn't valid JSON
            # IOError: Some other file reading error occurred
            #
            # Log a warning so users know their config isn't being used.
            # Falls back to defaults to keep the system working.
            logger.warning(
                "Failed to load config from %s: %s. Using defaults.",
                config_path, e
            )

    # Create and return the Config dataclass instance.
    # We explicitly pass each field to make it clear what we're setting.
    return Config(
        doc_sources=config_data["doc_sources"],
        changelog_url=config_data["changelog_url"],
        fetch_timeout=config_data["fetch_timeout"],
        analysis_model=config_data["analysis_model"],
    )


# =============================================================================
# CONFIGURATION CACHING
# =============================================================================

# Module-level cache variables for the configuration.
# These are global to the module (prefixed with _ to indicate internal use).
#
# Why cache? Loading and parsing a JSON file every time we need a config value
# would be wasteful. Instead, we load once and reuse.

# Stores the cached Config object, or None if not yet loaded
_cached_config: Optional[Config] = None

# Stores which config file path was used for the cache.
# This allows us to invalidate the cache if a different file is requested.
_cached_config_path: Optional[Path] = None


def _get_config(config_path: Optional[Path] = None) -> Config:
    """
    Get config, using cache when possible.

    This is an internal function (prefix _ indicates private) that handles
    the caching logic. It implements the "lazy loading with invalidation" pattern:
    1. On first call, load the config and cache it
    2. On subsequent calls with the same path, return cached version
    3. If a different path is requested, invalidate cache and reload

    The 'global' keyword allows this function to modify module-level variables.
    Without it, assigning to _cached_config would create a local variable instead.

    Args:
        config_path: Optional path to config file.

    Returns:
        Cached or freshly loaded Config object.
    """
    # Declare that we're using the global variables, not creating local ones.
    # This is required because we're assigning to these variables.
    global _cached_config, _cached_config_path

    # Cache invalidation check:
    # 1. If a different config path is requested than what's cached
    # 2. OR if no config has been cached yet
    # Then we need to (re)load the configuration.
    if config_path != _cached_config_path or _cached_config is None:
        # Load the configuration from the file (or defaults)
        _cached_config = load_config(config_path)
        # Remember which path we used so we can check for changes
        _cached_config_path = config_path

    # Return the cached configuration
    return _cached_config


# =============================================================================
# PUBLIC GETTER FUNCTIONS
# =============================================================================

# These functions provide a clean API for accessing configuration values.
# Instead of: config = load_config(); urls = config.doc_sources
# You can do: urls = get_doc_sources()
#
# Benefits:
# 1. Simpler API for common use cases
# 2. Automatically uses caching
# 3. Type hints on return values help IDE autocompletion

def get_doc_sources(config_path: Optional[Path] = None) -> Dict[str, str]:
    """
    Get the configured documentation sources.

    Returns a dictionary mapping topic names (like "api-messages") to their
    corresponding documentation URLs. These URLs are fetched and parsed to
    get the current state of Claude documentation.

    Args:
        config_path: Optional path to config file. If not provided, uses
                     the default config.json in current directory if it exists,
                     otherwise uses built-in defaults.

    Returns:
        Dictionary mapping topic names to URLs.
        Example: {"api-messages": "https://docs.anthropic.com/en/api/messages"}
    """
    return _get_config(config_path).doc_sources


def get_changelog_url(config_path: Optional[Path] = None) -> str:
    """
    Get the configured changelog URL.

    The changelog is where Anthropic announces updates to Claude's capabilities,
    API changes, and other important information. This URL is used by the
    get_changelog.py tool to fetch recent changes.

    Args:
        config_path: Optional path to config file.

    Returns:
        Changelog URL string.
    """
    return _get_config(config_path).changelog_url


def get_fetch_timeout(config_path: Optional[Path] = None) -> int:
    """
    Get the configured fetch timeout in seconds.

    This timeout applies to HTTP requests when fetching documentation pages.
    A longer timeout (like the default 45 seconds) is more reliable for slow
    connections, but means the program takes longer to fail if a server is down.

    Args:
        config_path: Optional path to config file.

    Returns:
        Timeout value in seconds (integer).
    """
    return _get_config(config_path).fetch_timeout


def get_analysis_model(config_path: Optional[Path] = None) -> str:
    """
    Get the configured Claude model for analysis.

    This specifies which Claude model to use when analyzing claims for drift.
    Different models have different capabilities, speeds, and costs.
    The default (claude-sonnet-4) balances accuracy with response speed.

    Model ID format: "claude-{variant}-{version}-{date}"
    - variant: haiku, sonnet, opus (increasing capability/cost)
    - version: major version number
    - date: YYYYMMDD release date

    Args:
        config_path: Optional path to config file.

    Returns:
        Model identifier string (e.g., "claude-sonnet-4-20250514").
    """
    return _get_config(config_path).analysis_model
