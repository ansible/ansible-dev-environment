"""Test the uninstaller module."""

from __future__ import annotations

import copy

from typing import TYPE_CHECKING

import pytest

from ansible_dev_environment.arg_parser import parse
from ansible_dev_environment.config import Config
from ansible_dev_environment.subcommands.installer import Installer
from ansible_dev_environment.subcommands.uninstaller import UnInstaller


if TYPE_CHECKING:
    from pathlib import Path

    from ansible_dev_environment.output import Output


def test_many(session_venv: Config, capsys: pytest.CaptureFixture[str]) -> None:
    """Test the uninstaller with many collections.

    Args:
        session_venv: The session_venv fixture.
        capsys: The capsys fixture.
    """
    config = copy.deepcopy(session_venv)
    config.args.collection_specifier = ["community.general", "ansible.utils"]
    uninstaller = UnInstaller(config=config, output=config._output)
    with pytest.raises(SystemExit) as exc:
        uninstaller.run()
    assert exc.value.code == 1
    captured = capsys.readouterr()
    assert "Only one collection can be uninstalled at a time." in captured.err


def test_missing_reqs(
    session_venv: Config,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test the uninstaller against a missing requirements file.

    Args:
        session_venv: The session_venv fixture.
        tmp_path: The tmp_path fixture.
        capsys: The capsys fixture.
    """
    config = copy.deepcopy(session_venv)
    config.args.requirement = str(tmp_path / "requirements.yml")
    uninstaller = UnInstaller(config=config, output=config._output)
    with pytest.raises(SystemExit) as exc:
        uninstaller.run()
    assert exc.value.code == 1
    captured = capsys.readouterr()
    assert "Failed to find requirements file" in captured.err


def test_editable_uninstall(
    tmp_path: Path,
    installable_local_collection: Path,
    output: Output,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test the uninstaller against an editable collection.

    Because the galaxy tar doesn't have a galaxy.yml file, construct one.
    Uninstall twice to catch them not found error. Use the ansible.posix
    collection since it has no deps.

    Args:
        tmp_path: The tmp_path fixture.
        installable_local_collection: The installable_local_collection fixture.
        output: The output fixture.
        capsys: The capsys fixture.
        monkeypatch: The monkeypatch fixture.

    """
    monkeypatch.setattr(
        "sys.argv",
        [
            "ade",
            "install",
            "--editable",
            str(installable_local_collection),
            "--lf",
            str(tmp_path / "ade.log"),
            "--venv",
            str(tmp_path / "venv"),
            "-vvv",
        ],
    )
    args = parse()
    config = Config(args=args, output=output, term_features=output.term_features)
    config.init()
    installer = Installer(config=config, output=config._output)
    installer.run()
    args.collection_specifier = ["ansible.posix"]
    uninstaller = UnInstaller(config=config, output=config._output)
    uninstaller.run()
    uninstaller.run()
    captured = capsys.readouterr()
    assert "Removed ansible.posix" in captured.out
    assert "Failed to find ansible.posix" in captured.out
