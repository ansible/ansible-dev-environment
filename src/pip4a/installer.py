"""The installer."""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess

from pathlib import Path
from typing import TYPE_CHECKING

from .utils import opt_deps_to_files, oxford_join, subprocess_run


if TYPE_CHECKING:
    from .config import Config


logger = logging.getLogger(__name__)


class Installer:
    """The installer class."""

    def __init__(self: Installer, config: Config) -> None:
        """Initialize the installer.

        Args:
            config: The application configuration.
        """
        self._config = config

    def run(self: Installer) -> None:
        """Run the installer."""
        self._install_core()
        self._install_collection()
        if self._config.args.editable:
            self._swap_editable_collection()

        self._discover_deps()
        self._pip_install()
        self._check_bindep()

        if self._config.args.venv and (
            self._config.interpreter != self._config.venv_interpreter
        ):
            msg = "A virtual environment was specified but has not been activated."
            logger.warning(msg)
            msg = (
                "Please activate the virtual environment:"
                f"\nsource {self._config.args.venv}/bin/activate"
            )
            logger.warning(msg)

    def _init_build_dir(self: Installer) -> None:
        """Initialize the build directory."""
        msg = f"Initializing build directory: {self._config.collection_build_dir}"
        logger.info(msg)
        if self._config.collection_build_dir.exists():
            shutil.rmtree(self._config.collection_build_dir)
        self._config.collection_build_dir.mkdir(parents=True)

    def _install_core(self: Installer) -> None:
        """Install ansible-core if not installed already."""
        core = self._config.venv_bindir / "ansible"
        if core.exists():
            return
        msg = "Installing ansible-core."
        logger.info(msg)
        command = f"{self._config.venv_interpreter} -m pip install ansible-core"
        try:
            subprocess_run(command=command, verbose=self._config.args.verbose)
        except subprocess.CalledProcessError as exc:
            err = f"Failed to install ansible-core: {exc}"
            logger.critical(err)

    def _discover_deps(self: Installer) -> None:
        """Discover the dependencies."""
        command = (
            f"ansible-builder introspect {self._config.site_pkg_path}"
            f" --write-pip {self._config.discovered_python_reqs}"
            f" --write-bindep {self._config.discovered_bindep_reqs}"
            " --sanitize"
        )
        opt_deps = re.match(r".*\[(.*)\]", self._config.args.collection_specifier)
        if opt_deps:
            dep_paths = opt_deps_to_files(
                collection_path=self._config.collection_path,
                dep_str=opt_deps.group(1),
            )
            for dep_path in dep_paths:
                command += f" --user-pip {dep_path}"
        msg = f"Writing discovered python requirements to: {self._config.discovered_python_reqs}"
        logger.info(msg)
        msg = f"Writing discovered system requirements to: {self._config.discovered_bindep_reqs}"
        logger.info(msg)
        try:
            subprocess_run(command=command, verbose=self._config.args.verbose)
        except subprocess.CalledProcessError as exc:
            err = f"Failed to discover requirements: {exc} {exc.stderr}"
            logger.critical(err)

    def _install_collection(self: Installer) -> None:
        """Install the collection from the build directory."""
        self._init_build_dir()

        command = (
            "cp -r --parents $(git ls-files 2> /dev/null || ls)"
            f" {self._config.collection_build_dir}"
        )
        msg = "Copying collection to build directory using git ls-files."
        logger.info(msg)
        try:
            subprocess_run(
                command=command,
                cwd=self._config.collection_path,
                verbose=self._config.args.verbose,
            )
        except subprocess.CalledProcessError as exc:
            err = f"Failed to copy collection to build directory: {exc} {exc.stderr}"
            logger.critical(err)

        command = (
            f"cd {self._config.collection_build_dir} &&"
            f" {self._config.venv_bindir / 'ansible-galaxy'} collection build"
            f" --output-path {self._config.collection_build_dir}"
            " --force"
        )

        msg = "Running ansible-galaxy to build collection."
        logger.info(msg)

        try:
            subprocess_run(command=command, verbose=self._config.args.verbose)
        except subprocess.CalledProcessError as exc:
            err = f"Failed to build collection: {exc} {exc.stderr}"
            logger.critical(err)

        built = [
            f
            for f in Path(self._config.collection_build_dir).iterdir()
            if f.is_file() and f.name.endswith(".tar.gz")
        ]
        if len(built) != 1:
            err = (
                "Expected to find one collection tarball in"
                f"{self._config.collection_build_dir}, found {len(built)}"
            )
            raise RuntimeError(err)
        tarball = built[0]

        if self._config.site_pkg_collection_path.exists():
            msg = f"Removing installed {self._config.site_pkg_collection_path}"
            logger.debug(msg)
            if self._config.site_pkg_collection_path.is_symlink():
                self._config.site_pkg_collection_path.unlink()
            else:
                shutil.rmtree(self._config.site_pkg_collection_path)

        command = (
            f"{self._config.venv_bindir / 'ansible-galaxy'} collection"
            f" install {tarball} -p {self._config.site_pkg_path}"
            " --force"
        )
        env = os.environ
        if not self._config.args.verbose:
            env["ANSIBLE_GALAXY_COLLECTIONS_PATH_WARNING"] = "false"
        msg = "Running ansible-galaxy to install collection and it's dependencies."
        logger.info(msg)
        try:
            proc = subprocess_run(command=command, verbose=self._config.args.verbose)
        except subprocess.CalledProcessError as exc:
            err = f"Failed to install collection: {exc} {exc.stderr}"
            logger.critical(err)
            return
        installed = re.findall(r"(\w+\.\w+):.*installed", proc.stdout)
        msg = f"Installed collections: {oxford_join(installed)}"
        logger.info(msg)
        with self._config.installed_collections.open(mode="w") as f:
            f.write("\n".join(installed))

    def _swap_editable_collection(self: Installer) -> None:
        """Swap the installed collection with the current working directory."""
        msg = f"Removing installed {self._config.site_pkg_collection_path}"
        logger.info(msg)
        if self._config.site_pkg_collection_path.exists():
            if self._config.site_pkg_collection_path.is_symlink():
                self._config.site_pkg_collection_path.unlink()
            else:
                shutil.rmtree(self._config.site_pkg_collection_path)

        cwd = Path.cwd()
        msg = f"Symlinking {self._config.site_pkg_collection_path} to {cwd}"
        logger.info(msg)
        self._config.site_pkg_collection_path.symlink_to(cwd)

    def _pip_install(self: Installer) -> None:
        """Install the dependencies."""
        command = (
            f"{self._config.venv_interpreter} -m pip install"
            f" -r {self._config.discovered_python_reqs}"
        )

        msg = (
            f"Installing python requirements from {self._config.discovered_python_reqs}"
        )
        logger.info(msg)
        try:
            subprocess_run(command=command, verbose=self._config.args.verbose)
        except subprocess.CalledProcessError as exc:
            err = (
                "Failed to install requirements from"
                f" {self._config.discovered_python_reqs}: {exc}"
            )
            raise RuntimeError(err) from exc

    def _check_bindep(self: Installer) -> None:
        """Check the bindep file."""
        command = f"bindep -b -f {self._config.discovered_bindep_reqs}"
        try:
            subprocess_run(command=command, verbose=self._config.args.verbose)
        except subprocess.CalledProcessError as exc:
            lines = exc.stdout.splitlines()
            msg = (
                "Required system packages are missing."
                " Please use the system package manager to install them."
            )
            logger.warning(msg)
            for line in lines:
                msg = f"Missing: {line}"
                logger.warning(msg)
                pass
        else:
            msg = "All required system packages are installed."
            logger.debug(msg)
            return
