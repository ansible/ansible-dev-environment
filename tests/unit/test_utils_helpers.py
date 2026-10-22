"""Unit tests for extracted helper functions in utils module."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import yaml

from ansible_dev_environment.utils import (
    JSONVal,
    _process_collection_info,
    _process_requirements_files,
    version_satisfies_constraint,
)


if TYPE_CHECKING:
    from pathlib import Path


def test_process_collection_info_with_galaxy_yml(tmp_path: Path) -> None:
    """Collection info extracted from galaxy.yml.

    Args:
        tmp_path: Temporary directory.
    """
    ns_dir = tmp_path / "testns"
    name_dir = ns_dir / "testcol"
    name_dir.mkdir(parents=True)
    galaxy = name_dir / "galaxy.yml"
    galaxy.write_text(yaml.dump({"version": "1.2.3", "dependencies": {"ns.dep": ">=1.0"}}))

    fqcn, info = _process_collection_info(ns_dir, name_dir, [])
    assert fqcn == "testns.testcol"
    assert info["version"] == "1.2.3"
    assert info["dependencies"] == {"ns.dep": ">=1.0"}


def test_process_collection_info_with_info_dir(tmp_path: Path) -> None:
    """Collection info extracted from .info directory.

    Args:
        tmp_path: Temporary directory.
    """
    ns_dir = tmp_path / "testns"
    name_dir = ns_dir / "testcol"
    name_dir.mkdir(parents=True)
    info_dir = tmp_path / "testns.testcol.info"
    info_dir.mkdir()
    galaxy = info_dir / "GALAXY.yml"
    galaxy.write_text(yaml.dump({"version": "2.0.0"}))

    fqcn, info = _process_collection_info(ns_dir, name_dir, [info_dir])
    assert fqcn == "testns.testcol"
    assert info["version"] == "2.0.0"


def test_process_collection_info_no_galaxy(tmp_path: Path) -> None:
    """Collection info falls back when no galaxy.yml exists.

    Args:
        tmp_path: Temporary directory.
    """
    ns_dir = tmp_path / "testns"
    name_dir = ns_dir / "testcol"
    name_dir.mkdir(parents=True)

    fqcn, info = _process_collection_info(ns_dir, name_dir, [])
    assert fqcn == "testns.testcol"
    assert info["version"] == "unknown"
    assert info["dependencies"] == []


def test_process_collection_info_empty_galaxy(tmp_path: Path) -> None:
    """Collection info handles empty galaxy.yml.

    Args:
        tmp_path: Temporary directory.
    """
    ns_dir = tmp_path / "testns"
    name_dir = ns_dir / "testcol"
    name_dir.mkdir(parents=True)
    galaxy = name_dir / "galaxy.yml"
    galaxy.write_text("")

    fqcn, info = _process_collection_info(ns_dir, name_dir, [])
    assert fqcn == "testns.testcol"
    assert info["version"] == "unknown"


def test_process_requirements_files(tmp_path: Path) -> None:
    """Requirements files are parsed into c_info.

    Args:
        tmp_path: Temporary directory.
    """
    col_dir = tmp_path / "col"
    col_dir.mkdir()
    (col_dir / "requirements.txt").write_text("boto3\nrequests\n")
    (col_dir / "bindep.txt").write_text("gcc\nlibffi-devel\n")
    (col_dir / "readme.md").write_text("not a requirements file")

    c_info: dict[str, JSONVal] = {
        "requirements": {
            "python": {},
            "system": [],
        },
    }
    _process_requirements_files(col_dir, c_info)

    reqs = c_info["requirements"]
    assert isinstance(reqs, dict)
    assert reqs["python"] == {"requirements": ["boto3", "requests"]}
    assert reqs["system"] == ["gcc", "libffi-devel"]


def test_process_requirements_files_no_files(tmp_path: Path) -> None:
    """No requirements files found.

    Args:
        tmp_path: Temporary directory.
    """
    col_dir = tmp_path / "col"
    col_dir.mkdir()

    c_info: dict[str, JSONVal] = {
        "requirements": {
            "python": {},
            "system": [],
        },
    }
    _process_requirements_files(col_dir, c_info)

    reqs = c_info["requirements"]
    assert isinstance(reqs, dict)
    assert not reqs["python"]
    assert not reqs["system"]


@pytest.mark.parametrize(
    ("installed_version", "version_req", "expected"),
    (
        pytest.param("1.5.0", ">=1.0.0,<2.0.0", True, id="range-satisfied"),
        pytest.param("2.0.0", ">=1.0.0,<2.0.0", False, id="range-not-satisfied"),
        pytest.param("1.5.0", None, True, id="no-constraint"),
        pytest.param("1.5.0", "", True, id="empty-constraint"),
        pytest.param("1.5.0", "*", True, id="wildcard"),
        pytest.param("1.5.0", ">=2.0.0", False, id="too-old"),
        pytest.param("1.5.0", "not-a-specifier", True, id="invalid-specifier-fallback"),
        pytest.param("not-a-version", ">=1.0.0", False, id="invalid-version"),
    ),
)
def test_version_satisfies_constraint(
    installed_version: str,
    version_req: str | None,
    expected: bool,  # noqa: FBT001
) -> None:
    """Shared constraint helper used by both Checker and Installer.

    Args:
        installed_version: Installed collection version string.
        version_req: Version constraint from galaxy.yml.
        expected: Expected satisfaction result.
    """
    assert version_satisfies_constraint(installed_version, version_req) is expected


def test_version_satisfies_constraint_without_packaging(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Returns False when packaging is unavailable.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
    """
    monkeypatch.setattr("ansible_dev_environment.utils._packaging_specifiers", None)
    monkeypatch.setattr("ansible_dev_environment.utils._packaging_version", None)
    assert version_satisfies_constraint("1.5.0", ">=1.0.0") is False
