"""Tests specific to isolation."""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from ansible_dev_environment.cli import Cli
from ansible_dev_environment.definitions import COLLECTIONS_PATH as CP
from ansible_dev_environment.definitions import AnsibleCfg


if TYPE_CHECKING:
    from pathlib import Path


ARGS = Namespace(
    isolation_mode="cfg",
    log_append=False,
    log_file="/dev/null",
    log_level="warning",
    verbose=0,
)


@pytest.fixture(name="cli")
def init_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Cli:
    """Fixture to mock the CLI for testing.

    Args:
        tmp_path: Pytest fixture.
        monkeypatch: Pytest fixture for monkey patching.

    Returns:
        Cli: Mocked CLI instance.
    """
    cwd = tmp_path / "cwd"
    home = tmp_path / "home"
    system = tmp_path / "system"
    cwd.mkdir()
    home.mkdir()
    system.mkdir()

    monkeypatch.chdir(cwd)
    monkeypatch.delenv("ANSIBLE_CONFIG", raising=False)

    cli = Cli()
    cli.args = ARGS
    cli.acfg_cwd = AnsibleCfg(path=cwd / "ansible.cfg")
    cli.acfg_home = AnsibleCfg(path=home / "ansible.cfg")
    cli.acfg_system = AnsibleCfg(path=system / "ansible.cfg")
    cli.init_output()
    return cli


def test_acfg_cwd_new(cli: Cli) -> None:
    """Test the creation of a new ansible.cfg in the cwd.

    Args:
        cli: A Cli instance from a fixture
    """
    test_path = cli.acfg_cwd.path

    assert cli.isolation_check() is True
    assert test_path.exists() is True
    assert cli.isolation_check() is True
    assert test_path.read_text() == f"[defaults]\n{CP}\n"
    assert cli.acfg_trusted == test_path


def test_acfg_cwd_modified(cli: Cli) -> None:
    """Test the update of an existing ansible.cfg in the cwd.

    Args:
        cli: A Cli instance from a fixture
    """
    test_path = cli.acfg_cwd.path

    with test_path.open(mode="w") as f:
        f.write("# comment\n")

    expected = f"[defaults]\n{CP}\n# comment\n"

    assert cli.isolation_check() is True
    assert test_path.read_text() == expected

    with test_path.open(mode="w") as f:
        f.write("[defaults]\n")
        f.write("collections_paths = /tmp/collections\n")
        f.write("# comment\n")

    assert cli.isolation_check() is True
    assert test_path.read_text() == expected
    assert cli.acfg_trusted == test_path


def test_acfg_home_modified(cli: Cli) -> None:
    """Test the update of an existing ansible.cfg in $HOME.

    Args:
        cli: A Cli instance from a fixture
    """
    with cli.acfg_home.path.open(mode="w") as f:
        f.write("# comment\n")

    expected = f"[defaults]\n{CP}\n# comment\n"

    test_path = cli.acfg_home.path

    assert cli.isolation_check() is True
    assert test_path.read_text() == expected
    assert cli.acfg_trusted == test_path
    cli.acfg_trusted = test_path.parent

    with test_path.open(mode="w") as f:
        f.write("[defaults]\n")
        f.write("collections_paths = /tmp/collections\n")
        f.write("# comment\n")

    assert cli.isolation_check() is True
    assert test_path.read_text() == expected
    assert cli.acfg_trusted == test_path


def test_acfg_system_ok(cli: Cli) -> None:
    """Test collections_path in a system ansible.cfg.

    Args:
        cli: A Cli instance from a fixture
    """
    test_path = cli.acfg_system.path

    with test_path.open(mode="w") as f:
        f.write(f"[defaults]\n{CP}\n")

    assert cli.isolation_check() is True
    assert cli.acfg_trusted == test_path


def test_isolation_none(cli: Cli) -> None:
    """Test isolation_none method.

    Args:
        cli: A Cli instance from a fixture
    """
    cli.args.isolation_mode = "none"
    assert cli.isolation_check() is True
    assert cli.acfg_trusted is None


def test_invalid_isolation_mode(cli: Cli) -> None:
    """Test invalid isolation mode.

    Args:
        cli: A Cli instance from a fixture
    """
    cli.args.isolation_mode = "invalid"
    assert cli.isolation_check() is False
    assert cli.acfg_trusted is None


def test_isolation_cfg_with_env_var(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Test isolation_cfg method with ANSIBLE_CONFIG environment variable.

    Args:
        monkeypatch: Pytest fixture for monkey patching.
        tmp_path: Pytest fixture for temporary file paths.
    """
    cli = Cli()
    cli.args = ARGS
    cli.init_output()

    monkeypatch.setenv("ANSIBLE_CONFIG", str(tmp_path / "ansible.cfg"))

    assert cli.isolation_check() is False
    assert cli.acfg_trusted is None
