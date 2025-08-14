"""Constants, for now, for ansible-dev-environment."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys

from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING

from .utils import subprocess_run


if TYPE_CHECKING:
    from argparse import Namespace

    from .output import Output
    from .utils import TermFeatures


class Config:  # pylint: disable=too-many-instance-attributes
    """The application configuration."""

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
        self.specified_python: str | Path | None = None
        self.venv_interpreter: Path
        self.term_features: TermFeatures = term_features

    def init(self) -> None:
        """Initialize the configuration."""
        if self.args.subcommand == "install":
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
        """Return the virtual environment path."""
        return Path(self.args.venv).expanduser().resolve()

    @property
    def venv_cache_dir(self) -> Path:
        """Return the virtual environment cache directory."""
        return self.cache_dir

    @property
    def venv_pip_cmd(self) -> str:
        """Return the pip command for the virtual environment.

        Returns:
            The pip command for the virtual environment.
        """
        if self.uv_available:
            return "uv pip"
        return f"{self.venv}/bin/python -m pip"

    @property
    def venv_pip_install_cmd(self) -> str:
        """Return the pip install command for the virtual environment.

        Returns:
            The pip install command for the virtual environment.
        """
        if self.uv_available:
            return f"{self.venv_pip_cmd} install --python {self.venv_interpreter}"
        return f"{self.venv_pip_cmd} install"

    @cached_property
    def uv_available(self) -> bool:
        """Return whether to use uv commands like venv or pip.

        Returns:
            True if uv is to be used.
        """
        if self.args.uv is False:
            self._output.debug("uv is disabled.")
            return False

        if not (uv_path := shutil.which("uv")):
            self._output.debug("uv is not available in the environment.")
            return False

        self._output.debug(f"uv is available at {uv_path}")
        self._output.info(
            "uv is available and will be used instead of venv/pip. Disable with 'ADE_UV=0' or '--uv false'.",
        )
        return True

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
        self._locate_python()
        if self.specified_python is None:
            venv_cmd = (
                "uv venv --seed --python-preference=system"
                if self.uv_available
                else f"{sys.executable} -m venv"
            )
        else:
            venv_cmd = (
                f"uv venv --seed --python-preference=system --python {self.specified_python}"
                if self.uv_available
                else f"{self.specified_python} -m venv"
            )

        if self.venv.exists() and self.specified_python:
            err = "User specified python cannot be used with an existing virtual environment."
            self._output.critical(err)
            return  # pragma: no cover # critical exits

        if not self.venv.exists() and not self._create_venv:
            err = f"Cannot find virtual environment: {self.venv}."
            self._output.critical(err)
            return  # pragma: no cover # critical exits

        if not self.venv.exists():
            msg = f"Creating virtual environment: {self.venv}"
            command = f"{venv_cmd} {self.venv}"
            if self.args.system_site_packages:
                command = f"{command} --system-site-packages"
                msg += " with system site packages"
            self._output.debug(msg)
            try:
                subprocess_run(
                    command=command,
                    verbose=self.args.verbose,
                    msg=msg,
                    output=self._output,
                )
                msg = f"Created virtual environment: {self.venv}"
                if self.specified_python:
                    msg += f" using {self.specified_python}"
                self._output.note(msg)
            except subprocess.CalledProcessError as exc:
                err = f"Failed to create virtual environment: {exc.stdout} {exc.stderr}"
                self._output.critical(err)
                return  # pragma: no cover # critical exits

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

    def _locate_python(self) -> None:
        """Locate the python interpreter.

        1) If not user provided default to system
        2) If it is a path and exists, use that
        3) If it starts with python and uv, use that
        4) If it starts with python and pip, use that
        5) If it is a version and uv, use that
        6) If it is a version and pip, and found, use that

        """
        python_arg = getattr(self.args, "python", None)
        if not python_arg:
            return

        if Path(python_arg).exists():
            self.specified_python = Path(python_arg).expanduser().resolve()
        elif python_arg.lower().startswith("python"):
            if self.uv_available:
                self.specified_python = python_arg
            elif path := shutil.which(python_arg):
                self.specified_python = path
            else:
                msg = f"Cannot find specified python interpreter. ({python_arg})"
                self._output.critical(msg)
                return  # pragma: no cover # critical exits
        else:
            possible = f"python{python_arg}"
            if self.uv_available:
                self.specified_python = possible
            elif path := shutil.which(possible):
                self.specified_python = path
            else:
                msg = f"Cannot find specified python interpreter. ({possible})"
                self._output.critical(msg)
                return  # pragma: no cover # critical exits
        self._output.debug(
            f"Using specified python interpreter: {self.specified_python}",
        )
        return
