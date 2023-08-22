"""The installer."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess

from pathlib import Path

from .base import Base
from .constants import Constants as C  # noqa: N817


logger = logging.getLogger(__name__)


class Installer(Base):
    """The installer class."""

    def run(self: Installer) -> None:
        """Run the installer."""
        if not self.app.args.collection_specifier.startswith("."):
            err = "Only local collections are supported at this time. ('.' or .[test])]"
            logger.critical(err)

        self._set_interpreter(create=True)
        self._set_bindir()
        self._set_site_pkg_path()

        self._pip_install(C.REQUIREMENTS_PY)
        if "[test]" in self.app.args.collection_specifier:
            self._pip_install(C.TEST_REQUIREMENTS_PY)
        self._install_core()
        self._install_collection()
        if self.app.args.editable:
            self._swap_editable_collection()
        self._check_bindep()

        if self.app.args.venv and (self.python_path != self.interpreter):
            msg = "A virtual environment was specified but has not been activated."
            logger.warning(msg)
            msg = (
                "Please activate the virtual environment:"
                f"\nsource {self.app.args.venv}/bin/activate"
            )
            logger.warning(msg)

    def _init_build_dir(self: Installer) -> None:
        """Initialize the build directory."""
        msg = f"Initializing build directory: {C.COLLECTION_BUILD_DIR}"
        logger.info(msg)
        if C.COLLECTION_BUILD_DIR.exists():
            shutil.rmtree(C.COLLECTION_BUILD_DIR)
        C.COLLECTION_BUILD_DIR.mkdir()

    def _install_core(self: Installer) -> None:
        """Install ansible-core if not installed already."""
        core = self.bindir / "ansible"
        if core.exists():
            return
        msg = "Installing ansible-core."
        logger.info(msg)
        command = f"{self.interpreter} -m pip install ansible-core"
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
            err = f"Failed to install ansible-core: {exc}"
            logger.critical(err)

    def _install_collection(self: Installer) -> None:
        """Install the collection from the current working directory."""
        self._init_build_dir()

        command = (
            f"{self.bindir / 'ansible-galaxy'} collection build"
            f" --output-path {C.COLLECTION_BUILD_DIR}"
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
        built[0]

        command = (
            f"{self.bindir / 'ansible-galaxy'} collection"
            " install {tarball} -p {self.site_pkg_path}"
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

    def _swap_editable_collection(self: Installer) -> None:
        """Swap the installed collection with the current working directory."""
        site_pkg_collection_path = (
            self.site_pkg_path
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

        command = f"{self.interpreter} -m pip install -r {requirements_file}"

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

        try:
            subprocess.run(
                f"{self.interpreter} -m bindep",
                check=True,
                shell=True,  # noqa: S602
            )
            bindep_found = True
        except subprocess.CalledProcessError:
            bindep_found = False

        if not bindep_found:
            msg = "Installing bindep for: {bindep}"
            logger.debug(msg)
            command = f"{self.interpreter} -m pip install bindep"
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

        command = f"{self.bindir / 'bindep'} -b -f {bindep}"
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
            msg = "All required system packages are installed."
            logger.debug(msg)
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
