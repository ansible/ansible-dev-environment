"""Constants, for now, for pip4a."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys

from pathlib import Path
from typing import TYPE_CHECKING

from .utils import subprocess_run


if TYPE_CHECKING:
    from argparse import Namespace

    from .utils import TermFeatures

logger = logging.getLogger(__name__)


class Config:
    """The application configuration."""

    # pylint: disable=too-many-instance-attributes
    def __init__(
        self: Config,
        args: Namespace,
        term_features: TermFeatures,
    ) -> None:
        """Initialize the configuration."""
        self._create_venv: bool = False
        self.args: Namespace = args
        self.bindir: Path
        self.python_path: Path
        self.site_pkg_path: Path
        self.venv_interpreter: Path
        self.term_features: TermFeatures = term_features

    def init(self: Config) -> None:
        """Initialize the configuration."""
        if self.args.venv:
            self._create_venv = True

        self._set_interpreter()
        self._set_site_pkg_path()

    @property
    def cache_dir(self: Config) -> Path:
        """Return the cache directory."""
        cache_dir = self.venv / ".pip4a"
        if not cache_dir.exists():
            cache_dir.mkdir(parents=True)
        return cache_dir

    @property
    def venv(self: Config) -> Path:
        """Return the virtual environment path."""
        if self.args.venv:
            return Path(self.args.venv).expanduser().resolve()
        venv_str = os.environ.get("VIRTUAL_ENV")
        if venv_str:
            return Path(venv_str).expanduser().resolve()
        err = "Failed to find a virtual environment."
        logger.critical(err)
        sys.exit(1)

    @property
    def venv_cache_dir(self: Config) -> Path:
        """Return the virtual environment cache directory."""
        return self.cache_dir

    @property
    def discovered_python_reqs(self: Config) -> Path:
        """Return the discovered python requirements file."""
        return self.venv_cache_dir / "discovered_requirements.txt"

    @property
    def discovered_bindep_reqs(self: Config) -> Path:
        """Return the discovered system package requirements file."""
        return self.venv_cache_dir / "discovered_bindep.txt"

    @property
    def site_pkg_collections_path(self: Config) -> Path:
        """Return the site packages collection path."""
        site_pkg_collections_path = self.site_pkg_path / "ansible_collections"
        if not site_pkg_collections_path.exists():
            site_pkg_collections_path.mkdir()
        return site_pkg_collections_path

    @property
    def venv_bindir(self: Config) -> Path:
        """Return the virtual environment bin directory."""
        return self.venv / "bin"

    @property
    def interpreter(self: Config) -> Path:
        """Return the current interpreter."""
        return Path(sys.executable)

    def _set_interpreter(
        self: Config,
    ) -> None:
        """Set the interpreter."""
        if not self.venv.exists():
            if self._create_venv:
                msg = f"Creating virtual environment: {self.venv}"
                logger.debug(msg)
                command = f"python -m venv {self.venv}"
                work = "Creating virtual environment"
                try:
                    subprocess_run(
                        command=command,
                        verbose=self.args.verbose,
                        msg=work,
                        term_features=self.term_features,
                    )
                    msg = f"Created virtual environment: {self.venv}"
                    logger.info(msg)
                except subprocess.CalledProcessError as exc:
                    err = f"Failed to create virtual environment: {exc}"
                    logger.critical(err)
            else:
                err = f"Cannot find virtual environment: {self.venv}."
                logger.critical(err)
        msg = f"Virtual environment: {self.venv}"
        logger.debug(msg)
        venv_interpreter = self.venv / "bin" / "python"
        if not venv_interpreter.exists():
            err = f"Cannot find interpreter: {venv_interpreter}."
            logger.critical(err)

        msg = f"Virtual environment interpreter: {venv_interpreter}"
        logger.debug(msg)
        self.venv_interpreter = venv_interpreter

    def _set_site_pkg_path(self: Config) -> None:
        """USe the interpreter to find the site packages path."""
        command = (
            f"{self.venv_interpreter} -c"
            " 'import json,site; print(json.dumps(site.getsitepackages()))'"
        )
        work = "Locating site packages directory"
        try:
            proc = subprocess_run(
                command=command,
                verbose=self.args.verbose,
                msg=work,
                term_features=self.term_features,
            )
        except subprocess.CalledProcessError as exc:
            err = f"Failed to find site packages path: {exc}"
            logger.critical(err)

        try:
            site_pkg_dirs = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            err = f"Failed to decode json: {exc}"
            logger.critical(err)

        if not site_pkg_dirs:
            err = "Failed to find site packages path."
            logger.critical(err)

        msg = f"Found site packages path: {site_pkg_dirs[0]}"
        logger.debug(msg)

        self.site_pkg_path = Path(site_pkg_dirs[0])
