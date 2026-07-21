# ABOUTME: Tests that the project is installed as a package with working
# ABOUTME: console-script entry points and a version sourced from package metadata.

"""Packaging tests.

The pyproject declares ``freshness-check`` and ``freshness-mcp`` under
``[project.scripts]``. Those scripts are only generated when the project is
actually built and installed into the environment (which requires a
``[build-system]``). These tests fail if the project regresses to an
unpackaged state where the documented commands silently stop existing.
"""

from importlib.metadata import entry_points, version
from pathlib import Path
import tomllib


def _pyproject_version() -> str:
    """Read the version straight from pyproject.toml for comparison."""
    pyproject = Path(__file__).parent.parent / "pyproject.toml"
    with open(pyproject, "rb") as f:
        return tomllib.load(f)["project"]["version"]


class TestConsoleScripts:
    """The [project.scripts] entry points must be installed in the env."""

    def test_freshness_check_entry_point_registered(self) -> None:
        """freshness-check should be a registered console script."""
        names = {ep.name for ep in entry_points(group="console_scripts")}
        assert "freshness-check" in names

    def test_freshness_mcp_entry_point_registered(self) -> None:
        """freshness-mcp should be a registered console script."""
        names = {ep.name for ep in entry_points(group="console_scripts")}
        assert "freshness-mcp" in names

    def test_entry_points_target_existing_callables(self) -> None:
        """Each entry point should load to a callable."""
        for ep in entry_points(group="console_scripts"):
            if ep.name in ("freshness-check", "freshness-mcp"):
                assert callable(ep.load())


class TestPackageVersion:
    """Version must come from installed package metadata."""

    def test_package_metadata_version_matches_pyproject(self) -> None:
        """Installed distribution version should match pyproject.toml."""
        assert version("content-freshness-system") == _pyproject_version()

    def test_cli_version_matches_pyproject(self) -> None:
        """cli.__version__ should match pyproject.toml."""
        from cli import __version__

        assert __version__ == _pyproject_version()
