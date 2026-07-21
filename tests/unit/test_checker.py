"""Unit tests for the checker subcommand helpers."""

from __future__ import annotations

from argparse import Namespace
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from packaging.specifiers import SpecifierSet

from ansible_dev_environment.subcommands.checker import Checker
from ansible_dev_environment.utils import TermFeatures


if TYPE_CHECKING:
    from pathlib import Path

    from ansible_dev_environment.output import Output


@pytest.fixture(name="checker")
def _checker(output: Output, tmp_path: Path) -> Checker:
    """Create a Checker instance for testing.

    Args:
        output: Output fixture.
        tmp_path: Temporary directory.

    Returns:
        Checker instance.
    """
    config = MagicMock()
    config.site_pkg_collections_path = tmp_path / "collections"
    config.venv_cache_dir = tmp_path / "cache"
    config.args = Namespace(verbose=0)
    config.venv_interpreter = "python"
    config.discovered_python_reqs = tmp_path / "reqs.txt"
    config.term_features = TermFeatures(color=False, links=False)
    return Checker(config=config, output=output)


def test_validate_valid(checker: Checker) -> None:
    """Validate well-formed collection info returns True.

    Args:
        checker: Checker fixture.
    """
    details = {"collection_info": {"dependencies": {"dep": ">=1.0"}}}
    assert checker._validate_collection_info(details, "err") is True


def test_validate_missing_ci(checker: Checker) -> None:
    """Validate missing collection_info returns False.

    Args:
        checker: Checker fixture.
    """
    assert checker._validate_collection_info({}, "err") is False


def test_validate_non_dict_ci(checker: Checker) -> None:
    """Validate non-dict collection_info returns False.

    Args:
        checker: Checker fixture.
    """
    assert checker._validate_collection_info({"collection_info": "bad"}, "err") is False


def test_validate_missing_deps(checker: Checker) -> None:
    """Validate missing dependencies returns False.

    Args:
        checker: Checker fixture.
    """
    details = {"collection_info": {"version": "1.0"}}
    assert checker._validate_collection_info(details, "err") is False


def test_installed_dep_match(checker: Checker) -> None:
    """Installed dependency version matches.

    Args:
        checker: Checker fixture.
    """
    dep_data = {"collection_info": {"version": "1.5.0"}}
    result = checker._check_installed_dependency(
        "ns.col",
        "ns.dep",
        ">=1.0",
        SpecifierSet(">=1.0"),
        dep_data,
    )
    assert result is False


def test_installed_dep_mismatch(checker: Checker) -> None:
    """Installed dependency version does not match.

    Args:
        checker: Checker fixture.
    """
    dep_data = {"collection_info": {"version": "0.5.0"}}
    result = checker._check_installed_dependency(
        "ns.col",
        "ns.dep",
        ">=1.0",
        SpecifierSet(">=1.0"),
        dep_data,
    )
    assert result is True


def test_check_dep_missing(checker: Checker) -> None:
    """Missing dependency returns True.

    Args:
        checker: Checker fixture.
    """
    assert checker._check_dependency("ns.col", "ns.dep", ">=1.0", {}) is True


def test_check_dep_installed(checker: Checker) -> None:
    """Installed and matching dependency returns False.

    Args:
        checker: Checker fixture.
    """
    collections = {"ns.dep": {"collection_info": {"version": "2.0.0"}}}
    assert checker._check_dependency("ns.col", "ns.dep", ">=1.0", collections) is False


def test_check_dep_invalid_specifier(checker: Checker) -> None:
    """Invalid version specifier falls back gracefully.

    Args:
        checker: Checker fixture.
    """
    collections = {"ns.dep": {"collection_info": {"version": "1.0.0"}}}
    result = checker._check_dependency("ns.col", "ns.dep", "bad_version", collections)
    assert result is False
