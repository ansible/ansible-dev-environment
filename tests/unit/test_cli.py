"""Test cli functionality."""

from __future__ import annotations

import io

from pathlib import Path
from typing import TYPE_CHECKING

import argcomplete
import pytest

from ansible_dev_environment.arg_parser import ArgumentParser, apply_envvars, parse
from ansible_dev_environment.cli import Cli, main


if TYPE_CHECKING:
    from collections.abc import Generator


def test_cpi(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test the cpi option.

    Args:
        monkeypatch: Pytest fixture.
    """
    monkeypatch.setattr("sys.argv", ["ansible-dev-environment", "install", "--cpi"])
    cli = Cli()
    cli.parse_args()
    assert cli.args.requirement.parts[-3:] == (
        "ansible-dev-environment",
        ".config",
        "source-requirements.yml",
    )


@pytest.mark.filterwarnings("ignore")
def test_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test term features with tty.

    Args:
        monkeypatch: Pytest fixture.
    """
    monkeypatch.setattr("sys.stdout.isatty", (lambda: True))
    monkeypatch.setattr("os.environ", {"NO_COLOR": "anything"})
    monkeypatch.setattr("sys.argv", ["ansible-dev-environment", "install"])
    cli = Cli()
    cli.parse_args()
    cli.init_output()
    assert not cli.output.term_features.color
    assert not cli.output.term_features.links


@pytest.mark.usefixtures("_wide_console")
def test_missing_requirements(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Test the missing requirements file.

    Args:
        capsys: Pytest stdout capture fixture.
        monkeypatch: Pytest fixture.
        tmp_path: Pytest fixture.
    """
    requirements_file = tmp_path / "requirements.yml"
    monkeypatch.setattr(
        "sys.argv",
        ["ansible-dev-environment", "install", "-r", str(requirements_file)],
    )
    match = f"Requirements file not found: {requirements_file}"
    with pytest.raises(SystemExit):
        main(dry=True)
    captured = capsys.readouterr()
    assert match in captured.err


def test_editable_many(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test the editable option with too many arguments.

    Args:
        capsys: Pytest stdout capture fixture.
        monkeypatch: Pytest fixture.
    """
    monkeypatch.setattr(
        "sys.argv",
        ["ansible-dev-environment", "install", "--venv", "venv", "-e", "one", "two"],
    )
    with pytest.raises(SystemExit):
        main(dry=True)
    captured = capsys.readouterr()
    assert "Editable can only be used with a single collection specifier." in captured.err


def test_editable_requirements(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Test the editable option with requirements file.

    Args:
        capsys: Pytest stdout capture fixture.
        monkeypatch: Pytest fixture.
        tmp_path: Pytest fixture.
    """
    requirements_file = tmp_path / "requirements.yml"
    requirements_file.touch()
    monkeypatch.setattr(
        "sys.argv",
        ["ansible-dev-environment", "install", "-r", str(requirements_file), "-e"],
    )
    with pytest.raises(SystemExit):
        main(dry=True)
    captured = capsys.readouterr()
    assert "Editable can not be used with a requirements file." in captured.err


@pytest.mark.parametrize(
    "env_var",
    (
        "ANSIBLE_COLLECTIONS_PATHS",
        "ANSIBLE_COLLECTION_PATH",
    ),
)
def test_acp_env_var_set(
    env_var: str,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test the ansible collection path environment variable set.

    Args:
        env_var: Environment variable name.
        capsys: Pytest stdout capture fixture.
        monkeypatch: Pytest fixture.
    """
    monkeypatch.setenv(env_var, "test")
    monkeypatch.setattr("sys.argv", ["ansible-dev-environment", "install", "--im", "restrictive"])
    with pytest.raises(SystemExit):
        main(dry=True)
    captured = capsys.readouterr()
    assert f"{env_var} is set" in captured.err


@pytest.mark.usefixtures("_wide_console")
def test_collections_in_home(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Test the collections in home directory.

    Args:
        capsys: Pytest stdout capture fixture.
        monkeypatch: Pytest fixture.
        tmp_path: Pytest fixture.
    """
    monkeypatch.setattr(
        "sys.argv",
        ["ansible-dev-environment", "install", "--venv", "venv", "--im", "restrictive"],
    )
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("ANSIBLE_HOME", str(tmp_path / ".ansible"))
    collection_root = tmp_path / ".ansible" / "collections" / "ansible_collections"
    (collection_root / "ansible" / "utils").mkdir(parents=True)
    with pytest.raises(SystemExit):
        main(dry=True)
    captured = capsys.readouterr()
    msg = f"Collections found in {collection_root}"
    assert msg in captured.err


def test_collections_in_user(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test the collections in user directory.

    Args:
        capsys: Pytest stdout capture fixture.
        monkeypatch: Pytest fixture.
    """
    usr_path = Path("/usr/share/ansible/collections")
    exists = Path.exists

    def _exists(path: Path) -> bool:
        """Patch the exists method.

        Args:
            path: Path object.

        Returns:
            bool: True if the path exists.
        """
        if path == usr_path:
            return True
        return exists(path)

    monkeypatch.setattr(Path, "exists", _exists)

    iterdir = Path.iterdir

    def _iterdir(path: Path) -> list[Path] | Generator[Path, None, None]:
        """Patch the iterdir method.

        Args:
            path: Path object.

        Returns:
            List of paths or generator.
        """
        if path == usr_path:
            return [usr_path / "ansible_collections"]
        return iterdir(path)

    monkeypatch.setattr(Path, "iterdir", _iterdir)

    monkeypatch.setattr(
        "sys.argv",
        ["ansible-dev-environment", "install", "--venv", "venv", "--im", "restrictive"],
    )
    with pytest.raises(SystemExit):
        main(dry=True)
    captured = capsys.readouterr()
    msg = f"Collections found in {usr_path}"
    assert msg in captured.err


def test_no_venv_specified(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test no virtual environment specified.

    Args:
        capsys: Pytest stdout capture fixture.
        monkeypatch: Pytest fixture.
    """
    monkeypatch.setattr(
        "sys.argv",
        ["ansible-dev-environment", "install", "-vvv"],
    )
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)
    main(dry=True)
    captured = capsys.readouterr()

    found = [line for line in captured.out.splitlines() if "Debug: venv: " in line]
    assert len(found) == 1
    assert found[0].endswith(".venv")


def test_exit_code_one(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test exit code one.

    Args:
        capsys: Pytest stdout capture fixture.
        monkeypatch: Pytest fixture.
    """
    monkeypatch.setattr(
        "sys.argv",
        ["ansible-dev-environment", "install"],
    )
    cli = Cli()
    cli.parse_args()
    cli.init_output()
    cli.output.error("Test error")
    with pytest.raises(SystemExit) as excinfo:
        cli.exit()
    expected = 1
    assert excinfo.value.code == expected
    captured = capsys.readouterr()
    assert "Test error" in captured.err


def test_exit_code_two(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test exit code two.

    Args:
        capsys: Pytest stdout capture fixture.
        monkeypatch: Pytest fixture.
    """
    monkeypatch.setattr(
        "sys.argv",
        ["ansible-dev-environment", "install"],
    )
    cli = Cli()
    cli.parse_args()
    cli.init_output()
    cli.output.warning("Test warning")
    with pytest.raises(SystemExit) as excinfo:
        cli.exit()
    expected = 2
    assert excinfo.value.code == expected
    captured = capsys.readouterr()
    assert "Test warning" in captured.out


def test_envvar_mapping_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test environment mapping error.

    Args:
        monkeypatch: Pytest fixture.
    """
    monkeypatch.setattr(
        "ansible_dev_environment.arg_parser.ENVVAR_MAPPING",
        {"foo": "FOO"},
    )
    monkeypatch.setattr(
        "sys.argv",
        ["ansible-dev-environment", "install"],
    )
    cli = Cli()
    with pytest.raises(NotImplementedError):
        cli.parse_args()


def test_apply_envvar_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test environment mapping error.

    Args:
        monkeypatch: Pytest fixture.
    """
    monkeypatch.setattr(
        "ansible_dev_environment.arg_parser.ENVVAR_MAPPING",
        {"foo": "FOO"},
    )
    monkeypatch.setenv("FOO", "42.0")

    parser = ArgumentParser()
    parser.add_argument("--foo", type=float, help="helpless")

    with pytest.raises(NotImplementedError) as excinfo:
        apply_envvars(args=[], parser=parser)

    assert "not implemented for envvar FOO" in str(excinfo.value)


def test_env_wrong_type(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test wrong type.

    Args:
        monkeypatch: Pytest fixture.
        capsys: Pytest stdout capture fixture.
    """
    monkeypatch.setattr(
        "sys.argv",
        ["ansible-dev-environment", "install"],
    )
    monkeypatch.setenv("ADE_VERBOSE", "not_an_int")
    cli = Cli()
    with pytest.raises(SystemExit):
        cli.parse_args()
    captured = capsys.readouterr()
    assert "could not convert to int" in captured.err


def test_env_wrong_choice(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test wrong choice.

    Args:
        monkeypatch: Pytest fixture.
        capsys: Pytest stdout capture fixture.
    """
    monkeypatch.setattr(
        "sys.argv",
        ["ansible-dev-environment", "install"],
    )
    monkeypatch.setenv("ADE_ISOLATION_MODE", "wrong_choice")
    cli = Cli()
    with pytest.raises(SystemExit):
        cli.parse_args()
    captured = capsys.readouterr()
    assert "choose from 'restrictive', 'cfg', 'none'" in captured.err


def test_arg_complete(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test argument completion.

    Args:
        monkeypatch: Pytest fixture.
    """
    inited_parser = None
    orig_apply_envvars = apply_envvars

    def _apply_envvars(
        args: list[str],
        parser: ArgumentParser,
    ) -> None:
        """Apply environment variables to the argument parser.

        Args:
            args: List of arguments.
            parser: Argument parser.
        """
        nonlocal inited_parser
        inited_parser = parser
        orig_apply_envvars(args, parser)

    monkeypatch.setattr(
        "ansible_dev_environment.arg_parser.apply_envvars",
        _apply_envvars,
    )

    monkeypatch.setattr(
        "sys.argv",
        ["ade", "install"],
    )
    parse()

    cli = "ade ins"
    monkeypatch.setenv("_ARGCOMPLETE", "1")
    monkeypatch.setenv("_ARGCOMPLETE_IFS", "\013")
    monkeypatch.setenv("COMP_LINE", cli)
    monkeypatch.setenv("COMP_POINT", str(len(cli)))

    str_io = io.StringIO()

    argcomplete.autocomplete(inited_parser, exit_method=print, output_stream=str_io)  # type: ignore[arg-type]

    output = str_io.getvalue()
    assert "inspect" in output
    assert "install" in output
