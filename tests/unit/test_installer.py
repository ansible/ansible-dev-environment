"""Tests for the installer."""

import subprocess

from argparse import Namespace
from pathlib import Path

import pytest

from ansible_dev_environment.config import Config
from ansible_dev_environment.output import Output
from ansible_dev_environment.subcommands.installer import Installer


NAMESPACE = Namespace()
NAMESPACE.verbose = 0


def test_git_no_files(tmp_path: Path, output: Output) -> None:
    """Test no files using git.

    Args:
        tmp_path: Temp directory
        output: Output instance
    """
    config = Config(args=NAMESPACE, output=output, term_features=output.term_features)
    installer = Installer(output=output, config=config)
    found_using, files = installer._find_files_using_git_ls_files(
        local_repo_path=tmp_path,
    )
    assert not found_using
    assert files is None


def test_git_none_tracked(tmp_path: Path, output: Output) -> None:
    """Test non tracked using git.

    Args:
        tmp_path: Temp directory
        output: Output instance
    """
    config = Config(args=NAMESPACE, output=output, term_features=output.term_features)
    installer = Installer(output=output, config=config)
    subprocess.run(args=["git", "init"], cwd=tmp_path, check=False)
    found_using, files = installer._find_files_using_git_ls_files(
        local_repo_path=tmp_path,
    )
    assert found_using == "git ls-files"
    assert files == ""


def test_git_one_tracked(tmp_path: Path, output: Output) -> None:
    """Test one tracked using git.

    Args:
        tmp_path: Temp directory
        output: Output instance
    """
    config = Config(args=NAMESPACE, output=output, term_features=output.term_features)
    installer = Installer(output=output, config=config)
    subprocess.run(args=["git", "init"], cwd=tmp_path, check=False)
    (tmp_path / "file.txt").touch()
    subprocess.run(args=["git", "add", "--all"], cwd=tmp_path, check=False)
    found_using, files = installer._find_files_using_git_ls_files(
        local_repo_path=tmp_path,
    )
    assert found_using == "git ls-files"
    assert files == "file.txt\n"


def test_ls_no_files(tmp_path: Path, output: Output) -> None:
    """Test no files using ls.

    Args:
        tmp_path: Temp directory
        output: Output instance
    """
    config = Config(args=NAMESPACE, output=output, term_features=output.term_features)
    installer = Installer(output=output, config=config)
    found_using, files = installer._find_files_using_ls(local_repo_path=tmp_path)
    assert found_using == "ls"
    assert files == ""


def test_ls_one_found(tmp_path: Path, output: Output) -> None:
    """Test one found using ls.

    Args:
        tmp_path: Temp directory
        output: Output instance
    """
    config = Config(args=NAMESPACE, output=output, term_features=output.term_features)
    installer = Installer(output=output, config=config)
    (tmp_path / "file.txt").touch()
    found_using, files = installer._find_files_using_ls(local_repo_path=tmp_path)
    assert found_using == "ls"
    assert files == "file.txt\n"


def test_copy_no_files(tmp_path: Path, output: Output) -> None:
    """Test file copy no files.

    Args:
        tmp_path: Temp directory
        output: Output instance
    """
    source = tmp_path / "source"
    source.mkdir()
    dest = tmp_path / "build"
    dest.mkdir()
    config = Config(args=NAMESPACE, output=output, term_features=output.term_features)
    installer = Installer(output=output, config=config)
    with pytest.raises(SystemExit) as excinfo:
        installer._copy_repo_files(local_repo_path=source, destination_path=dest)
    assert excinfo.value.code == 1


def test_copy_using_git(tmp_path: Path, output: Output) -> None:
    """Test file copy using git.

    Args:
        tmp_path: Temp directory
        output: Output instance
    """
    source = tmp_path / "source"
    source.mkdir()
    dest = tmp_path / "build"
    dest.mkdir()
    config = Config(args=NAMESPACE, output=output, term_features=output.term_features)
    installer = Installer(output=output, config=config)
    subprocess.run(args=["git", "init"], cwd=source, check=False)
    (source / "file_tracked.txt").touch()
    (source / "file_untracked.txt").touch()
    subprocess.run(args=["git", "add", "file_tracked.txt"], cwd=source, check=False)
    installer._copy_repo_files(local_repo_path=source, destination_path=dest)
    moved = dest.glob("**/*")
    assert [m.name for m in list(moved)] == ["file_tracked.txt"]


def test_copy_using_ls(tmp_path: Path, output: Output) -> None:
    """Test file copy using ls.

    Args:
        tmp_path: Temp directory
        output: Output instance
    """
    source = tmp_path / "source"
    source.mkdir()
    dest = tmp_path / "build"
    dest.mkdir()
    config = Config(args=NAMESPACE, output=output, term_features=output.term_features)
    installer = Installer(output=output, config=config)
    (source / "file1.txt").touch()
    (source / "file2.txt").touch()
    installer._copy_repo_files(local_repo_path=source, destination_path=dest)
    moved = dest.glob("**/*")
    assert sorted([m.name for m in list(moved)]) == ["file1.txt", "file2.txt"]


def test_no_adt_install(
    tmpdir: Path,
    output: Output,
) -> None:
    """Test only core is installed.

    Args:
        tmpdir: A temporary directory.
        output: The output fixture.
    """
    venv = tmpdir / "test_venv"
    args = Namespace(
        venv=venv,
        verbose=0,
        adt=False,
        system_site_packages=False,
        collection_specifier=None,
        requirement=None,
        cpi=None,
    )

    config = Config(args=args, output=output, term_features=output.term_features)
    config.init()

    installer = Installer(output=output, config=config)
    installer.run()
    assert venv.exists()
    assert (venv / "bin" / "ansible").exists()
    assert not (venv / "bin" / "adt").exists()


def test_adt_install(
    tmpdir: Path,
    output: Output,
) -> None:
    """Test adt is installed.

    Args:
        tmpdir: A temporary directory.
        output: The output fixture.
    """
    venv = tmpdir / "test_venv"
    args = Namespace(
        venv=venv,
        verbose=0,
        adt=True,
        system_site_packages=False,
        collection_specifier=None,
        requirement=None,
        cpi=None,
    )

    config = Config(args=args, output=output, term_features=output.term_features)
    config.init()

    installer = Installer(output=output, config=config)
    installer.run()
    assert venv.exists()
    assert (venv / "bin" / "ansible").exists()
    assert (venv / "bin" / "adt").exists()
