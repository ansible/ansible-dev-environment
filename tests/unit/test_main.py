"""Test the main file."""

import runpy

import pytest


def test_main(capsys: pytest.CaptureFixture[str]) -> None:
    """Test the main file.

    Args:
        capsys: Capture stdout and stderr
    """
    with pytest.raises(SystemExit):
        runpy.run_module("ansible_dev_environment", run_name="__main__", alter_sys=True)

    captured = capsys.readouterr()
    assert "the following arguments are required" in captured.err
