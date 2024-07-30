"""Tests for the inspector module."""

import copy
import importlib
import json
import re
import sys

import pytest

from ansible_dev_environment.config import Config
from ansible_dev_environment.subcommands import inspector


def test_output_no_color(session_venv: Config, capsys: pytest.CaptureFixture) -> None:
    """Test the inspector output.

    Args:
        session_venv: The configuration object for the venv.
        capsys: Pytest capture fixture.
    """
    _inspector = inspector.Inspector(config=session_venv, output=session_venv._output)
    _inspector.run()
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "ansible.posix" in data
    assert "ansible.scm" in data
    assert "ansible.utils" in data


def test_output_color(
    session_venv: Config,
    capsys: pytest.CaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test the inspector output.

    Args:
        session_venv: The configuration object for the venv.
        capsys: Pytest capture fixture.
        monkeypatch: Pytest monkeypatch fixture.
    """
    monkeypatch.setenv("FORCE_COLOR", "1")
    config = copy.deepcopy(session_venv)
    config.term_features.color = True
    _inspector = inspector.Inspector(config=config, output=session_venv._output)
    _inspector.run()
    captured = capsys.readouterr()
    assert captured.out.startswith("\x1b")
    ansi_escape = re.compile(r"(\x9B|\x1B\[)[0-?]*[ -\/]*[@-~]")
    no_ansi = ansi_escape.sub("", captured.out)
    data = json.loads(no_ansi)
    assert "ansible.posix" in data
    assert "ansible.scm" in data
    assert "ansible.utils" in data


def test_no_rich(
    session_venv: Config,
    capsys: pytest.CaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test the inspector output when rich is not available.

    Args:
        session_venv: The configuration object for the venv.
        capsys: Pytest capture fixture.
        monkeypatch: Pytest monkeypatch fixture.
    """
    with monkeypatch.context() as monkey_rich:
        monkey_rich.setitem(sys.modules, "pip._vendor.rich", None)
        importlib.reload(inspector)
        assert inspector.HAS_RICH is False

        _inspector = inspector.Inspector(config=session_venv, output=session_venv._output)
        _inspector.run()

    importlib.reload(inspector)

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "ansible.posix" in data
    assert "ansible.scm" in data
    assert "ansible.utils" in data
