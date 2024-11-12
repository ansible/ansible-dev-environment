"""Test cli functionality."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from ansible_dev_environment.cli import Cli


if TYPE_CHECKING:
    from collections.abc import Generator


def main(cli: Cli) -> None:
    """Stub main function for testing.

    Args:
        cli: Cli object.
    """
    cli.parse_args()
    cli.init_output()
    cli.args_sanity()
    cli.ensure_isolated()


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


def test_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test term features with tty.

    Args:
        monkeypatch: Pytest fixture.
    """
    monkeypatch.setattr("sys.stdout.isatty", (lambda: True))
    monkeypatch.setattr("os.environ", {"NO_COLOR": ""})
    monkeypatch.setattr("sys.argv", ["ansible-dev-environment", "install"])
    cli = Cli()
    cli.parse_args()
    cli.init_output()
    assert cli.output.term_features.color
    assert cli.output.term_features.links


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
    cli = Cli()
    with pytest.raises(SystemExit):
        main(cli)
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
    cli = Cli()
    cli.parse_args()
    with pytest.raises(SystemExit):
        main(cli)
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
    cli = Cli()
    cli.parse_args()
    with pytest.raises(SystemExit):
        main(cli)
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
    monkeypatch.setattr("sys.argv", ["ansible-dev-environment", "install"])
    cli = Cli()
    cli.parse_args()
    with pytest.raises(SystemExit):
        main(cli)
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
        ["ansible-dev-environment", "install", "--venv", "venv"],
    )
    monkeypatch.setenv("HOME", str(tmp_path))
    collection_root = tmp_path / ".ansible" / "collections" / "ansible_collections"
    (collection_root / "ansible" / "utils").mkdir(parents=True)
    cli = Cli()
    cli.parse_args()
    with pytest.raises(SystemExit):
        main(cli)
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
        ["ansible-dev-environment", "install", "--venv", "venv"],
    )
    cli = Cli()
    cli.parse_args()
    with pytest.raises(SystemExit):
        main(cli)
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
        ["ansible-dev-environment", "install"],
    )
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)
    cli = Cli()
    cli.parse_args()
    with pytest.raises(SystemExit):
        main(cli)
    captured = capsys.readouterr()
    assert "Unable to use user site packages directory" in captured.err


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
        cli._exit()
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
        cli._exit()
    expected = 2
    assert excinfo.value.code == expected
    captured = capsys.readouterr()
    assert "Test warning" in captured.out
