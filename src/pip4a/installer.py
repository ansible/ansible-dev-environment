"""The installer."""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess

from pathlib import Path

from .base import Base
from .constants import Constants as C  # noqa: N817
from .utils import opt_deps_to_files, oxford_join, subprocess_run


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

        self._install_core()
        self._install_collection()
        if self.app.args.editable:
            self._swap_editable_collection()

        self._discover_deps()
        self._pip_install()
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
        C.COLLECTION_BUILD_DIR.mkdir(parents=True)

    def _install_core(self: Installer) -> None:
        """Install ansible-core if not installed already."""
        core = self.bindir / "ansible"
        if core.exists():
            return
        msg = "Installing ansible-core."
        logger.info(msg)
        command = f"{self.interpreter} -m pip install ansible-core"
        try:
            subprocess_run(command=command, verbose=self.app.args.verbose)
        except subprocess.CalledProcessError as exc:
            err = f"Failed to install ansible-core: {exc}"
            logger.critical(err)

    def _discover_deps(self: Installer) -> None:
        """Discover the dependencies."""
        command = (
            f"ansible-builder introspect {self.site_pkg_path}"
            f" --write-pip {C.DISCOVERED_PYTHON_REQS}"
            f" --write-bindep {C.DISCOVERED_BINDEP_REQS}"
            " --sanitize"
        )
        opt_deps = re.match(r".*\[(.*)\]", self.app.args.collection_specifier)
        if opt_deps:
            for dep in opt_deps_to_files(opt_deps.group(1)):
                command += f" --user-pip {dep}"
        msg = f"Writing discovered python requirements to: {C.DISCOVERED_PYTHON_REQS}"
        logger.info(msg)
        msg = f"Writing discovered system package requirements to: {C.DISCOVERED_BINDEP_REQS}"
        logger.info(msg)
        try:
            subprocess_run(command=command, verbose=self.app.args.verbose)
        except subprocess.CalledProcessError as exc:
            err = f"Failed to discover requirements: {exc}"
            logger.critical(err)

    def _install_collection(self: Installer) -> None:
        """Install the collection from the build directory."""
        self._init_build_dir()

        command = f"cp -r --parents $(git ls-files 2> /dev/null || ls) {C.COLLECTION_BUILD_DIR}"
        msg = "Copying collection to build directory using git ls-files."
        logger.info(msg)
        try:
            subprocess_run(command=command, verbose=self.app.args.verbose)
        except subprocess.CalledProcessError as exc:
            err = f"Failed to copy collection to build directory: {exc}"
            logger.critical(err)

        command = (
            f"cd {C.COLLECTION_BUILD_DIR} &&"
            f" {self.bindir / 'ansible-galaxy'} collection build"
            f" --output-path {C.COLLECTION_BUILD_DIR}"
            " --force"
        )

        msg = "Running ansible-galaxy to build collection."
        logger.info(msg)

        try:
            subprocess_run(command=command, verbose=self.app.args.verbose)
        except subprocess.CalledProcessError as exc:
            err = f"Failed to build collection: {exc} {exc.stderr}"
            logger.critical(err)

        built = [
            f
            for f in Path(C.COLLECTION_BUILD_DIR).iterdir()
            if f.is_file() and f.name.endswith(".tar.gz")
        ]
        if len(built) != 1:
            err = (
                "Expected to find one collection tarball in"
                f"{C.COLLECTION_BUILD_DIR}, found {len(built)}"
            )
            raise RuntimeError(err)
        tarball = built[0]

        # Remove installed collection if it exists
        site_pkg_collection_path = (
            self.site_pkg_path
            / "ansible_collections"
            / self.app.collection_name.split(".")[0]
            / self.app.collection_name.split(".")[1]
        )
        if site_pkg_collection_path.exists():
            msg = f"Removing installed {site_pkg_collection_path}"
            logger.debug(msg)
            if site_pkg_collection_path.is_symlink():
                site_pkg_collection_path.unlink()
            else:
                shutil.rmtree(site_pkg_collection_path)

        command = (
            f"{self.bindir / 'ansible-galaxy'} collection"
            f" install {tarball} -p {self.site_pkg_path}"
            " --force"
        )
        env = os.environ
        if not self.app.args.verbose:
            env["ANSIBLE_GALAXY_COLLECTIONS_PATH_WARNING"] = "false"
        msg = "Running ansible-galaxy to install collection and it's dependencies."
        logger.info(msg)
        try:
            proc = subprocess_run(command=command, verbose=self.app.args.verbose)
        except subprocess.CalledProcessError as exc:
            err = f"Failed to install collection: {exc} {exc.stderr}"
            logger.critical(err)
            return
        installed = re.findall(r"(\w+\.\w+):.*installed", proc.stdout)
        msg = f"Installed collections: {oxford_join(installed)}"
        logger.info(msg)
        with C.INSTALLED_COLLECTIONS.open(mode="w") as f:
            f.write("\n".join(installed))

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

    def _pip_install(self: Installer) -> None:
        """Install the dependencies."""
        command = f"{self.interpreter} -m pip install -r {C.DISCOVERED_PYTHON_REQS}"

        msg = f"Installing python requirements from {C.DISCOVERED_PYTHON_REQS}"
        logger.info(msg)
        try:
            subprocess_run(command=command, verbose=self.app.args.verbose)
        except subprocess.CalledProcessError as exc:
            err = (
                f"Failed to install requirements from {C.DISCOVERED_PYTHON_REQS}: {exc}"
            )
            raise RuntimeError(err) from exc

    def _check_bindep(self: Installer) -> None:
        """Check the bindep file."""
        command = f"{self.bindir / 'bindep'} -b -f {C.DISCOVERED_BINDEP_REQS}"
        try:
            subprocess_run(command=command, verbose=self.app.args.verbose)
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
