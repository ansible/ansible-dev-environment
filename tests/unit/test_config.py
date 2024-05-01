"""Test the config module."""

from __future__ import annotations

import argparse
import shutil

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from ansible_dev_environment.config import Config


if TYPE_CHECKING:
    from ansible_dev_environment.output import Output


def gen_args(
    venv: str,
    system_site_packages: bool = False,  # noqa: FBT001, FBT002
) -> argparse.Namespace:
    """Generate the arguments.

    Args:
        venv: The virtual environment.
        system_site_packages: Whether to include system site packages.

    Returns:
        The arguments.
    """
    return argparse.Namespace(
        verbose=0,
        venv=venv,
        system_site_packages=system_site_packages,
    )


@pytest.mark.parametrize(
    "system_site_packages",
    ((True, False)),
    ids=["ssp_true", "ssp_false"],
)
def test_paths(
    tmpdir: Path,
    system_site_packages: bool,  # noqa: FBT001
    output: Output,
) -> None:
    """Test the paths.

    Several of the found directories should have a parent of the tmpdir / test_venv

    Args:
        tmpdir: A temporary directory.
        system_site_packages: Whether to include system site packages.
        output: The output fixture.
    """
    venv = tmpdir / "test_venv"
    args = gen_args(
        venv=str(venv),
        system_site_packages=system_site_packages,
    )

    config = Config(args=args, output=output, term_features=output.term_features)
    config.init()

    assert config.venv == venv
    for attr in (
        "site_pkg_collections_path",
        "site_pkg_path",
        "venv_bindir",
        "venv_cache_dir",
        "venv_interpreter",
    ):
        assert venv in getattr(config, attr).parents


def test_galaxy_bin_venv(
    tmpdir: Path,
    monkeypatch: pytest.MonkeyPatch,
    output: Output,
) -> None:
    """Test the galaxy_bin property found in venv.

    Args:
        tmpdir: A temporary directory.
        monkeypatch: A pytest fixture for monkey patching.
        output: The output fixture.
    """
    venv = tmpdir / "test_venv"
    args = gen_args(venv=str(venv))

    config = Config(args=args, output=output, term_features=output.term_features)
    config.init()

    orig_exists = Path.exists
    exists_called = False

    def _exists(path: Path) -> bool:
        if path.name != "ansible-galaxy":
            return orig_exists(path)
        if path.parent == config.venv_bindir:
            nonlocal exists_called
            exists_called = True
            return True
        return False

    monkeypatch.setattr(Path, "exists", _exists)

    assert config.galaxy_bin == venv / "bin" / "ansible-galaxy"
    assert exists_called


def test_galaxy_bin_site(
    tmpdir: Path,
    monkeypatch: pytest.MonkeyPatch,
    output: Output,
) -> None:
    """Test the galaxy_bin property found in site.

    Args:
        tmpdir: A temporary directory.
        monkeypatch: A pytest fixture for monkey patching.
        output: The output fixture.
    """
    venv = tmpdir / "test_venv"
    args = gen_args(venv=str(venv))

    config = Config(args=args, output=output, term_features=output.term_features)
    config.init()

    orig_exists = Path.exists
    exists_called = False

    def _exists(path: Path) -> bool:
        if path.name != "ansible-galaxy":
            return orig_exists(path)
        if path.parent == config.site_pkg_path / "bin":
            nonlocal exists_called
            exists_called = True
            return True
        return False

    monkeypatch.setattr(Path, "exists", _exists)

    assert config.galaxy_bin == config.site_pkg_path / "bin" / "ansible-galaxy"
    assert exists_called


def test_galaxy_bin_path(
    tmpdir: Path,
    monkeypatch: pytest.MonkeyPatch,
    output: Output,
) -> None:
    """Test the galaxy_bin property found in path.

    Args:
        tmpdir: A temporary directory.
        monkeypatch: A pytest fixture for monkey patching.
        output: The output fixture.
    """
    venv = tmpdir / "test_venv"
    args = gen_args(venv=str(venv))

    config = Config(args=args, output=output, term_features=output.term_features)
    config.init()

    orig_exists = Path.exists
    exists_called = False

    def _exists(path: Path) -> bool:
        if path.name != "ansible-galaxy":
            return orig_exists(path)
        nonlocal exists_called
        exists_called = True
        return False

    monkeypatch.setattr(Path, "exists", _exists)

    orig_which = shutil.which
    which_called = False

    def _which(name: str) -> str | None:
        if not name.endswith("ansible-galaxy"):
            return orig_which(name)
        nonlocal which_called
        which_called = True
        return "patched"

    monkeypatch.setattr(shutil, "which", _which)

    assert config.galaxy_bin == Path("patched")
    assert exists_called
    assert which_called


def test_galaxy_bin_not_found(
    tmpdir: Path,
    monkeypatch: pytest.MonkeyPatch,
    output: Output,
) -> None:
    """Test the galaxy_bin property found in venv.

    Args:
        tmpdir: A temporary directory.
        monkeypatch: A pytest fixture for monkey patching.
        output: The output fixture.
    """
    venv = tmpdir / "test_venv"
    args = gen_args(venv=str(venv))

    config = Config(args=args, output=output, term_features=output.term_features)
    config.init()

    orig_exists = Path.exists
    exist_called = False

    def _exists(path: Path) -> bool:
        if path.name == "ansible-galaxy":
            nonlocal exist_called
            exist_called = True
            return False
        return orig_exists(path)

    monkeypatch.setattr(Path, "exists", _exists)

    orig_which = shutil.which
    which_called = False

    def _which(name: str) -> str | None:
        if name.endswith("ansible-galaxy"):
            nonlocal which_called
            which_called = True
            return None
        return orig_which(name)

    monkeypatch.setattr(shutil, "which", _which)

    with pytest.raises(SystemExit) as exc:
        assert config.galaxy_bin is None

    assert exc.value.code == 1
    assert exist_called
    assert which_called
