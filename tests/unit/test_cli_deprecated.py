"""Test some deprecated values in the CLI."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ansible_dev_environment.cli import main


if TYPE_CHECKING:
    import pytest


def test_adt(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    """Test the seed option.

    Args:
        capsys: Pytest stdout capture fixture.
        monkeypatch: Pytest fixture.
    """
    # Test the seed option
    monkeypatch.setattr(
        "sys.argv",
        ["ansible-dev-environment", "install", "--adt"],
    )
    main(dry=True)
    captured = capsys.readouterr()
    assert "'--adt' is deprecated" in captured.out


def test_skip_uv(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    """Test the skip uv option.

    Args:
        capsys: Pytest stdout capture fixture.
        monkeypatch: Pytest fixture.
    """
    # Test the skip uv option
    monkeypatch.setattr(
        "sys.argv",
        ["ansible-dev-environment", "install"],
    )
    monkeypatch.setenv("SKIP_UV", "1")
    main(dry=True)
    captured = capsys.readouterr()
    assert "'SKIP_UV' is deprecated" in captured.out
