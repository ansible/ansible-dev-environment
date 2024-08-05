"""Test the uninstaller module."""

import copy
import tarfile

from pathlib import Path

import pytest
import yaml

from ansible_dev_environment.arg_parser import parse
from ansible_dev_environment.config import Config
from ansible_dev_environment.output import Output
from ansible_dev_environment.subcommands.installer import Installer
from ansible_dev_environment.subcommands.uninstaller import UnInstaller


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
    output: Output,
    galaxy_cache: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test the uninstaller against an editable collection.

    Because the galaxy tar doesn't have a galaxy.yml file, construct one.
    Uninstall twice to catch them not found error. Use the ansible.posix
    collection since it has no deps.

    Args:
        tmp_path: The tmp_path fixture.
        output: The output fixture.
        galaxy_cache: The galaxy_cache fixture.
        capsys: The capsys fixture.
        monkeypatch: The monkeypatch fixture.

    """
    src_dir = tmp_path / "ansible.posix"
    tar_file_path = next(galaxy_cache.glob("ansible-posix*"))
    with tarfile.open(tar_file_path, "r") as tar:
        try:
            tar.extractall(src_dir, filter="data")
        except TypeError:
            tar.extractall(src_dir)  # noqa: S202
    galaxy_contents = {
        "authors": "author",
        "name": "posix",
        "namespace": "ansible",
        "readme": "readme",
        "version": "1.0.0",
    }
    yaml.dump(galaxy_contents, (src_dir / "galaxy.yml").open("w"))

    monkeypatch.setattr(
        "sys.argv",
        [
            "ade",
            "install",
            "--editable",
            str(src_dir),
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
