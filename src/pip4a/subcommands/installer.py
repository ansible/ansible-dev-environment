"""The installer."""

from __future__ import annotations

import re
import shutil
import subprocess

from pathlib import Path
from typing import TYPE_CHECKING

from pip4a.collection import Collection, parse_collection_request
from pip4a.utils import (
    builder_introspect,
    collections_from_requirements,
    oxford_join,
    subprocess_run,
)

from .checker import Checker


if TYPE_CHECKING:
    from pip4a.config import Config
    from pip4a.output import Output


class Installer:
    """The installer class."""

    def __init__(self: Installer, config: Config, output: Output) -> None:
        """Initialize the installer.

        Args:
            config: The application configuration.
            output: The application output object.
        """
        self._config = config
        self._collection: Collection
        self._output = output

    def run(self: Installer) -> None:
        """Run the installer."""
        if (
            self._config.args.collection_specifier
            and "," in self._config.args.collection_specifier
        ):
            err = "Multiple optional dependencies are not supported at this time."
            self._output.critical(err)

        self._install_core()

        if self._config.args.requirement:
            self._install_galaxy_requirements()
        elif self._config.args.collection_specifier:
            self._collection = parse_collection_request(
                string=self._config.args.collection_specifier,
                config=self._config,
                output=self._output,
            )
            if self._collection.local:
                self._install_local_collection()
                if self._config.args.editable:
                    self._swap_editable_collection()
            elif not self._collection.local:
                if self._config.args.editable:
                    msg = "Editable installs are only supported for local collections."
                    self._output.critical(msg)
                self._install_galaxy_collection()

        builder_introspect(config=self._config)
        self._pip_install()
        Checker(config=self._config, output=self._output).system_deps()

        if self._config.args.venv and (
            self._config.interpreter != self._config.venv_interpreter
        ):
            msg = "A virtual environment was specified but has not been activated."
            self._output.note(msg)
            msg = (
                "Please activate the virtual environment:"
                f"\nsource {self._config.args.venv}/bin/activate"
            )
            self._output.note(msg)

    def _install_core(self: Installer) -> None:
        """Install ansible-core if not installed already."""
        msg = "Installing ansible-core."
        self._output.info(msg)

        core = self._config.venv_bindir / "ansible"
        if core.exists():
            return
        msg = "Installing ansible-core."
        self._output.debug(msg)
        command = f"{self._config.venv_interpreter} -m pip install ansible-core"
        try:
            subprocess_run(
                command=command,
                verbose=self._config.args.verbose,
                msg=msg,
                term_features=self._config.term_features,
            )
        except subprocess.CalledProcessError as exc:
            err = f"Failed to install ansible-core: {exc}"
            self._output.critical(err)

    def _install_galaxy_collection(self: Installer) -> None:
        """Install the collection from galaxy."""
        msg = f"Installing collection from galaxy: {self._config.args.collection_specifier}"
        self._output.info(msg)

        if self._collection.site_pkg_path.exists():
            msg = f"Removing installed {self._collection.site_pkg_path}"
            self._output.debug(msg)
            if self._collection.site_pkg_path.is_symlink():
                self._collection.site_pkg_path.unlink()
            else:
                shutil.rmtree(self._collection.site_pkg_path)

        command = (
            f"{self._config.venv_bindir / 'ansible-galaxy'} collection"
            f" install '{self._config.args.collection_specifier}'"
            f" -p {self._config.site_pkg_path}"
            " --force"
        )
        env = {
            "ANSIBLE_GALAXY_COLLECTIONS_PATH_WARNING": str(self._config.args.verbose),
        }
        msg = "Running ansible-galaxy to install non-local collection and it's dependencies."
        self._output.debug(msg)
        try:
            proc = subprocess_run(
                command=command,
                env=env,
                verbose=self._config.args.verbose,
                msg=msg,
                term_features=self._config.term_features,
            )
        except subprocess.CalledProcessError as exc:
            err = f"Failed to install collection: {exc}\n{exc.stderr}"
            self._output.critical(err)
            return
        installed = re.findall(r"(\w+\.\w+):.*installed", proc.stdout)
        msg = f"Installed collections include: {oxford_join(installed)}"
        self._output.note(msg)

    def _install_galaxy_requirements(self: Installer) -> None:
        """Install the collections using requirements.yml."""
        msg = f"Installing collections from requirements file: {self._config.args.requirement}"
        self._output.info(msg)

        collections = collections_from_requirements(file=self._config.args.requirement)
        for collection in collections:
            cnamespace = collection["name"].split(".")[0]
            cname = collection["name"].split(".")[1]
            cpath = self._config.site_pkg_collections_path / cnamespace / cname
            if cpath.exists():
                msg = f"Removing installed {cpath}"
                self._output.debug(msg)
                if cpath.is_symlink():
                    cpath.unlink()
                else:
                    shutil.rmtree(cpath)

        command = (
            f"{self._config.venv_bindir / 'ansible-galaxy'} collection"
            f" install -r {self._config.args.requirement}"
            f" -p {self._config.site_pkg_path}"
            " --force"
        )
        work = "Install collections from requirements file"
        try:
            proc = subprocess_run(
                command=command,
                verbose=self._config.args.verbose,
                msg=work,
                term_features=self._config.term_features,
            )
        except subprocess.CalledProcessError as exc:
            err = f"Failed to install collections: {exc} {exc.stderr}"
            self._output.critical(err)

        installed = re.findall(r"(\w+\.\w+):.*installed", proc.stdout)
        msg = f"Installed collections include: {oxford_join(installed)}"
        self._output.note(msg)

    def _install_local_collection(self: Installer) -> None:  # noqa: PLR0912, PLR0915
        """Install the collection from the build directory.

        Raises:
            RuntimeError: If tarball is not found or if more than one tarball is found.
        """
        msg = f"Installing local collection from: {self._collection.build_dir}"
        self._output.info(msg)

        command = (
            "cp -r --parents $(git ls-files 2> /dev/null || ls)"
            f" {self._collection.build_dir}"
        )
        msg = "Copying collection to build directory using git ls-files."
        self._output.debug(msg)
        try:
            subprocess_run(
                command=command,
                cwd=self._collection.path,
                verbose=self._config.args.verbose,
                msg=msg,
                term_features=self._config.term_features,
            )
        except subprocess.CalledProcessError as exc:
            err = f"Failed to copy collection to build directory: {exc} {exc.stderr}"
            self._output.critical(err)

        command = (
            f"cd {self._collection.build_dir} &&"
            f" {self._config.venv_bindir / 'ansible-galaxy'} collection build"
            f" --output-path {self._collection.build_dir}"
            " --force"
        )

        msg = "Running ansible-galaxy to build collection."
        self._output.debug(msg)

        try:
            subprocess_run(
                command=command,
                verbose=self._config.args.verbose,
                msg=msg,
                term_features=self._config.term_features,
            )
        except subprocess.CalledProcessError as exc:
            err = f"Failed to build collection: {exc} {exc.stderr}"
            self._output.critical(err)

        built = [
            f
            for f in Path(self._collection.build_dir).iterdir()
            if f.is_file() and f.name.endswith(".tar.gz")
        ]
        if len(built) != 1:
            err = (
                "Expected to find one collection tarball in"
                f"{self._collection.build_dir}, found {len(built)}"
            )
            raise RuntimeError(err)
        tarball = built[0]

        if self._collection.site_pkg_path.exists():
            msg = f"Removing installed {self._collection.site_pkg_path}"
            self._output.debug(msg)
            if self._collection.site_pkg_path.is_symlink():
                self._collection.site_pkg_path.unlink()
            else:
                shutil.rmtree(self._collection.site_pkg_path)

        info_dirs = [
            entry
            for entry in self._config.site_pkg_collections_path.iterdir()
            if entry.is_dir()
            and entry.name.endswith(".info")
            and entry.name.startswith(self._collection.name)
        ]
        for info_dir in info_dirs:
            msg = f"Removing installed {info_dir}"
            self._output.debug(msg)
            shutil.rmtree(info_dir)

        command = (
            f"{self._config.venv_bindir / 'ansible-galaxy'} collection"
            f" install {tarball} -p {self._config.site_pkg_path}"
            " --force"
        )
        env = {
            "ANSIBLE_GALAXY_COLLECTIONS_PATH_WARNING": str(self._config.args.verbose),
        }
        msg = "Running ansible-galaxy to install a local collection and it's dependencies."
        self._output.debug(msg)
        try:
            proc = subprocess_run(
                command=command,
                env=env,
                verbose=self._config.args.verbose,
                msg=msg,
                term_features=self._config.term_features,
            )
        except subprocess.CalledProcessError as exc:
            err = f"Failed to install collection: {exc} {exc.stderr}"
            self._output.critical(err)
            return

        # ansible-galaxy collection install does not include the galaxy.yml for version
        # nor does it create an info file that can be used to determine the version.
        # preserve the MANIFEST.json file for editable installs
        if not self._config.args.editable:
            shutil.copy(
                self._collection.build_dir / "galaxy.yml",
                self._collection.site_pkg_path / "galaxy.yml",
            )
        else:
            shutil.copy(
                self._collection.site_pkg_path / "MANIFEST.json",
                self._collection.cache_dir / "MANIFEST.json",
            )

        installed = re.findall(r"(\w+\.\w+):.*installed", proc.stdout)
        msg = f"Installed collections include: {oxford_join(installed)}"
        self._output.note(msg)

    def _swap_editable_collection(self: Installer) -> None:
        """Swap the installed collection with the current working directory.

        Raises:
            RuntimeError: If the collection path is not set.
        """
        msg = f"Swapping {self._collection.name} with {self._collection.path}"
        self._output.info(msg)

        if self._collection.path is None:
            msg = "Collection path not set"
            raise RuntimeError(msg)
        msg = f"Removing installed {self._collection.site_pkg_path}"
        self._output.debug(msg)
        if self._collection.site_pkg_path.exists():
            if self._collection.site_pkg_path.is_symlink():
                self._collection.site_pkg_path.unlink()
            else:
                shutil.rmtree(self._collection.site_pkg_path)

        msg = f"Symlinking {self._collection.site_pkg_path} to {self._collection.path}"
        self._output.debug(msg)
        self._collection.site_pkg_path.symlink_to(self._collection.path)

    def _pip_install(self: Installer) -> None:
        """Install the dependencies."""
        msg = "Installing python requirements."
        self._output.info(msg)

        command = (
            f"{self._config.venv_interpreter} -m pip install"
            f" -r {self._config.discovered_python_reqs}"
        )

        msg = (
            f"Installing python requirements from {self._config.discovered_python_reqs}"
        )
        self._output.debug(msg)
        work = "Installing python requirements"
        try:
            subprocess_run(
                command=command,
                verbose=self._config.args.verbose,
                msg=work,
                term_features=self._config.term_features,
            )
        except subprocess.CalledProcessError as exc:
            err = (
                "Failed to install requirements from"
                f" {self._config.discovered_python_reqs}: {exc} {exc.stderr}"
            )
            self._output.critical(err)
        else:
            msg = "All python requirements are installed."
            self._output.note(msg)
