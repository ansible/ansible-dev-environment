"""Test the main file."""
from __future__ import annotations

import runpy

import pytest


def test_main(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    """Test the main file.

    Args:
        capsys: Capture stdout and stderr
        monkeypatch: Pytest monkeypatch fixture.
    """
    monkeypatch.setattr("sys.argv", ["ansible-dev-environment"])
    with pytest.raises(SystemExit):
        runpy.run_module("ansible_dev_environment", run_name="__main__", alter_sys=True)

    captured = capsys.readouterr()
    assert "the following arguments are required" in captured.err
