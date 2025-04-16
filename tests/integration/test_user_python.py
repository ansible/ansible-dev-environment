"""Test multiple variants of python version."""

from __future__ import annotations

import sys

from pathlib import Path

import pytest

from ansible_dev_environment.cli import main


def generate_pythons_uv() -> list[str]:
    """Generate a list of python versions.

    Returns:
        List of python versions
    """
    pythons = ["python3"]
    version = sys.version.split(" ", maxsplit=1)[0]
    pythons.append(version)
    pythons.append(f"python{version}")
    major_minor = version.rsplit(".", 1)[0]
    pythons.append(major_minor)
    major, minor = major_minor.split(".")
    one_less = f"{major}.{int(minor) - 1}"
    pythons.append(one_less)
    sys_path = str(Path("/usr/bin/python3").resolve())
    pythons.append(sys_path)
    return pythons


@pytest.mark.parametrize("python", generate_pythons_uv())
def test_specified_python_version_uv(
    python: str,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Build the venv with a user specified python version.

    Args:
        python: Python version
        capsys: Capture stdout and stderr
        tmp_path: Temporary directory
        monkeypatch: Pytest monkeypatch
    """
    venv_path = tmp_path / ".venv"
    monkeypatch.setattr(
        "sys.argv",
        [
            "ade",
            "install",
            f"--venv={venv_path}",
            f"--python={python}",
        ],
    )
    with pytest.raises(SystemExit):
        main()

    captured = capsys.readouterr()
    venv_line = [
        line for line in captured.out.splitlines() if "Created virtual environment:" in line
    ]
    assert venv_line[0].endswith(python)


def generate_pythons_pip() -> list[str]:
    """Generate a list of python versions.

    Returns:
        List of python versions
    """
    pythons = ["python3"]
    version = sys.version.split(" ", maxsplit=1)[0]
    major_minor = version.rsplit(".", 1)[0]
    pythons.append(major_minor)
    sys_path = str(Path("/usr/bin/python3").resolve())
    pythons.append(sys_path)
    return pythons


@pytest.mark.parametrize("python", generate_pythons_pip())
def test_specified_python_version_pip(
    python: str,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Build the venv with a user specified python version.

    Args:
        python: Python version
        capsys: Capture stdout and stderr
        tmp_path: Temporary directory
        monkeypatch: Pytest monkeypatch
    """
    venv_path = tmp_path / ".venv"
    monkeypatch.setattr(
        "sys.argv",
        ["ade", "install", f"--venv={venv_path}", f"--python={python}", "--no-uv"],
    )
    with pytest.raises(SystemExit):
        main()

    captured = capsys.readouterr()
    venv_line = [
        line for line in captured.out.splitlines() if "Created virtual environment:" in line
    ]
    assert venv_line[0].endswith(python)
