"""Constants, for now, for pip4a."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
import sys

from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from .utils import subprocess_run


if TYPE_CHECKING:
    from argparse import Namespace

logger = logging.getLogger(__name__)


class Config:
    """The application configuration."""

    # pylint: disable=too-many-instance-attributes
    def __init__(
        self: Config,
        args: Namespace,
    ) -> None:
        """Initialize the configuration."""
        self._create_venv: bool
        self.args: Namespace = args
        self.bindir: Path
        self.c_name: str
        self.c_namespace: str
        self.python_path: Path
        self.site_pkg_path: Path
        self.venv_interpreter: Path

    def init(self: Config, create_venv: bool = False) -> None:  # noqa: FBT001, FBT002
        """Initialize the configuration.

        Args:
            create_venv: Create a virtual environment. Defaults to False.
        """
        if self.args.subcommand == "install":
            self._get_galaxy()
        elif self.args.subcommand == "uninstall":
            parts = self.args.collection_specifier.split(".")
            fqcn_parts = 2
            if len(parts) != fqcn_parts:
                err = (
                    "The collection specifier must be in the form of"
                    " 'namespace.collection'"
                )
                logger.critical(err)
            self.c_namespace = parts[0]
            self.c_name = parts[1]
        self._create_venv = create_venv
        self._set_interpreter()
        self._set_site_pkg_path()

    @property
    def collection_path(self: Config) -> Path:
        """Set the collection root directory."""
        spec = self.args.collection_specifier.split("[")[0]
        specp = Path(spec).expanduser().resolve()
        if specp.is_dir():
            return specp
        err = f"Cannot find collection root directory. {specp}"
        logger.critical(err)
        sys.exit(1)

    @property
    def collection_name(self: Config) -> str:
        """Return the collection name."""
        return f"{self.c_namespace}.{self.c_name}"

    @property
    def cache_dir(self: Config) -> Path:
        """Return the cache directory."""
        cache_home = os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")
        return (Path(cache_home) / "pip4a").resolve()

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
    def vuuid(self: Config) -> str:
        """Return the virtual environment uuid."""
        result = hashlib.md5(str(self.venv).encode())  # noqa: S324
        return result.hexdigest()

    @property
    def venv_cache_dir(self: Config) -> Path:
        """Return the virtual environment cache directory."""
        return self.cache_dir / self.vuuid

    @property
    def collection_cache_dir(self: Config) -> Path:
        """Return the collection cache directory."""
        return self.venv_cache_dir / self.collection_name

    @property
    def collection_build_dir(self: Config) -> Path:
        """Return the collection cache directory."""
        return self.collection_cache_dir / "build"

    @property
    def discovered_python_reqs(self: Config) -> Path:
        """Return the discovered python requirements file."""
        return self.collection_cache_dir / "discovered_requirements.txt"

    @property
    def discovered_bindep_reqs(self: Config) -> Path:
        """Return the discovered system package requirements file."""
        return self.collection_cache_dir / "discovered_bindep.txt"

    @property
    def installed_collections(self: Config) -> Path:
        """Return the installed collections file."""
        return self.collection_cache_dir / "installed_collections.txt"

    @property
    def site_pkg_collections_path(self: Config) -> Path:
        """Return the site packages collection path."""
        return (
            self.site_pkg_path / "ansible_collections"
        )

    @property
    def site_pkg_collection_path(self: Config) -> Path:
        """Return the site packages collection path."""
        return (
            self.site_pkg_collections_path / self.c_namespace / self.c_name
        )

    @property
    def venv_bindir(self: Config) -> Path:
        """Return the virtual environment bin directory."""
        return self.venv / "bin"

    @property
    def interpreter(self: Config) -> Path:
        """Return the current interpreter."""
        return Path(sys.executable)

    def _get_galaxy(self: Config) -> None:
        """Retrieve the collection name from the galaxy.yml file.

        Returns:
            str: The collection name and dependencies

        Raises:
            SystemExit: If the collection name is not found
        """
        file_name = self.collection_path / "galaxy.yml"
        if not file_name.exists():
            err = f"Failed to find {file_name} in {self.collection_path}"
            logger.critical(err)

        with file_name.open(encoding="utf-8") as fileh:
            try:
                yaml_file = yaml.safe_load(fileh)
            except yaml.YAMLError as exc:
                err = f"Failed to load yaml file: {exc}"
                logger.critical(err)

        try:
            self.c_namespace = yaml_file["namespace"]
            self.c_name = yaml_file["name"]
            msg = f"Found collection name: {self.collection_name} from {file_name}."
            logger.info(msg)
        except KeyError as exc:
            err = f"Failed to find collection name in {file_name}: {exc}"
            logger.critical(err)
        else:
            return
        raise SystemExit(1)  # We shouldn't be here

    def _set_interpreter(
        self: Config,
    ) -> None:
        """Set the interpreter."""
        if not self.venv.exists():
            if self._create_venv:
                msg = f"Creating virtual environment: {self.venv}"
                logger.info(msg)
                command = f"python -m venv {self.venv}"
                try:
                    subprocess_run(command=command, verbose=self.args.verbose)
                except subprocess.CalledProcessError as exc:
                    err = f"Failed to create virtual environment: {exc}"
                    logger.critical(err)
            else:
                err = f"Cannot find virtual environment: {self.venv}."
                logger.critical(err)
        msg = f"Virtual environment: {self.venv}"
        logger.info(msg)
        venv_interpreter = self.venv / "bin" / "python"
        if not venv_interpreter.exists():
            err = f"Cannot find interpreter: {venv_interpreter}."
            logger.critical(err)

        msg = f"Virtual environment interpreter: {venv_interpreter}"
        logger.info(msg)
        self.venv_interpreter = venv_interpreter

    def _set_site_pkg_path(self: Config) -> None:
        """USe the interpreter to find the site packages path."""
        command = (
            f"{self.venv_interpreter} -c"
            " 'import json,site; print(json.dumps(site.getsitepackages()))'"
        )
        try:
            proc = subprocess_run(command=command, verbose=self.args.verbose)
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
