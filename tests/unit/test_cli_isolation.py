"""Tests specific to isolation."""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path
from typing import TYPE_CHECKING

from ansible_dev_environment.cli import Cli
from ansible_dev_environment.definitions import COLLECTIONS_PATH as CP
from ansible_dev_environment.definitions import AnsibleCfg


if TYPE_CHECKING:
    from pathlib import Path

    import pytest


ARGS = Namespace(
    isolation_mode="cfg",
    log_append=False,
    log_file="/dev/null",
    log_level="warning",
    verbose=0,
)


def test_acfg_cwd_new(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test the creation of a new ansible.cfg in the cwd.

    Args:
        tmp_path: Pytest fixture.
        monkeypatch: Pytest fixture for monkey patching.
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

    test_path = cli.acfg_cwd.path

    assert cli.isolation_check() is True
    assert test_path.exists() is True
    assert cli.isolation_check() is True
    assert test_path.read_text() == f"[defaults]\n{CP}\n"
    assert cli.acfg_trusted == test_path


def test_acfg_cwd_modified(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test the update of an existing ansible.cfg in the cwd.

    Args:
        tmp_path: Pytest fixture.
        monkeypatch: Pytest fixture for monkey patching.
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


def test_acfg_home_modified(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test the update of an existing ansible.cfg in $HOME.

    Args:
        tmp_path: Pytest fixture.
        monkeypatch: Pytest fixture for monkey patching.
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

    with cli.acfg_home.path.open(mode="w") as f:
        f.write("# comment\n")

    expected = f"[defaults]\n{CP}\n# comment\n"

    test_path = cli.acfg_home.path

    assert cli.isolation_check() is True
    assert test_path.read_text() == expected
    assert cli.acfg_trusted == test_path
    cli.acfg_trusted = tmp_path

    with test_path.open(mode="w") as f:
        f.write("[defaults]\n")
        f.write("collections_paths = /tmp/collections\n")
        f.write("# comment\n")

    assert cli.isolation_check() is True
    assert test_path.read_text() == expected
    assert cli.acfg_trusted == test_path


def test_acfg_system_ok(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test collections_path in a system ansible.cfg.

    Args:
        tmp_path: Pytest fixture.
        monkeypatch: Pytest fixture for monkey patching.
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

    test_path = cli.acfg_system.path

    with test_path.open(mode="w") as f:
        f.write(f"[defaults]\n{CP}\n")

    assert cli.isolation_check() is True
    assert cli.acfg_trusted == test_path
