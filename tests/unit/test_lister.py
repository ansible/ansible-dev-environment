"""Test the lister module."""

import copy
import tarfile

from pathlib import Path

import pytest
import yaml

from ansible_dev_environment.arg_parser import parse
from ansible_dev_environment.config import Config
from ansible_dev_environment.output import Output
from ansible_dev_environment.subcommands.installer import Installer
from ansible_dev_environment.subcommands.lister import Lister
from ansible_dev_environment.utils import JSONVal, collect_manifests


def test_success(session_venv: Config, capsys: pytest.CaptureFixture[str]) -> None:
    """Test the lister.

    Args:
        session_venv: The venv configuration.
        capsys: The capsys fixture.

    """
    lister = Lister(config=session_venv, output=session_venv._output)
    lister.run()
    captured = capsys.readouterr()
    assert "ansible.scm" in captured.out
    assert "ansible.utils" in captured.out
    assert "ansible.posix" in captured.out


def test_collection_info_corrupt(
    session_venv: Config,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test the lister with corrupt collection info.

    Args:
        session_venv: The venv configuration.
        monkeypatch: The monkeypatch fixture.
        capsys: The capsys fixture.
    """
    orig_collect_manifests = collect_manifests

    def mock_collect_manifests(target: Path, venv_cache_dir: Path) -> dict[str, dict[str, JSONVal]]:
        """Mock the manifest collection.

        Args:
            target: The target directory.
            venv_cache_dir: The venv cache directory.

        Returns:
            dict: The collection manifests.

        """
        collections = orig_collect_manifests(target=target, venv_cache_dir=venv_cache_dir)
        collections["ansible.utils"]["collection_info"] = "This is not a valid dict."
        return collections

    monkeypatch.setattr(
        "ansible_dev_environment.subcommands.lister.collect_manifests",
        mock_collect_manifests,
    )

    lister = Lister(config=session_venv, output=session_venv._output)
    lister.run()
    captured = capsys.readouterr()
    assert "Collection ansible.utils has malformed metadata." in captured.err


def test_collection_info_collection_corrupt(
    session_venv: Config,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test the lister with corrupt collection info for collections.

    Args:
        session_venv: The venv configuration.
        monkeypatch: The monkeypatch fixture.
        capsys: The capsys fixture.
    """
    orig_collect_manifests = collect_manifests

    def mock_collect_manifests(target: Path, venv_cache_dir: Path) -> dict[str, dict[str, JSONVal]]:
        """Mock the manifest collection.

        Args:
            target: The target directory.
            venv_cache_dir: The venv cache directory.

        Returns:
            dict: The collection manifests.

        """
        collections = orig_collect_manifests(target=target, venv_cache_dir=venv_cache_dir)
        assert isinstance(collections["ansible.utils"]["collection_info"], dict)
        assert isinstance(collections["ansible.scm"]["collection_info"], dict)
        assert isinstance(collections["ansible.posix"]["collection_info"], dict)
        collections["ansible.utils"]["collection_info"]["name"] = True
        collections["ansible.scm"]["collection_info"]["namespace"] = True
        collections["ansible.posix"]["collection_info"]["version"] = True
        return collections

    monkeypatch.setattr(
        "ansible_dev_environment.subcommands.lister.collect_manifests",
        mock_collect_manifests,
    )

    lister = Lister(config=session_venv, output=session_venv._output)
    lister.run()
    captured = capsys.readouterr()
    assert "Collection ansible.utils has malformed metadata." in captured.err
    assert "Collection ansible.utils has malformed metadata." in captured.err
    assert "Collection ansible.scm has malformed metadata." in captured.err


def test_broken_link(
    session_venv: Config,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test the lister with corrupt repository URL.

    Args:
        session_venv: The venv configuration.
        monkeypatch: The monkeypatch fixture.
        capsys: The capsys fixture.
    """
    config = copy.deepcopy(session_venv)
    config._output.term_features.links = True
    orig_collect_manifests = collect_manifests

    def mock_collect_manifests(target: Path, venv_cache_dir: Path) -> dict[str, dict[str, JSONVal]]:
        """Mock the manifest collection.

        Args:
            target: The target directory.
            venv_cache_dir: The venv cache directory.

        Returns:
            dict: The collection manifests.

        """
        collections = orig_collect_manifests(target=target, venv_cache_dir=venv_cache_dir)
        assert isinstance(collections["ansible.utils"]["collection_info"], dict)
        collections["ansible.utils"]["collection_info"]["repository"] = True
        return collections

    monkeypatch.setattr(
        "ansible_dev_environment.subcommands.lister.collect_manifests",
        mock_collect_manifests,
    )

    lister = Lister(config=session_venv, output=session_venv._output)
    lister.run()
    captured = capsys.readouterr()
    assert "Collection ansible.utils has malformed metadata." in captured.err


def test_editable(
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
        ],
    )
    args = parse()
    config = Config(args=args, output=output, term_features=output.term_features)
    config.init()
    installer = Installer(config=config, output=config._output)
    installer.run()

    lister = Lister(config=config, output=config._output)
    lister.run()
    captured = capsys.readouterr()
    assert "ansible.posix" in captured.out
    assert str(tmp_path / "ansible.posix") in captured.out
