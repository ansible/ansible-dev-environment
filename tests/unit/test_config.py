"""Test the config module."""

from __future__ import annotations

import argparse
import copy
import json
import shutil
import subprocess

from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from ansible_dev_environment.config import Config
from ansible_dev_environment.utils import subprocess_run


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


def test_venv_from_env_var(
    monkeypatch: pytest.MonkeyPatch,
    session_venv: Config,
    output: Output,
) -> None:
    """Test the venv property found in the environment variable.

    Reuse the venv from the session_venv fixture.

    Args:
        monkeypatch: A pytest fixture for patching.
        session_venv: The session venv fixture.
        output: The output fixture.
    """
    venv = session_venv.venv

    args = gen_args(venv="")
    monkeypatch.setenv("VIRTUAL_ENV", str(venv))

    config = Config(args=args, output=output, term_features=output.term_features)
    config.init()

    assert config.venv == venv


def test_venv_not_found(
    output: Output,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test the venv  not found.

    Args:
        output: The output fixture.
        capsys: A pytest fixture for capturing stdout and stderr.
        monkeypatch: A pytest fixture for patching.
    """
    args = gen_args(venv="")
    config = Config(args=args, output=output, term_features=output.term_features)
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)

    with pytest.raises(SystemExit) as exc:
        config.init()

    assert exc.value.code == 1
    assert "Failed to find a virtual environment." in capsys.readouterr().err


def test_venv_creation_failed(
    tmp_path: Path,
    output: Output,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test the venv creation failed.

    Args:
        tmp_path: A temporary directory.
        output: The output fixture.
        monkeypatch: A pytest fixture for patching.
        capsys: A pytest fixture for capturing stdout and stderr.
    """
    args = gen_args(venv=str(tmp_path / "test_venv"))

    orig_subprocess_run = subprocess_run

    def mock_subprocess_run(
        *args: Any,  # noqa: ANN401
        **kwargs: Any,  # noqa: ANN401
    ) -> subprocess.CompletedProcess[str]:
        """Mock the subprocess.run function.

        Args:
            *args: The positional arguments.
            **kwargs: The keyword arguments.

        Raises:
            subprocess.CalledProcessError: For the venv command
        Returns:
            The completed process.

        """
        if "venv" in kwargs["command"]:
            raise subprocess.CalledProcessError(1, kwargs["command"])
        return orig_subprocess_run(*args, **kwargs)

    monkeypatch.setattr("ansible_dev_environment.config.subprocess_run", mock_subprocess_run)
    config = Config(args=args, output=output, term_features=output.term_features)

    with pytest.raises(SystemExit) as exc:
        config.init()

    assert exc.value.code == 1
    assert "Failed to create virtual environment" in capsys.readouterr().err


def test_venv_env_var_wrong(
    output: Output,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Test VIRTUAL_ENV points to a non-existent venv.

    Args:
        output: The output fixture.
        capsys: A pytest fixture for capturing stdout and stderr.
        monkeypatch: A pytest fixture for patching.
        tmp_path: A temporary directory
    """
    args = gen_args(venv="")
    config = Config(args=args, output=output, term_features=output.term_features)
    monkeypatch.setenv("VIRTUAL_ENV", str(tmp_path / "test_venv"))

    with pytest.raises(SystemExit) as exc:
        config.init()

    assert exc.value.code == 1
    assert "Cannot find virtual environment" in capsys.readouterr().err


def test_venv_env_var_missing_interpreter(
    output: Output,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Test VIRTUAL_ENV points to a directory without a python interpreter.

    Args:
        output: The output fixture.
        capsys: A pytest fixture for capturing stdout and stderr.
        monkeypatch: A pytest fixture for patching.
        tmp_path: A temporary directory
    """
    args = gen_args(venv="")
    config = Config(args=args, output=output, term_features=output.term_features)
    venv = tmp_path / "test_venv"
    venv.mkdir()
    monkeypatch.setenv("VIRTUAL_ENV", str(venv))

    with pytest.raises(SystemExit) as exc:
        config.init()

    assert exc.value.code == 1
    assert "Cannot find interpreter" in capsys.readouterr().err


def test_sys_packages_path_fail_call(
    session_venv: Config,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test the system site packages path.

    Args:
        session_venv: The session venv fixture.
        monkeypatch: A pytest fixture for patching.
        capsys: A pytest fixture for capturing stdout and stderr.
    """
    orig_subprocess_run = subprocess_run

    def mock_subprocess_run(
        *args: Any,  # noqa: ANN401
        **kwargs: Any,  # noqa: ANN401
    ) -> subprocess.CompletedProcess[str]:
        """Mock the subprocess.run function.

        Args:
            *args: The positional arguments.
            **kwargs: The keyword arguments.

        Raises:
            subprocess.CalledProcessError: For the venv command
        Returns:
            The completed process.

        """
        if "sysconfig.get_paths" in kwargs["command"]:
            raise subprocess.CalledProcessError(1, kwargs["command"])
        return orig_subprocess_run(*args, **kwargs)

    monkeypatch.setattr("ansible_dev_environment.config.subprocess_run", mock_subprocess_run)

    copied_config = copy.deepcopy(session_venv)

    with pytest.raises(SystemExit) as exc:
        copied_config._set_site_pkg_path()

    assert exc.value.code == 1
    assert "Failed to find site packages path" in capsys.readouterr().err


def test_sys_packages_path_fail_invalid_json(
    session_venv: Config,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test the system site packages path when the json is invalid.

    Args:
        session_venv: The session venv fixture.
        monkeypatch: A pytest fixture for patching.
        capsys: A pytest fixture for capturing stdout and stderr.
    """
    orig_subprocess_run = subprocess_run

    def mock_subprocess_run(
        *args: Any,  # noqa: ANN401
        **kwargs: Any,  # noqa: ANN401
    ) -> subprocess.CompletedProcess[str]:
        """Mock the subprocess.run function.

        Args:
            *args: The positional arguments.
            **kwargs: The keyword arguments.

        Raises:
            subprocess.CalledProcessError: For the venv command
        Returns:
            The completed process.

        """
        if "sysconfig.get_paths" in kwargs["command"]:
            return subprocess.CompletedProcess(
                args=kwargs["command"],
                returncode=0,
                stdout="invalid json",
                stderr="",
            )
        return orig_subprocess_run(*args, **kwargs)

    monkeypatch.setattr("ansible_dev_environment.config.subprocess_run", mock_subprocess_run)

    copied_config = copy.deepcopy(session_venv)

    with pytest.raises(SystemExit) as exc:
        copied_config._set_site_pkg_path()

    assert exc.value.code == 1
    assert "Failed to decode json" in capsys.readouterr().err


def test_sys_packages_path_fail_empty(
    session_venv: Config,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test the system site packages path when the json is empty.

    Args:
        session_venv: The session venv fixture.
        monkeypatch: A pytest fixture for patching.
        capsys: A pytest fixture for capturing stdout and stderr.
    """
    orig_subprocess_run = subprocess_run

    def mock_subprocess_run(
        *args: Any,  # noqa: ANN401
        **kwargs: Any,  # noqa: ANN401
    ) -> subprocess.CompletedProcess[str]:
        """Mock the subprocess.run function.

        Args:
            args: The positional arguments.
            kwargs: The keyword arguments.

        Raises:
            subprocess.CalledProcessError: For the get_paths command
        Returns:
            The completed process.

        """
        if "sysconfig.get_paths" in kwargs["command"]:
            return subprocess.CompletedProcess(
                args=kwargs["command"],
                returncode=0,
                stdout="[]",
                stderr="",
            )
        return orig_subprocess_run(*args, **kwargs)

    monkeypatch.setattr("ansible_dev_environment.config.subprocess_run", mock_subprocess_run)

    copied_config = copy.deepcopy(session_venv)

    with pytest.raises(SystemExit) as exc:
        copied_config._set_site_pkg_path()

    assert exc.value.code == 1
    assert "Failed to find site packages path" in capsys.readouterr().err


def test_sys_packages_path_missing_purelib(
    session_venv: Config,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test the system site packages path when the json is empty.

    Args:
        session_venv: The session venv fixture.
        monkeypatch: A pytest fixture for patching.
        capsys: A pytest fixture for capturing stdout and stderr.
    """
    orig_subprocess_run = subprocess_run

    def mock_subprocess_run(
        *args: Any,  # noqa: ANN401
        **kwargs: Any,  # noqa: ANN401
    ) -> subprocess.CompletedProcess[str]:
        """Mock the subprocess.run function.

        Args:
            *args: The positional arguments.
            **kwargs: The keyword arguments.

        Raises:
            subprocess.CalledProcessError: For the sysconfig command
        Returns:
            The completed process.

        """
        if "sysconfig.get_paths" in kwargs["command"]:
            response = {
                "stdlib": "/usr/lib64/python3.12",
                "platstdlib": "/home/user/ansible-dev-environment/venv/lib64/python3.12",
                "_purelib": "/home/user/ansible-dev-environment/venv/lib/python3.12/site-packages",
                "platlib": "/home/user/ansible-dev-environment/venv/lib64/python3.12/site-packages",
                "include": "/usr/include/python3.12",
                "platinclude": "/usr/include/python3.12",
                "scripts": "/home/user/ansible-dev-environment/venv/bin",
                "data": "/home/user/github/ansible-dev-environment/venv",
            }
            return subprocess.CompletedProcess(
                args=kwargs["command"],
                returncode=0,
                stdout=json.dumps(response),
                stderr="",
            )
        return orig_subprocess_run(*args, **kwargs)

    monkeypatch.setattr("ansible_dev_environment.config.subprocess_run", mock_subprocess_run)

    copied_config = copy.deepcopy(session_venv)

    with pytest.raises(SystemExit) as exc:
        copied_config._set_site_pkg_path()

    assert exc.value.code == 1
    assert "Failed to find purelib in sysconfig paths" in capsys.readouterr().err
