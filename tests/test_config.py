# ABOUTME: Unit tests for configuration loading.
# ABOUTME: Tests loading doc sources from config files.

import json
import logging
from pathlib import Path

import pytest
from config import (
    load_config,
    get_doc_sources,
    get_changelog_url,
    get_fetch_timeout,
    get_analysis_model,
    DEFAULT_CONFIG,
    Config,
)


class TestLoadConfig:
    """Tests for loading configuration files."""

    def test_load_config_from_file(self, tmp_path: Path) -> None:
        """Should load config from a JSON file."""
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({
            "doc_sources": {"test": "https://example.com"},
            "changelog_url": "https://example.com/changelog"
        }))

        config = load_config(config_file)

        assert config.doc_sources == {"test": "https://example.com"}

    def test_load_config_returns_defaults_when_no_file(self) -> None:
        """Should return default config when file doesn't exist."""
        config = load_config(Path("/nonexistent/config.json"))

        assert config.doc_sources == DEFAULT_CONFIG["doc_sources"]

    def test_load_config_merges_with_defaults(self, tmp_path: Path) -> None:
        """Should merge partial config with defaults."""
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({
            "doc_sources": {"custom": "https://custom.example.com"}
        }))

        config = load_config(config_file)

        # Should have custom sources
        assert "custom" in config.doc_sources
        # Should still have default changelog_url
        assert config.changelog_url == DEFAULT_CONFIG["changelog_url"]

    def test_load_config_warns_on_invalid_json(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """Should log a warning when config file has invalid JSON."""
        config_file = tmp_path / "config.json"
        config_file.write_text("{ invalid json !!!")

        with caplog.at_level(logging.WARNING, logger="config"):
            config = load_config(config_file)

        # Should fall back to defaults
        assert config.doc_sources == DEFAULT_CONFIG["doc_sources"]
        # Should have logged a warning
        assert any("Failed to load config" in record.message for record in caplog.records)

    def test_load_config_validates_urls(self, tmp_path: Path) -> None:
        """Should validate that doc_sources contains valid URLs."""
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({
            "doc_sources": {"test": "https://example.com"}
        }))

        config = load_config(config_file)

        assert all(
            url.startswith("http")
            for url in config.doc_sources.values()
        )


class TestGetDocSources:
    """Tests for get_doc_sources function."""

    def test_get_doc_sources_returns_dict(self) -> None:
        """Should return a dictionary of doc sources."""
        sources = get_doc_sources()

        assert isinstance(sources, dict)
        assert len(sources) > 0

    def test_get_doc_sources_with_custom_config(self, tmp_path: Path) -> None:
        """Should use custom config when provided."""
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({
            "doc_sources": {"only": "https://only.example.com"}
        }))

        sources = get_doc_sources(config_file)

        assert sources == {"only": "https://only.example.com"}


class TestGetChangelogUrl:
    """Tests for get_changelog_url function."""

    def test_get_changelog_url_returns_string(self) -> None:
        """Should return a URL string."""
        url = get_changelog_url()

        assert isinstance(url, str)
        assert url.startswith("http")


class TestGetFetchTimeout:
    """Tests for get_fetch_timeout function."""

    def test_get_fetch_timeout_returns_number(self) -> None:
        """Should return a timeout value in seconds."""
        timeout = get_fetch_timeout()

        assert isinstance(timeout, (int, float))
        assert timeout > 0

    def test_get_fetch_timeout_from_config(self, tmp_path: Path) -> None:
        """Should read timeout from config file."""
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({
            "fetch_timeout": 60
        }))

        timeout = get_fetch_timeout(config_file)

        assert timeout == 60


class TestGetAnalysisModel:
    """Tests for get_analysis_model function."""

    def test_get_analysis_model_returns_string(self) -> None:
        """Should return a model identifier string."""
        model = get_analysis_model()

        assert isinstance(model, str)
        assert len(model) > 0


class TestConfigDataClass:
    """Tests for the Config data class."""

    def test_config_has_required_fields(self) -> None:
        """Config should have all required fields."""
        config = Config(
            doc_sources={"test": "https://example.com"},
            changelog_url="https://example.com/changelog",
            fetch_timeout=30,
            analysis_model="claude-sonnet-4-6"
        )

        assert config.doc_sources == {"test": "https://example.com"}
        assert config.changelog_url == "https://example.com/changelog"
        assert config.fetch_timeout == 30
        assert config.analysis_model == "claude-sonnet-4-6"


class TestDefaultConfig:
    """Tests for default configuration."""

    def test_default_config_has_doc_sources(self) -> None:
        """Default config should include doc sources."""
        assert "doc_sources" in DEFAULT_CONFIG
        assert len(DEFAULT_CONFIG["doc_sources"]) >= 19

    def test_default_config_has_official_doc_urls(self) -> None:
        """Default doc sources should point to official documentation platform."""
        for url in DEFAULT_CONFIG["doc_sources"].values():
            assert "platform.claude.com" in url
