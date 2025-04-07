# pylint: disable=C0302
"""Tests for the installer."""

from __future__ import annotations

import os
import shutil
import subprocess

from argparse import Namespace
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
import yaml

from ansible_dev_environment.arg_parser import parse
from ansible_dev_environment.cli import Cli, main
from ansible_dev_environment.config import Config
from ansible_dev_environment.subcommands.installer import Installer
from ansible_dev_environment.utils import subprocess_run


if TYPE_CHECKING:
    from ansible_dev_environment.collection import Collection
    from ansible_dev_environment.output import Output


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


def test_ls_failed(
    tmp_path: Path,
    output: Output,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test one found using ls.

    Args:
        tmp_path: Temp directory
        output: Output instance
        monkeypatch: The monkeypatch fixture
        capsys: The capsys fixture
    """

    def mock_subprocess_run(**_kwargs: Any) -> None:  # noqa: ANN401
        """Raise an exception.

        Args:
            **_kwargs: Keyword arguments

        Raises:
            subprocess.CalledProcessError: Always

        """
        raise subprocess.CalledProcessError(1, "ls")

    monkeypatch.setattr(
        "ansible_dev_environment.subcommands.installer.subprocess_run",
        mock_subprocess_run,
    )
    config = Config(args=NAMESPACE, output=output, term_features=output.term_features)
    installer = Installer(output=output, config=config)
    (tmp_path / "file.txt").touch()
    result = installer._find_files_using_ls(local_repo_path=tmp_path)
    assert result == (None, None)

    captured = capsys.readouterr()
    assert "Failed to list collection using ls" in captured.out


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


def test_copy_fails(
    tmp_path: Path,
    output: Output,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test file copy using ls.

    Args:
        tmp_path: Temp directory
        output: Output instance
        monkeypatch: The monkeypatch fixture
        capsys: The capsys fixture
    """
    source = tmp_path / "source"
    source.mkdir()
    dest = tmp_path / "build"
    dest.mkdir()
    config = Config(args=NAMESPACE, output=output, term_features=output.term_features)
    installer = Installer(output=output, config=config)
    (source / "file1.txt").touch()
    (source / "file2.txt").touch()

    def mock_copy2(src: Path, dest: Path) -> None:  # noqa: ARG001
        """Raise an exception.

        Args:
            src: Source path
            dest: Destination path

        Raises:
            shutil.Error: Always

        """
        raise shutil.Error

    monkeypatch.setattr(shutil, "copy2", mock_copy2)
    with pytest.raises(SystemExit) as excinfo:
        installer._copy_repo_files(local_repo_path=source, destination_path=dest)

    assert excinfo.value.code == 1
    captured = capsys.readouterr()
    assert "Failed to copy collection to build directory" in captured.err


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
        seed=False,
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
        seed=True,
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
    command = [
        "ade",
        "install",
        "ansible.utils[dev,test]",
        "--venv",
        str(tmp_path / "venv"),
    ]
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
    command = [
        "ade",
        "install",
        "-e",
        "ansible.utils",
        "--venv",
        str(tmp_path / "venv"),
    ]
    monkeypatch.setattr("sys.argv", command)
    args = parse()
    config = Config(args=args, output=output, term_features=output.term_features)
    config.init()
    installer = Installer(
        output=output,
        config=config,
    )

    def install_core(installer: Installer) -> None:
        """Don't install core.

        Args:
            installer: Installer instance.
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

    def mock_subprocess_run(**kwargs: Any) -> None:  # noqa: ANN401
        """Raise an exception.

        Args:
            **kwargs: Keyword arguments

        Raises:
            subprocess.CalledProcessError: Always

        """
        raise subprocess.CalledProcessError(1, kwargs["command"])

    monkeypatch.setattr(
        "ansible_dev_environment.subcommands.installer.subprocess_run",
        mock_subprocess_run,
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

    def mock_subprocess_run(**kwargs: Any) -> None:  # noqa: ANN401
        """Raise an exception.

        Args:
            **kwargs: Keyword arguments

        Raises:
            subprocess.CalledProcessError: Always

        """
        raise subprocess.CalledProcessError(1, kwargs["command"])

    monkeypatch.setattr(
        "ansible_dev_environment.subcommands.installer.subprocess_run",
        mock_subprocess_run,
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


def test_reinstall_editable(
    tmp_path: Path,
    installable_local_collection: Path,
    monkeypatch: pytest.MonkeyPatch,
    output: Output,
) -> None:
    """Test that reinstalling works if initially editable.

    Add a galaxy.yml file to the extracted collection and install it editable. Then install it
    non-editable.

    Args:
        tmp_path: A temporary directory.
        installable_local_collection: The installable_local_collection fixture.
        monkeypatch: The monkeypatch fixture.
        output: The output fixture.
    """
    monkeypatch.setattr(
        "sys.argv",
        [
            "ade",
            "install",
            "--editable",
            str(installable_local_collection),
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
    assert (config.site_pkg_collections_path / "ansible" / "posix").is_symlink()

    monkeypatch.setattr(
        "sys.argv",
        [
            "ade",
            "install",
            "ansible.posix",
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
    assert not (config.site_pkg_collections_path / "ansible" / "posix").is_symlink()


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

    def mock_subprocess_run(**kwargs: Any) -> subprocess.CompletedProcess[str]:  # noqa: ANN401
        """Raise an exception.

        Args:
            **kwargs: Keyword arguments

        Raises:
            subprocess.CalledProcessError: if ansible posix is being installed

        Returns:
            The completed process

        """
        if "install 'ansible.posix'" in kwargs["command"]:
            raise subprocess.CalledProcessError(1, kwargs["command"])
        return subprocess_run(**kwargs)

    monkeypatch.setattr(
        "ansible_dev_environment.subcommands.installer.subprocess_run",
        mock_subprocess_run,
    )

    installer = Installer(config=config, output=function_venv._output)
    with pytest.raises(SystemExit):
        installer.run()
    captured = capsys.readouterr()
    assert "Failed to install collection" in captured.err


def test_collection_pre_install(
    tmp_path: Path,
    installable_local_collection: Path,
    galaxy_cache: Path,
    monkeypatch: pytest.MonkeyPatch,
    output: Output,
) -> None:
    """Test the collection pre-install functionality.

    Rewrite the galaxy_cache requirements.yml file to only include the ansible-utils collection
    as the source requirements file in an extracted collection. Add the galaxy.yml file to the
    extracted collection. Install the collection with the collection pre-install.

    Args:
        tmp_path: A temporary directory.
        installable_local_collection: The installable_local_collection fixture.
        galaxy_cache: The galaxy_cache fixture.
        monkeypatch: The monkeypatch fixture.
        output: The output fixture.
    """
    orig_reqs = galaxy_cache / "requirements.yml"
    source_reqs = installable_local_collection / ".config" / "source-requirements.yml"
    source_reqs.parent.mkdir(parents=True)
    shutil.copy(src=orig_reqs, dst=source_reqs)
    content = yaml.load(source_reqs.read_text(), Loader=yaml.SafeLoader)
    content["collections"] = [c for c in content["collections"] if "ansible-utils" in c["name"]]
    source_reqs.write_text(yaml.dump(content))
    monkeypatch.chdir(installable_local_collection)
    monkeypatch.setattr(
        "sys.argv",
        [
            "ade",
            "install",
            ".",
            "--collection-pre-install",
            "--venv",
            str(tmp_path / "venv"),
        ],
    )
    cli = Cli()
    cli.parse_args()
    cli.output = output
    cli.args_sanity()
    config = Config(args=cli.args, output=output, term_features=output.term_features)
    config.init()
    installer = Installer(config=config, output=config._output)
    installer.run()
    subdirs = (config.site_pkg_collections_path / "ansible").glob("*")
    assert sorted({c.name for c in subdirs}) == ["posix", "utils"]


def test_args_sanity(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """Test the args_sanity method.

    Args:
        monkeypatch: The monkeypatch fixture.
        capsys: The capsys fixture.
    """
    # Adds invalid entry in PATH to detect that we can detect it and exit
    monkeypatch.setenv("PATH", "~/bin", prepend=os.pathsep)
    monkeypatch.setattr("sys.argv", ["ade", "check"])

    with pytest.raises(SystemExit) as exc:
        main(dry=True)
    assert exc.value.code == 1

    captured = capsys.readouterr()
    assert "~ character was found inside PATH" in captured.err


@pytest.mark.parametrize("first", (True, False), ids=["editable", "not_editable"])
@pytest.mark.parametrize("second", (True, False), ids=["editable", "not_editable"])
def test_reinstall_local_collection(  # pylint: disable=too-many-positional-arguments
    first: bool,  # noqa: FBT001
    second: bool,  # noqa: FBT001
    tmp_path: Path,
    installable_local_collection: Path,
    output: Output,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that reinstalling works with a local collection.

    Args:
        first: A boolean indicating if the collection is installed editable first.
        second: A boolean indicating if the collection is installed editable second.
        tmp_path: A temporary directory.
        installable_local_collection: The installable_local_collection fixture.
        output: The output fixture.
        monkeypatch: The monkeypatch fixture.
    """
    cli_args = [
        "ade",
        "install",
        str(installable_local_collection),
        "--venv",
        str(tmp_path / "venv"),
        "-vvv",
    ]
    monkeypatch.setattr("sys.argv", cli_args + (["--editable"] if first else []))
    args = parse()
    config = Config(args=args, output=output, term_features=output.term_features)
    config.init()
    installer = Installer(config=config, output=config._output)
    installer.run()
    assert (config.site_pkg_collections_path / "ansible" / "posix").is_symlink() is first
    monkeypatch.setattr("sys.argv", cli_args + (["--editable"] if second else []))
    args = parse()
    config = Config(args=args, output=output, term_features=output.term_features)
    config.init()
    installer = Installer(config=config, output=config._output)
    installer.run()
    assert (config.site_pkg_collections_path / "ansible" / "posix").is_symlink() is second


def test_reinstall_local_collection_after_galaxy(
    tmp_path: Path,
    installable_local_collection: Path,
    output: Output,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that reinstalling works with a local collection after a galaxy install.

    The galaxy install should be removed and the local collection installed. The galaxy install
    leaves an info directory in the site-packages directory that should be removed.

    Args:
        tmp_path: A temporary directory.
        installable_local_collection: The installable_local_collection fixture.
        output: The output fixture.
        monkeypatch: The monkeypatch fixture.
    """
    monkeypatch.setattr(
        "sys.argv",
        ["ade", "install", "ansible.posix", "--venv", str(tmp_path / "venv")],
    )
    args = parse()
    config = Config(args=args, output=output, term_features=output.term_features)
    config.init()
    installer = Installer(config=config, output=config._output)
    installer.run()
    assert (config.site_pkg_collections_path / "ansible" / "posix").is_dir()
    monkeypatch.setattr(
        "sys.argv",
        [
            "ade",
            "install",
            "--editable",
            str(installable_local_collection),
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
    assert (config.site_pkg_collections_path / "ansible" / "posix").is_symlink()


def test_reinstall_requirements_file(
    tmp_path: Path,
    function_venv: Config,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test that reinstalling works with a requirements file.

    Args:
        tmp_path: A temporary directory.
        function_venv: The function_venv fixture.
        capsys: The capsys fixture.
    """
    galaxy = {
        "collections": [{"name": "ansible.posix"}],
    }
    galaxy_file = tmp_path / "requirements.yml"
    yaml.dump(galaxy, galaxy_file.open("w"))
    function_venv.args.requirement = galaxy_file
    installer = Installer(config=function_venv, output=function_venv._output)
    installer._install_galaxy_requirements()
    captured = capsys.readouterr()
    assert "Removing installed " in captured.out
    assert (function_venv.site_pkg_collections_path / "ansible" / "posix").exists()


def test_reinstall_requirements_file_after_editable(
    tmp_path: Path,
    installable_local_collection: Path,
    output: Output,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that reinstalling works with a requirements file after an editable install.

    Args:
        tmp_path: A temporary directory.
        installable_local_collection: The installable_local_collection fixture.
        output: The output fixture.
        monkeypatch: The monkeypatch fixture.
    """
    monkeypatch.setattr(
        "sys.argv",
        [
            "ade",
            "install",
            "--editable",
            str(installable_local_collection),
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
    assert (config.site_pkg_collections_path / "ansible" / "posix").is_symlink()
    galaxy = {
        "collections": [{"name": "ansible.posix"}],
    }
    galaxy_file = tmp_path / "requirements.yml"
    yaml.dump(galaxy, galaxy_file.open("w"))

    monkeypatch.setattr(
        "sys.argv",
        [
            "ade",
            "install",
            "--requirement",
            str(galaxy_file),
            "--venv",
            str(tmp_path / "venv"),
            "-vvv",
        ],
    )
    cli = Cli()
    cli.parse_args()
    args = cli.args
    config = Config(args=args, output=output, term_features=output.term_features)
    config.init()
    installer = Installer(config=config, output=config._output)
    installer.run()
    assert not (config.site_pkg_collections_path / "ansible" / "posix").is_symlink()


def test_install_requirements_file_failed(
    tmp_path: Path,
    output: Output,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test that reinstalling works with a requirements file after an editable install.

    Args:
        tmp_path: A temporary directory.
        output: The output fixture.
        monkeypatch: The monkeypatch fixture.
        capsys: The capsys fixture.

    """
    galaxy = {
        "collections": [{"name": "ansible.posix"}],
    }
    galaxy_file = tmp_path / "requirements.yml"
    yaml.dump(galaxy, galaxy_file.open("w"))

    monkeypatch.setattr(
        "sys.argv",
        [
            "ade",
            "install",
            "--requirement",
            str(galaxy_file),
            "--venv",
            str(tmp_path / "venv"),
            "-vvv",
        ],
    )

    def mock_subprocess_run(
        **kwargs: Any,  # noqa: ANN401
    ) -> subprocess.CompletedProcess[str]:
        """Raise an exception.

        Args:
            **kwargs: Keyword arguments

        Raises:
            subprocess.CalledProcessError: if requirements file is being installed

        Returns:
            The completed process

        """
        if str(tmp_path / "requirements.yml") in kwargs["command"]:
            raise subprocess.CalledProcessError(1, kwargs["command"])
        return subprocess_run(**kwargs)

    monkeypatch.setattr(
        "ansible_dev_environment.subcommands.installer.subprocess_run",
        mock_subprocess_run,
    )

    cli = Cli()
    cli.parse_args()
    args = cli.args
    config = Config(args=args, output=output, term_features=output.term_features)
    config.init()
    installer = Installer(config=config, output=config._output)

    with pytest.raises(SystemExit):
        installer.run()

    captured = capsys.readouterr()
    assert "Failed to install collection" in captured.err


def test_local_collection_build_fails(
    tmp_path: Path,
    installable_local_collection: Path,
    output: Output,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test that a clean exit occurs if the local collection build fails.

    Args:
        tmp_path: A temporary directory.
        installable_local_collection: The installable_local_collection fixture.
        output: The output fixture.
        monkeypatch: The monkeypatch fixture.
        capsys: The capsys fixture.
    """
    monkeypatch.setattr(
        "sys.argv",
        [
            "ade",
            "install",
            "--editable",
            str(installable_local_collection),
            "--venv",
            str(tmp_path / "venv"),
            "-vvv",
        ],
    )
    args = parse()
    config = Config(args=args, output=output, term_features=output.term_features)
    config.init()
    installer = Installer(config=config, output=config._output)

    def mock_subprocess_run(
        **kwargs: Any,  # noqa: ANN401
    ) -> subprocess.CompletedProcess[str]:
        """Raise an exception.

        Args:
            **kwargs: Keyword arguments

        Raises:
            subprocess.CalledProcessError: if requirements file is being installed

        Returns:
            The completed process

        """
        if "collection build" in kwargs["command"]:
            raise subprocess.CalledProcessError(1, kwargs["command"])
        return subprocess_run(**kwargs)

    monkeypatch.setattr(
        "ansible_dev_environment.subcommands.installer.subprocess_run",
        mock_subprocess_run,
    )

    with pytest.raises(SystemExit):
        installer.run()
    captured = capsys.readouterr()
    assert "Failed to build collection" in captured.err


def test_local_collection_build_no_tar(
    tmp_path: Path,
    installable_local_collection: Path,
    output: Output,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that a clean exit occurs if the local collection build fails.

    Args:
        tmp_path: A temporary directory.
        installable_local_collection: The installable_local_collection fixture.
        output: The output fixture.
        monkeypatch: The monkeypatch fixture.
    """
    monkeypatch.setattr(
        "sys.argv",
        [
            "ade",
            "install",
            "--editable",
            str(installable_local_collection),
            "--venv",
            str(tmp_path / "venv"),
            "-vvv",
        ],
    )
    args = parse()
    config = Config(args=args, output=output, term_features=output.term_features)
    config.init()
    installer = Installer(config=config, output=config._output)

    def mock_subprocess_run(
        **kwargs: Any,  # noqa: ANN401
    ) -> subprocess.CompletedProcess[str]:
        """Raise an exception.

        Args:
            **kwargs: Keyword arguments

        Returns:
            A completed process

        """
        if "collection build" in kwargs["command"]:
            return subprocess.CompletedProcess(
                args=kwargs["command"],
                returncode=0,
                stdout="",
                stderr="",
            )
        return subprocess_run(**kwargs)

    monkeypatch.setattr(
        "ansible_dev_environment.subcommands.installer.subprocess_run",
        mock_subprocess_run,
    )

    with pytest.raises(RuntimeError, match="Expected to find one collection tarball"):
        installer.run()


def test_local_collection_install_fails(
    tmp_path: Path,
    installable_local_collection: Path,
    output: Output,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test that a clean exit occurs if the local collection install fails.

    Args:
        tmp_path: A temporary directory.
        installable_local_collection: The installable_local_collection fixture.
        output: The output fixture.
        monkeypatch: The monkeypatch fixture.
        capsys: The capsys fixture.
    """
    monkeypatch.setattr(
        "sys.argv",
        [
            "ade",
            "install",
            "--editable",
            str(installable_local_collection),
            "--venv",
            str(tmp_path / "venv"),
            "-vvv",
        ],
    )
    args = parse()
    config = Config(args=args, output=output, term_features=output.term_features)
    config.init()
    installer = Installer(config=config, output=config._output)

    def mock_subprocess_run(
        **kwargs: Any,  # noqa: ANN401
    ) -> subprocess.CompletedProcess[str]:
        """Raise an exception.

        Args:
            **kwargs: Keyword arguments

        Raises:
            subprocess.CalledProcessError: if requirements file is being installed

        Returns:
            The completed process

        """
        if "collection install" in kwargs["command"]:
            raise subprocess.CalledProcessError(1, kwargs["command"])
        return subprocess_run(**kwargs)

    monkeypatch.setattr(
        "ansible_dev_environment.subcommands.installer.subprocess_run",
        mock_subprocess_run,
    )

    with pytest.raises(SystemExit):
        installer.run()

    captured = capsys.readouterr()
    assert "Failed to install collection" in captured.err


def test_local_collection_without_tar_install(
    tmp_path: Path,
    installable_local_collection: Path,
    output: Output,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test a collection is installed editable if previously editable.

    This should never happen since the collection tarball is always created and always used
    prior to symlinking the collection. Use os.lstat here to get the mtime of the symlink itself.

    Args:
        tmp_path: A temporary directory.
        installable_local_collection: The installable_local_collection fixture.
        output: The output fixture.
        monkeypatch: The monkeypatch fixture.
    """
    monkeypatch.setattr(
        "sys.argv",
        [
            "ade",
            "install",
            "--editable",
            str(installable_local_collection),
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
    pre_mtime = os.lstat(
        config.site_pkg_collections_path / "ansible" / "posix",
    ).st_mtime

    def install_local_collection(installer: Installer, collection: Collection) -> None:
        """Do nothing.

        Args:
            installer: Installer instance.
            collection: The collection to install.

        """

    monkeypatch.setattr(
        Installer,
        "_install_local_collection",
        install_local_collection,
    )
    installer.run()
    post_mtime = os.lstat(
        config.site_pkg_collections_path / "ansible" / "posix",
    ).st_mtime
    assert post_mtime > pre_mtime


def test_failed_pip_install(
    function_venv: Config,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test a clean exit if the pip install fails.

    Args:
        function_venv: The function_venv fixture.
        monkeypatch: The monkeypatch fixture.
        capsys: The capsys fixture.
    """
    installer = Installer(config=function_venv, output=function_venv._output)

    def mock_subprocess_run(**kwargs: Any) -> subprocess.CompletedProcess[str]:  # noqa: ANN401
        """Raise an exception.

        Args:
            **kwargs: Keyword arguments

        Raises:
            subprocess.CalledProcessError: if pip install is being run

        Returns:
            The completed process

        """
        if "pip install" in kwargs["command"]:
            raise subprocess.CalledProcessError(1, kwargs["command"])
        return subprocess_run(**kwargs)

    monkeypatch.setattr(
        "ansible_dev_environment.subcommands.installer.subprocess_run",
        mock_subprocess_run,
    )

    with pytest.raises(SystemExit):
        installer.run()

    captured = capsys.readouterr()
    assert "Failed to install requirements from" in captured.err
