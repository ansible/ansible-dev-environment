"""Constants, for now, for ansible-dev-environment."""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys

from pathlib import Path
from typing import TYPE_CHECKING

from .utils import subprocess_run


if TYPE_CHECKING:
    from argparse import Namespace

    from .output import Output
    from .utils import TermFeatures


_logger = logging.getLogger(__name__)


def use_uv() -> bool:
    """Return whether to use uv commands like venv or pip.

    Returns:
        True if uv is to be used.
    """
    if int(os.environ.get("SKIP_UV", "0")):
        return False
    try:
        import uv  # noqa: F401
    except ImportError:  # pragma: no cover
        return False
    else:
        _logger.info(
            "UV detected and will be used instead of venv/pip. To disable that define SKIP_UP=1 in your environment.",
        )
        return True


class Config:  # pylint: disable=too-many-instance-attributes
    """The application configuration.

    Attributes:
        pip_cmd: The pip command.
        venv_cmd: The venv command.
    """

    pip_cmd: str
    venv_cmd: str

    def __init__(
        self,
        args: Namespace,
        output: Output,
        term_features: TermFeatures,
    ) -> None:
        """Initialize the configuration.

        Args:
            args: The command line arguments
            output: The output object
            term_features: The terminal features
        """
        self._create_venv: bool = False
        self.args: Namespace = args
        self.bindir: Path
        self._output: Output = output
        self.python_path: Path
        self.site_pkg_path: Path
        self.venv_interpreter: Path
        self.term_features: TermFeatures = term_features

    def init(self) -> None:
        """Initialize the configuration."""
        if self.args.venv:
            self._create_venv = True

        self._set_interpreter()
        self._set_site_pkg_path()

    @property
    def cache_dir(self) -> Path:
        """Return the cache directory."""
        cache_dir = self.venv / ".ansible-dev-environment"
        if not cache_dir.exists():
            cache_dir.mkdir(parents=True)
        return cache_dir

    @property
    def venv(self) -> Path:
        """Return the virtual environment path.

        Raises:
            SystemExit: If the virtual environment cannot be found.
        """
        if self.args.venv:
            return Path(self.args.venv).expanduser().resolve()
        venv_str = os.environ.get("VIRTUAL_ENV")
        if venv_str:
            return Path(venv_str).expanduser().resolve()
        err = "Failed to find a virtual environment."
        self._output.critical(err)
        raise SystemExit(1)  # pragma: no cover # critical exits

    @property
    def venv_cache_dir(self) -> Path:
        """Return the virtual environment cache directory."""
        return self.cache_dir

    @property
    def discovered_python_reqs(self) -> Path:
        """Return the discovered python requirements file."""
        return self.venv_cache_dir / "discovered_requirements.txt"

    @property
    def discovered_bindep_reqs(self) -> Path:
        """Return the discovered system package requirements file."""
        return self.venv_cache_dir / "discovered_bindep.txt"

    @property
    def site_pkg_collections_path(self) -> Path:
        """Return the site packages collection path."""
        site_pkg_collections_path = self.site_pkg_path / "ansible_collections"
        if not site_pkg_collections_path.exists():
            site_pkg_collections_path.mkdir()
        return site_pkg_collections_path

    @property
    def venv_bindir(self) -> Path:
        """Return the virtual environment bin directory."""
        return self.venv / "bin"

    @property
    def interpreter(self) -> Path:
        """Return the current interpreter."""
        return Path(sys.executable)

    @property
    def galaxy_bin(self) -> Path:
        """Find the ansible galaxy command.

        Prefer the venv over the system package over the PATH.

        Raises:
            SystemExit: If the command cannot be found.
        """
        within_venv = self.venv_bindir / "ansible-galaxy"
        if within_venv.exists():
            msg = f"Found ansible-galaxy in virtual environment: {within_venv}"
            self._output.debug(msg)
            return within_venv
        system_pkg = self.site_pkg_path / "bin" / "ansible-galaxy"
        if system_pkg.exists():
            msg = f"Found ansible-galaxy in system packages: {system_pkg}"
            self._output.debug(msg)
            return system_pkg
        last_resort = shutil.which("ansible-galaxy")
        if last_resort:
            msg = f"Found ansible-galaxy in PATH: {last_resort}"
            self._output.debug(msg)
            return Path(last_resort)
        msg = "Failed to find ansible-galaxy."
        self._output.critical(msg)
        raise SystemExit(1)  # pragma: no cover # critical exits

    def _set_interpreter(
        self,
    ) -> None:
        """Set the interpreter."""
        self.pip_cmd = f"{sys.executable} -m pip"
        self.venv_cmd = f"{sys.executable} -m venv"
        if use_uv():
            self.pip_cmd = f"{sys.executable} -m uv pip"
            # seed and python-preference make uv venv match python -m venv behavior:
            self.venv_cmd = f"{sys.executable} -m uv venv --seed --python-preference=system"

        if not self.venv.exists():
            if self._create_venv:
                msg = f"Creating virtual environment: {self.venv}"
                self._output.debug(msg)
                command = f"{self.venv_cmd} {self.venv}"
                msg = f"Creating virtual environment: {self.venv}"
                if self.args.system_site_packages:
                    command = f"{command} --system-site-packages"
                    msg = f"Creating virtual environment with system site packages: {self.venv}"
                try:
                    subprocess_run(
                        command=command,
                        verbose=self.args.verbose,
                        msg=msg,
                        output=self._output,
                    )
                    msg = f"Created virtual environment: {self.venv}"
                    self._output.info(msg)
                except subprocess.CalledProcessError as exc:
                    err = f"Failed to create virtual environment: {exc}"
                    self._output.critical(err)
            else:
                err = f"Cannot find virtual environment: {self.venv}."
                self._output.critical(err)
        msg = f"Virtual environment: {self.venv}"
        self._output.debug(msg)
        venv_interpreter = self.venv / "bin" / "python"
        if not venv_interpreter.exists():
            err = f"Cannot find interpreter: {venv_interpreter}."
            self._output.critical(err)

        msg = f"Virtual environment interpreter: {venv_interpreter}"
        self._output.debug(msg)
        self.venv_interpreter = venv_interpreter

    def _set_site_pkg_path(self) -> None:
        """Use the interpreter to find the site packages path."""
        command = (
            f"{self.venv_interpreter} -c"
            "'import json,sysconfig; print(json.dumps(sysconfig.get_paths()))'"
        )
        work = "Locating site packages directory"
        try:
            proc = subprocess_run(
                command=command,
                verbose=self.args.verbose,
                msg=work,
                output=self._output,
            )
        except subprocess.CalledProcessError as exc:
            err = f"Failed to find site packages path: {exc}"
            self._output.critical(err)

        try:
            sysconfig_paths = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            err = f"Failed to decode json: {exc}"
            self._output.critical(err)

        if not sysconfig_paths:
            err = "Failed to find site packages path."
            self._output.critical(err)

        purelib = sysconfig_paths.get("purelib")
        if not purelib:
            err = "Failed to find purelib in sysconfig paths."
            self._output.critical(err)

        self.site_pkg_path = Path(purelib)
        msg = f"Found site packages path: {self.site_pkg_path}"
        self._output.debug(msg)
