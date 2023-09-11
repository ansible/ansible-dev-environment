"""Constants, for now, for pip4a."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys

from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from .utils import parse_collection_request, subprocess_run


if TYPE_CHECKING:
    from argparse import Namespace

    from .utils import CollectionSpec

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
        self.python_path: Path
        self.site_pkg_path: Path
        self.venv_interpreter: Path
        self.collection: CollectionSpec

    def init(self: Config, create_venv: bool = False) -> None:  # noqa: FBT001, FBT002
        """Initialize the configuration.

        Args:
            create_venv: Create a virtual environment. Defaults to False.
        """
        if self.args.subcommand == "install" and not self.args.requirement:
            self.collection = parse_collection_request(self.args.collection_specifier)
            if self.collection.path:
                self._get_galaxy()
        elif self.args.subcommand == "uninstall" and not self.args.requirement:
            self.collection = parse_collection_request(self.args.collection_specifier)
            if self.collection.path:
                err = "Please use a collection name for uninstallation."
                logger.critical(err)

        self._create_venv = create_venv
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
    def collection_cache_dir(self: Config) -> Path:
        """Return the collection cache directory."""
        collection_cache_dir = self.venv_cache_dir / self.collection.name
        if not collection_cache_dir.exists():
            collection_cache_dir.mkdir()
        return collection_cache_dir

    @property
    def collection_build_dir(self: Config) -> Path:
        """Return the collection cache directory."""
        collection_build_dir = self.collection_cache_dir / "build"
        if not collection_build_dir.exists():
            collection_build_dir.mkdir()
        return collection_build_dir

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
    def site_pkg_collection_path(self: Config) -> Path:
        """Return the site packages collection path."""
        if not self.collection.cnamespace or not self.collection.cname:
            msg = "Collection namespace or name not set."
            raise RuntimeError(msg)
        return (
            self.site_pkg_collections_path
            / self.collection.cnamespace
            / self.collection.cname
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
        if self.collection is None or self.collection.path is None:
            msg = "_get_galaxy called without a collection or path"
            raise RuntimeError(msg)
        file_name = self.collection.path / "galaxy.yml"
        if not file_name.exists():
            err = f"Failed to find {file_name} in {self.collection.path}"
            logger.critical(err)

        with file_name.open(encoding="utf-8") as fileh:
            try:
                yaml_file = yaml.safe_load(fileh)
            except yaml.YAMLError as exc:
                err = f"Failed to load yaml file: {exc}"
                logger.critical(err)

        try:
            self.collection.cnamespace = yaml_file["namespace"]
            self.collection.cname = yaml_file["name"]
            msg = f"Found collection name: {self.collection.name} from {file_name}."
            logger.debug(msg)
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
                logger.debug(msg)
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
