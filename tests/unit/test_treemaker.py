"""Test the treemaker module."""

from argparse import Namespace
from pathlib import Path
from venv import EnvBuilder

import pytest

from ansible_dev_environment.config import Config
from ansible_dev_environment.output import Output
from ansible_dev_environment.subcommands.treemaker import TreeMaker
from ansible_dev_environment.utils import JSONVal


def test_tree_empty(
    capsys: pytest.CaptureFixture[str],
    output: Output,
    tmp_path: Path,
) -> None:
    """Test tree_not_dict.

    Args:
        capsys: Pytest stdout capture fixture.
        output: Output class object.
        tmp_path: Pytest fixture.
    """
    venv_path = tmp_path / "venv"
    EnvBuilder().create(venv_path)

    args = Namespace(
        venv=venv_path,
        verbose=0,
    )
    config = Config(args=args, output=output, term_features=output.term_features)
    config.init()
    treemaker = TreeMaker(config=config, output=output)
    treemaker.run()
    captured = capsys.readouterr()
    assert captured.out == "\n\n"
    assert not captured.err


def test_tree_malformed_info(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    output: Output,
    tmp_path: Path,
) -> None:
    """Test malformed collection info.

    Args:
        capsys: Pytest stdout capture fixture.
        monkeypatch: Pytest fixture.
        output: Output class object.
        tmp_path: Pytest fixture.
    """
    venv_path = tmp_path / "venv"
    EnvBuilder().create(venv_path)

    args = Namespace(
        venv=venv_path,
        verbose=0,
    )

    def collect_manifests(
        target: Path,
        venv_cache_dir: Path,
    ) -> dict[str, dict[str, JSONVal]]:
        """Return a malformed collection info.

        Args:
            target: Target path.
            venv_cache_dir: Venv cache directory.
        <<<<<<< HEAD

        Returns:
            Collection info.
        =======
        >>>>>>> 556acba (Add some tests)
        """
        assert target
        assert venv_cache_dir
        return {
            "collection_one": {
                "collection_info": "malformed",
            },
        }

    monkeypatch.setattr(
        "ansible_dev_environment.subcommands.treemaker.collect_manifests",
        collect_manifests,
    )
    config = Config(args=args, output=output, term_features=output.term_features)
    config.init()
    treemaker = TreeMaker(config=config, output=output)
    treemaker.run()
    captured = capsys.readouterr()
    assert "Collection collection_one has malformed metadata." in captured.err


def test_tree_malformed_deps(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    output: Output,
    tmp_path: Path,
) -> None:
    """Test malformed collection deps.

    Args:
        capsys: Pytest stdout capture fixture.
        monkeypatch: Pytest fixture.
        output: Output class object.
        tmp_path: Pytest fixture.
    """
    venv_path = tmp_path / "venv"
    EnvBuilder().create(venv_path)

    args = Namespace(
        venv=venv_path,
        verbose=0,
    )

    def collect_manifests(
        target: Path,
        venv_cache_dir: Path,
    ) -> dict[str, dict[str, JSONVal]]:
        """Return a malformed collection info.

        Args:
            target: Target path.
            venv_cache_dir: Venv cache directory.
        <<<<<<< HEAD

        Returns:
            Collection info.
        =======
        >>>>>>> 556acba (Add some tests)
        """
        assert target
        assert venv_cache_dir
        return {
            "collection_one": {
                "collection_info": {
                    "dependencies": "malformed",
                },
            },
        }

    monkeypatch.setattr(
        "ansible_dev_environment.subcommands.treemaker.collect_manifests",
        collect_manifests,
    )
    config = Config(args=args, output=output, term_features=output.term_features)
    config.init()
    treemaker = TreeMaker(config=config, output=output)
    treemaker.run()
    captured = capsys.readouterr()
    assert "Collection collection_one has malformed metadata." in captured.err


def test_tree_malformed_deps_not_string(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    output: Output,
    tmp_path: Path,
) -> None:
    """Test malformed collection deps.

    Args:
        capsys: Pytest stdout capture fixture.
        monkeypatch: Pytest fixture.
        output: Output class object.
        tmp_path: Pytest fixture.
    """
    venv_path = tmp_path / "venv"
    EnvBuilder().create(venv_path)

    args = Namespace(
        venv=venv_path,
        verbose=0,
    )

    def collect_manifests(
        target: Path,
        venv_cache_dir: Path,
    ) -> dict[str, dict[str, dict[str, dict[int, int]]]]:
        """Return a malformed collection info.

        Args:
            target: Target path.
            venv_cache_dir: Venv cache directory.
        <<<<<<< HEAD

        Returns:
            Collection info.
        =======
        >>>>>>> 556acba (Add some tests)
        """
        assert target
        assert venv_cache_dir
        return {
            "collection_one": {
                "collection_info": {
                    "dependencies": {1: 2},
                },
            },
        }

    monkeypatch.setattr(
        "ansible_dev_environment.subcommands.treemaker.collect_manifests",
        collect_manifests,
    )
    config = Config(args=args, output=output, term_features=output.term_features)
    config.init()
    treemaker = TreeMaker(config=config, output=output)
    treemaker.run()
    captured = capsys.readouterr()
    assert "Collection collection_one has malformed dependency." in captured.err


def test_tree_malformed_repo_not_string(
    monkeypatch: pytest.MonkeyPatch,
    output: Output,
    tmp_path: Path,
) -> None:
    """Test malformed collection repo.

    Args:
        monkeypatch: Pytest fixture.
        output: Output class object.
        tmp_path: Pytest fixture.
    """
    venv_path = tmp_path / "venv"
    EnvBuilder().create(venv_path)

    args = Namespace(
        venv=venv_path,
        verbose=0,
    )

    def collect_manifests(
        target: Path,
        venv_cache_dir: Path,
    ) -> dict[str, dict[str, JSONVal]]:
        """Return a malformed collection info.

        Args:
            target: Target path.
            venv_cache_dir: Venv cache directory.
        <<<<<<< HEAD

        Returns:
            Collection info.
        =======
        >>>>>>> 556acba (Add some tests)
        """
        assert target
        assert venv_cache_dir
        return {
            "collection_one": {
                "collection_info": {
                    "dependencies": {},
                    "repository": True,
                },
            },
        }

    monkeypatch.setattr(
        "ansible_dev_environment.subcommands.treemaker.collect_manifests",
        collect_manifests,
    )
    config = Config(args=args, output=output, term_features=output.term_features)
    config.init()
    treemaker = TreeMaker(config=config, output=output)
    with pytest.raises(TypeError, match="Link is not a string."):
        treemaker.run()
