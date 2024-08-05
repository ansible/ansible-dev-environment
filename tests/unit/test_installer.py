"""Tests for the installer."""

import subprocess

from argparse import Namespace
from pathlib import Path
from typing import Any

import pytest

from ansible_dev_environment.arg_parser import parse
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
    tmp_path: Path,
    output: Output,
) -> None:
    """Test only core is installed.

    Args:
        tmp_path: A temporary directory.
        output: The output fixture.
    """
    venv = tmp_path / "test_venv"
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
    tmp_path: Path,
    output: Output,
) -> None:
    """Test adt is installed.

    Args:
        tmp_path: A temporary directory.
        output: The output fixture.
    """
    venv = tmp_path / "test_venv"
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


def test_multiple_specifiers(
    tmp_path: Path,
    output: Output,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test more than one collection specifier.

    Args:
        tmp_path: A temporary directory.
        output: The output fixture.
        monkeypatch: The monkeypatch fixture.
        capsys: The capsys fixture.
    """
    command = ["ade", "install", "ansible.utils[dev,test]", "--venv", str(tmp_path / "venv")]
    monkeypatch.setattr("sys.argv", command)
    args = parse()
    installer = Installer(
        output=output,
        config=Config(args=args, output=output, term_features=output.term_features),
    )
    with pytest.raises(SystemExit):
        installer.run()
    captured = capsys.readouterr()
    assert "Multiple optional dependencies are not supported at this time" in captured.err


def test_editable_not_local(
    tmp_path: Path,
    output: Output,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test editable with a non-local collection.

    Args:
        tmp_path: A temporary directory.
        output: The output fixture.
        monkeypatch: The monkeypatch fixture.
        capsys: The capsys fixture.
    """
    command = ["ade", "install", "-e", "ansible.utils", "--venv", str(tmp_path / "venv")]
    monkeypatch.setattr("sys.argv", command)
    args = parse()
    config = Config(args=args, output=output, term_features=output.term_features)
    config.init()
    installer = Installer(
        output=output,
        config=config,
    )

    def install_core(self: Installer) -> None:  # noqa: ARG001
        """Don't install core.

        Args:
            self: The installer instance.
        """

    monkeypatch.setattr(Installer, "_install_core", install_core)
    with pytest.raises(SystemExit):
        installer.run()
    captured = capsys.readouterr()
    assert "Editable installs are only supported for local collections" in captured.err


def test_core_installed(session_venv: Config) -> None:
    """Test that core is installed only once.

    Args:
        session_venv: The session_venv fixture.
    """
    mtime_pre = session_venv.venv_bindir.joinpath("ansible").stat().st_mtime
    installer = Installer(config=session_venv, output=session_venv._output)
    installer._install_core()
    mtime_post = session_venv.venv_bindir.joinpath("ansible").stat().st_mtime
    assert mtime_pre == mtime_post


def test_core_install_fails(
    session_venv: Config,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test a clean exit if the core install fails.

    Args:
        session_venv: The session_venv fixture.
        monkeypatch: The monkeypatch fixture.
        capsys: The capsys fixture.
    """
    orig_exists = Path.exists

    def exists(path: Path) -> bool:
        """Selectively return False.

        Args:
            path: A path to check

        Returns:
            False if the path is "ansible", otherwise the original exists function result.
        """
        if path.name == "ansible":
            return False
        return orig_exists(path)

    monkeypatch.setattr(Path, "exists", exists)

    def subprocess_run(*_args: Any, **_kwargs: Any) -> None:  # noqa: ANN401
        """Raise an exception.

        Args:
            *_args: Arguments
            **_kwargs: Keyword arguments

        Raises:
            subprocess.CalledProcessError: Always

        """
        raise subprocess.CalledProcessError(1, "ansible")

    monkeypatch.setattr(
        "ansible_dev_environment.subcommands.installer.subprocess_run",
        subprocess_run,
    )
    installer = Installer(config=session_venv, output=session_venv._output)

    with pytest.raises(SystemExit):
        installer._install_core()

    captured = capsys.readouterr()
    assert "Failed to install ansible-core" in captured.err


def test_adt_installed(session_venv: Config) -> None:
    """Test that adt is installed only once.

    Args:
        session_venv: The session_venv fixture.
    """
    orig_exists = Path.exists

    def exists(path: Path) -> bool:
        """Selectively return False.

        Args:
            path: A path to check

        Returns:
            False if the path is "adt", otherwise the original exists function result.
        """
        if path.name == "adt":
            return True
        return orig_exists(path)

    with pytest.MonkeyPatch.context() as m:
        m.setattr(Path, "exists", exists)
        installer = Installer(config=session_venv, output=session_venv._output)
        installer._install_dev_tools()

    assert not session_venv.venv_bindir.joinpath("adt").exists()


def test_adt_install_fails(
    session_venv: Config,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test a clean exit if the adt install fails.

    Args:
        session_venv: The session_venv fixture.
        monkeypatch: The monkeypatch fixture.
        capsys: The capsys fixture.
    """

    def subprocess_run(*_args: Any, **_kwargs: Any) -> None:  # noqa: ANN401
        """Raise an exception.

        Args:
            *_args: Arguments
            **_kwargs: Keyword arguments

        Raises:
            subprocess.CalledProcessError: Always

        """
        raise subprocess.CalledProcessError(1, "adt")

    monkeypatch.setattr(
        "ansible_dev_environment.subcommands.installer.subprocess_run",
        subprocess_run,
    )
    installer = Installer(config=session_venv, output=session_venv._output)

    with pytest.raises(SystemExit):
        installer._install_dev_tools()

    captured = capsys.readouterr()
    assert "Failed to install ansible-dev-tools" in captured.err


def test_reinstall(
    function_venv: Config,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test that reinstalling works.

    Args:
        function_venv: The function_venv fixture.
        monkeypatch: The monkeypatch fixture.
        capsys: The capsys fixture.
    """
    command = [
        "ade",
        "install",
        "ansible.posix",
        "--venv",
        str(function_venv.venv),
        "--ll",
        "notset",
        "-vvv",
    ]
    monkeypatch.setattr("sys.argv", command)
    args = parse()
    config = Config(
        args=args,
        output=function_venv._output,
        term_features=function_venv._output.term_features,
    )
    config.init()
    pre_mtime = (function_venv.site_pkg_collections_path / "ansible" / "posix").stat().st_mtime
    installer = Installer(config=config, output=function_venv._output)
    installer.run()
    post_mtime = (function_venv.site_pkg_collections_path / "ansible" / "posix").stat().st_mtime
    assert post_mtime > pre_mtime
    captured = capsys.readouterr()
    assert "Removing installed " in captured.out


def test_install_fails(
    function_venv: Config,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test for a clean exit if a collection install fails.

    Args:
        function_venv: The function_venv fixture.
        monkeypatch: The monkeypatch fixture.
        capsys: The capsys fixture.
    """
    command = [
        "ade",
        "install",
        "ansible.posix",
        "--venv",
        str(function_venv.venv),
        "--ll",
        "notset",
        "-vvv",
    ]
    monkeypatch.setattr("sys.argv", command)
    args = parse()
    config = Config(
        args=args,
        output=function_venv._output,
        term_features=function_venv._output.term_features,
    )
    config.init()

    def subprocess_run(**kwargs: Any) -> subprocess.CompletedProcess[str]:  # noqa: ANN401
        """Raise an exception.

        Args:
            **kwargs: Keyword arguments

        Raises:
            subprocess.CalledProcessError: if ansible posix is being installed

        Returns:
            The completed process

        """
        if "install 'ansible.posix'" in kwargs["command"]:
            raise subprocess.CalledProcessError(1, "ansible.posix")
        return subprocess_run(**kwargs)

    monkeypatch.setattr(
        "ansible_dev_environment.subcommands.installer.subprocess_run",
        subprocess_run,
    )

    installer = Installer(config=config, output=function_venv._output)
    with pytest.raises(SystemExit):
        installer.run()
    captured = capsys.readouterr()
    assert "Failed to install collection" in captured.err
