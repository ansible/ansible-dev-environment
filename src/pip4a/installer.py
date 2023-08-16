"""The installer."""

from __future__ import annotations

import logging
import os
import shutil
import site
import subprocess
import sys

from pathlib import Path
from typing import TYPE_CHECKING

from .constants import Constants as C  # noqa: N817


if TYPE_CHECKING:
    from .app import App


logger = logging.getLogger(__name__)


class Installer:
    """The installer class."""

    def __init__(self: Installer, app: App) -> None:
        """Initialize the installer.

        Arguments:
            app: The app instance
        """
        self.app: App = app

    def run(self: Installer) -> None:
        """Run the installer."""
        if self.app.args.collection_specifier.startswith("."):
            self._pip_install(C.REQUIREMENTS_PY)
            if "[test]" in self.app.args.collection_specifier:
                self._pip_install(C.TEST_REQUIREMENTS_PY)
            site_pkg_path = self._install_collection()
            if self.app.args.editable:
                self._swap_editable_collection(site_pkg_path)
            self._check_bindep()
            return
        err = "Only local collections are supported at this time. ('.' or .[test])]"
        logger.critical(err)

    def _init_build_dir(self: Installer) -> None:
        """Initialize the build directory."""
        msg = f"Initializing build directory: {C.COLLECTION_BUILD_DIR}"
        logger.info(msg)
        if C.COLLECTION_BUILD_DIR.exists():
            shutil.rmtree(C.COLLECTION_BUILD_DIR)
        C.COLLECTION_BUILD_DIR.mkdir()

    def _install_collection(self: Installer) -> Path:
        """Install the collection from the current working directory."""
        self._init_build_dir()

        command = (
            f"ansible-galaxy collection build --output-path {C.COLLECTION_BUILD_DIR}"
        )

        msg = "Running ansible-galaxy to build collection."
        logger.info(msg)
        msg = f"Running command: {command}"
        logger.debug(msg)

        try:
            subprocess.run(
                command,
                check=True,
                capture_output=not self.app.args.verbose,
                shell=True,  # noqa: S602
            )
        except subprocess.CalledProcessError as exc:
            err = f"Failed to build collection: {exc} {exc.stderr}"
            logger.critical(err)

        built = [f for f in Path(C.COLLECTION_BUILD_DIR).iterdir() if f.is_file()]
        if len(built) != 1:
            err = (
                "Expected to find one collection tarball in"
                f"{C.COLLECTION_BUILD_DIR}, found {len(built)}"
            )
            raise RuntimeError(err)
        tarball = built[0]
        site_pkg_dirs = site.getsitepackages()

        first_site_pkg_path = Path(site_pkg_dirs[0])
        command = (
            f"ansible-galaxy collection install {tarball} -p {first_site_pkg_path}"
        )
        env = os.environ
        if not self.app.args.verbose:
            env["ANSIBLE_GALAXY_COLLECTIONS_PATH_WARNING"] = "false"
        msg = "Running ansible-galaxy to install collection and it's dependencies."
        logger.info(msg)
        msg = f"Running command: {command}"
        logger.debug(msg)
        try:
            subprocess.run(
                command,
                check=True,
                capture_output=not self.app.args.verbose,
                env=env,
                shell=True,  # noqa: S602
            )
        except subprocess.CalledProcessError as exc:
            err = f"Failed to install collection: {exc} {exc.stderr}"
            logger.critical(err)

        return first_site_pkg_path

    def _swap_editable_collection(self: Installer, site_pkg_path: Path) -> None:
        """Swap the installed collection with the current working directory.

        Args:
            site_pkg_path: The first site package path
        """
        site_pkg_collection_path = (
            site_pkg_path
            / "ansible_collections"
            / self.app.collection_name.split(".")[0]
            / self.app.collection_name.split(".")[1]
        )

        msg = f"Removing installed {site_pkg_collection_path}"
        logger.info(msg)
        if site_pkg_collection_path.exists():
            if site_pkg_collection_path.is_symlink():
                site_pkg_collection_path.unlink()
            else:
                shutil.rmtree(site_pkg_collection_path)

        cwd = Path.cwd()
        msg = f"Symlinking {site_pkg_collection_path} to {cwd}"
        logger.info(msg)
        site_pkg_collection_path.symlink_to(cwd)

    def _pip_install(self: Installer, requirements_file: Path) -> None:
        """Install the dependencies."""
        if not requirements_file.exists():
            msg = f"Requirements file {requirements_file} does not exist, skipping"
            logger.info(msg)
            return

        if requirements_file.stat().st_size == 0:
            msg = f"Requirements file {requirements_file} is empty, skipping"
            logger.info(msg)
            return

        command = f"{sys.executable} -m pip install -r {requirements_file}"

        msg = f"Installing python requirements from {requirements_file}"
        logger.info(msg)
        msg = f"Running command: {command}"
        logger.debug(msg)
        try:
            subprocess.run(
                command,
                check=True,
                capture_output=not self.app.args.verbose,
                shell=True,  # noqa: S602
            )
        except subprocess.CalledProcessError as exc:
            err = f"Failed to install requirements from {requirements_file}: {exc}"
            raise RuntimeError(err) from exc

    def _check_bindep(self: Installer) -> None:
        """Check the bindep file."""
        bindep = Path("./bindep.txt").resolve()
        if not bindep.exists():
            msg = f"System package requirements file {bindep} does not exist, skipping"
            logger.info(msg)
            return
        msg = f"bindep file found: {bindep}"
        logger.debug(msg)

        bindep_found = bool(shutil.which("bindep"))
        if not bindep_found:
            msg = "Installing bindep for: {bindep}"
            logger.debug(msg)
            command = f"{sys.executable} -m pip install bindep"
            try:
                subprocess.run(
                    command,
                    check=True,
                    capture_output=not self.app.args.verbose,
                    shell=True,  # noqa: S602
                )
            except subprocess.CalledProcessError as exc:
                err = f"Failed to install bindep: {exc}"
                logger.critical(err)

        command = f"bindep -b -f {bindep}"
        msg = f"Running command: {command}"
        logger.debug(msg)
        proc = subprocess.run(
            command,
            check=False,
            capture_output=True,
            shell=True,  # noqa: S602
            text=True,
        )
        if proc.returncode == 0:
            return

        lines = proc.stdout.splitlines()
        msg = (
            "Required system packages are missing."
            " Please use the system package manager to install them."
        )
        logger.warning(msg)
        for line in lines:
            msg = f"Missing: {line}"
            logger.warning(msg)
