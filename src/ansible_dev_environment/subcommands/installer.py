"""The installer."""

from __future__ import annotations

import re
import shutil
import subprocess

from pathlib import Path
from typing import TYPE_CHECKING


try:
    from packaging import specifiers, version
except ImportError:
    specifiers = None  # type: ignore[assignment]
    version = None  # type: ignore[assignment]

from ansible_dev_environment.collection import (
    Collection,
    parse_collection_request,
)
from ansible_dev_environment.utils import (
    builder_introspect,
    collections_from_requirements,
    get_dependency_constraint,
    opt_deps_to_files,
    oxford_join,
    subprocess_run,
)

from .checker import Checker


if TYPE_CHECKING:
    from ansible_dev_environment.config import Config
    from ansible_dev_environment.output import Output


def format_process(exc: subprocess.CalledProcessError) -> str:
    """Format the subprocess exception.

    Args:
        exc: The exception.

    Returns:
        The formatted exception.
    """
    result = f"Got {exc.returncode} return code from: {exc.cmd}\n"
    if exc.stdout:  # pragma: no cover
        result += f"stdout:\n{exc.stdout}"
    if exc.stderr:
        result += f"stderr:\n{exc.stderr}"
    return result


class Installer:
    """The installer class.

    Attributes:
        RE_GALAXY_INSTALLED: The regular expression to match galaxy installed collections
    """

    RE_GALAXY_INSTALLED = re.compile(r"(\w+\.\w+):.*installed")

    def __init__(self, config: Config, output: Output) -> None:
        """Initialize the installer.

        Args:
            config: The application configuration.
            output: The application output object.
        """
        self._config = config
        self._output = output
        self._current_collection_spec: str

    def run(self) -> None:
        """Run the installer."""
        if self._config.args.collection_specifier and any(
            "," in s for s in self._config.args.collection_specifier
        ):
            err = "Multiple optional dependencies are not supported at this time."
            self._output.critical(err)

        self._install_ade_deps()

        if self._config.args.requirement or self._config.args.cpi:
            self._install_galaxy_requirements()

        opt_dep_paths = None
        if self._config.args.collection_specifier:
            collections = [
                parse_collection_request(
                    string=entry,
                    config=self._config,
                    output=self._output,
                )
                for entry in self._config.args.collection_specifier
            ]
            local_collections = [collection for collection in collections if collection.local]
            for local_collection in local_collections:
                self._install_local_collection(collection=local_collection)
                if self._config.args.editable:
                    self._swap_editable_collection(collection=local_collection)
            distant_collections = [collection for collection in collections if not collection.local]
            if distant_collections:
                if self._config.args.editable:
                    msg = "Editable installs are only supported for local collections."
                    self._output.critical(msg)
                self._install_galaxy_collections(collections=distant_collections)

            opt_dep_paths = [
                path
                for collection in collections
                for path in opt_deps_to_files(collection, self._output)
            ]
            msg = f"Optional dependencies found: {oxford_join(opt_dep_paths)}"
            self._output.info(msg)

        builder_introspect(config=self._config, opt_dep_paths=opt_dep_paths, output=self._output)
        self._pip_install()
        Checker(config=self._config, output=self._output).system_deps()

        if self._config.args.venv and (self._config.interpreter != self._config.venv_interpreter):
            msg = "A virtual environment was specified but has not been activated."
            self._output.note(msg)
            msg = (
                "Please activate the virtual environment:"
                f"\nsource {self._config.args.venv}/bin/activate"
            )
            self._output.note(msg)

    def _install_ade_deps(self) -> None:
        """Install our dependencies."""
        core_version = getattr(self._config.args, "ansible_core_version", None)

        # Warn about potential incompatibility before installation
        if core_version and self._config.args.seed:
            self._warn_if_core_version_incompatible(core_version)

        # Install dev tools first if requested
        if self._config.args.seed:
            self._install_dev_tools()

        # Then install specific core version (this will override whatever dev-tools installed)
        if core_version or not self._config.args.seed:
            self._install_core()

    def _install_core(self) -> None:
        """Install ansible-core if not installed already."""
        core = self._config.venv_bindir / "ansible"
        core_version = getattr(self._config.args, "ansible_core_version", None)

        # If no specific version requested and ansible is already installed, skip
        if core.exists() and not core_version:
            msg = "ansible-core is already installed."
            self._output.debug(msg)
            return

        msg = "Installing ansible-core."
        self._output.debug(msg)
        command = f"{self._config.venv_pip_install_cmd} ansible-core"

        if core_version:
            command += f"=={core_version}"
            msg = f"Using user specified ansible-core version: {core_version}"
            self._output.debug(msg)

        try:
            subprocess_run(
                command=command,
                verbose=self._config.args.verbose,
                msg=msg,
                output=self._output,
            )
        except subprocess.CalledProcessError as exc:
            err = f"Failed to install ansible-core: {format_process(exc)}"
            self._output.critical(err)

    def _install_dev_tools(self) -> None:
        """Install ansible developer tools."""
        msg = "Installing ansible-dev-tools."
        self._output.info(msg)

        adt = self._config.venv_bindir / "adt"
        if adt.exists():
            msg = "ansible-dev-tools is already installed."
            self._output.debug(msg)
            return
        msg = "Installing ansible-dev-tools."
        self._output.debug(msg)
        command = f"{self._config.venv_pip_install_cmd} ansible-dev-tools"

        ansible_dev_tools_version = getattr(self._config.args, "ansible_dev_tools_version", None)
        if ansible_dev_tools_version:
            command += f"=={ansible_dev_tools_version}"
            msg = f"Using user specified ansible-dev-tools version: {ansible_dev_tools_version}"
            self._output.debug(msg)
            msg = "Specifying an ansible-dev-tools version may result in installing a version that is no longer supported. Please use the latest release of ansible-dev-tools if you encounter issues or unexpected behavior."
            self._output.info(msg)

        try:
            subprocess_run(
                command=command,
                verbose=self._config.args.verbose,
                msg=msg,
                output=self._output,
            )
        except subprocess.CalledProcessError as exc:
            err = f"Failed to install ansible-dev-tools: {format_process(exc)}"
            self._output.critical(err)

    def _warn_if_core_version_incompatible(self, requested_version: str) -> None:
        """Warn if requested ansible-core version falls outside ansible-dev-tools requirements.

        Args:
            requested_version: The ansible-core version requested by the user.
        """
        # Only warn if seed is True (ansible-dev-tools will be installed)
        if not self._config.args.seed:
            return

        constraint = get_dependency_constraint(
            package_name="ansible-dev-tools",
            dependency_name="ansible-core",
            pip_command=self._config.venv_pip_cmd,
        )

        if not constraint:
            return  # Couldn't determine constraint

        # Check if packaging is available
        if specifiers is None or version is None:
            return  # Packaging not available, skip version comparison

        try:
            spec = specifiers.SpecifierSet(constraint)
            requested = version.parse(requested_version)

            if requested not in spec:
                msg = (
                    f"ansible-dev-tools requires ansible-core{constraint}, "
                    f"the requested version {requested_version} falls outside this range. "
                    f"There may be compatibility issues."
                )
                self._output.warning(msg)

        except Exception:  # noqa: BLE001, S110
            # If any error occurs during version comparison, skip warning gracefully
            pass

    def _install_galaxy_collections(
        self,
        collections: list[Collection],
    ) -> None:
        """Install the collection from galaxy.

        Args:
            collections: The collection objects.

        Raises:
            SystemError: If the collection installation fails.
        """
        collections_str = " ".join(
            [f"'{collection.original}'" for collection in collections],
        )
        msg = f"Installing collections from galaxy: {collections_str}"
        self._output.info(msg)

        for collection in collections:
            if collection.site_pkg_path.exists():
                msg = f"Removing installed {collection.site_pkg_path}"
                self._output.debug(msg)
                if collection.site_pkg_path.is_symlink():
                    collection.site_pkg_path.unlink()
                else:
                    shutil.rmtree(collection.site_pkg_path)

        command = (
            f"{self._config.galaxy_bin} collection"
            f" install {collections_str}"
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
                output=self._output,
            )
        except subprocess.CalledProcessError as exc:
            err = f"Failed to install collection: {format_process(exc)}"
            self._output.critical(err)
            raise SystemError(err) from exc  # pragma: no cover # critical exits
        installed = self.RE_GALAXY_INSTALLED.findall(proc.stdout)
        msg = f"Installed collections include: {oxford_join(installed)}"
        self._output.note(msg)

    def _install_galaxy_requirements(self) -> None:
        """Install the collections using requirements.yml."""
        method = "Pre-installing" if self._config.args.cpi else "Installing"
        msg = f"{method} collections from requirements file: {self._config.args.requirement}"

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
            f"{self._config.galaxy_bin} collection"
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
                output=self._output,
            )
        except subprocess.CalledProcessError as exc:
            err = f"Failed to install collections: {format_process(exc)}"
            self._output.critical(err)

        installed = self.RE_GALAXY_INSTALLED.findall(proc.stdout)
        if not self._config.args.cpi:
            msg = f"Installed collections include: {oxford_join(installed)}"
        else:
            msg = f"Source installed collections include: {oxford_join(installed)}"
        self._output.note(msg)

    def _find_files_using_git_ls_files(
        self,
        local_repo_path: Path | None,
    ) -> tuple[str | None, str | None]:
        """Copy collection files tracked using git ls-files to the build directory.

        Args:
            local_repo_path: The collection local path.

        Returns:
            string with the command used to list files or None
            string containing a list of files or nothing
        """
        msg = "List collection files using git ls-files."
        self._output.debug(msg)

        try:
            # Get the list of tracked files in the repository
            tracked_files_output = subprocess_run(
                command="git ls-files 2> /dev/null",
                cwd=local_repo_path,
                verbose=self._config.args.verbose,
                msg=msg,
                output=self._output,
            )
        except subprocess.CalledProcessError as exc:
            err = f"Failed to list collection using git ls-files: {format_process(exc)}"
            self._output.info(err)
            return None, None

        return "git ls-files", tracked_files_output.stdout

    def _find_files_using_ls(
        self,
        local_repo_path: Path | None,
    ) -> tuple[str | None, str | None]:
        """Copy collection files tracked using ls to the build directory.

        Args:
            local_repo_path: The collection local path.

        Returns:
            string with the command used to list files or None
            string containing a list of files or nothing
        """
        msg = "List collection files using ls."
        self._output.debug(msg)

        try:
            # Get the list of tracked files in the repository
            tracked_files_output = subprocess_run(
                command="ls 2> /dev/null",
                cwd=local_repo_path,
                verbose=self._config.args.verbose,
                msg=msg,
                output=self._output,
            )
        except subprocess.CalledProcessError as exc:
            err = f"Failed to list collection using ls: {format_process(exc)}"
            self._output.debug(err)
            return None, None

        return "ls", tracked_files_output.stdout

    def _copy_repo_files(
        self,
        local_repo_path: Path,
        destination_path: Path,
    ) -> None:
        """Copy collection files tracked in git to the build directory.

        Args:
            local_repo_path: The collection local path.
            destination_path: The build destination path.

        Raises:
            SystemExit: If no files are found.

        """
        # Get tracked files from git ls-files command
        found_using, files_stdout = self._find_files_using_git_ls_files(
            local_repo_path=local_repo_path,
        )

        if not files_stdout:
            found_using, files_stdout = self._find_files_using_ls(
                local_repo_path=local_repo_path,
            )

        if not files_stdout:
            msg = "No files found with either 'git ls-files' or 'ls"
            self._output.critical(msg)
            raise SystemExit(msg)  # pragma: no cover # critical exits

        msg = f"File list generated with '{found_using}'"
        self._output.info(msg)

        # Parse tracked files output
        files_list = files_stdout.split("\n")

        # Create the destination folder if it doesn't exist
        Path(destination_path).mkdir(parents=True, exist_ok=True)

        for file in files_list:
            src_file_path = Path(local_repo_path) / file
            dest_file_path = Path(destination_path) / file

            # Ensure the destination directory for the file exists
            dest_file_path.parent.mkdir(parents=True, exist_ok=True)

            if src_file_path.is_dir():
                # Skip directories
                continue

            try:
                # Copy the file
                shutil.copy2(src_file_path, dest_file_path)
            except shutil.Error as exc:
                err = f"Failed to copy collection to build directory: {exc}"
                self._output.critical(err)

    def _install_local_collection(
        self,
        collection: Collection,
    ) -> None:
        """Install the collection from the build directory.

        Args:
            collection: The collection object.

        Raises:
            RuntimeError: If tarball is not found or if more than one tarball is found.
            SystemError: If the collection installation fails.
        """
        msg = f"Installing local collection from: {collection.build_dir}"
        self._output.info(msg)

        self._copy_repo_files(
            local_repo_path=collection.path,
            destination_path=collection.build_dir,
        )

        command = (
            f"cd {collection.build_dir} &&"
            f" {self._config.galaxy_bin} collection build"
            f" --output-path {collection.build_dir}"
            " --force"
        )

        msg = "Running ansible-galaxy to build collection."
        self._output.debug(msg)

        try:
            subprocess_run(
                command=command,
                verbose=self._config.args.verbose,
                msg=msg,
                output=self._output,
            )
        except subprocess.CalledProcessError as exc:
            err = f"Failed to build collection: {format_process(exc)}"
            self._output.critical(err)

        built = [
            f
            for f in Path(collection.build_dir).iterdir()
            if f.is_file() and f.name.endswith(".tar.gz")
        ]
        if len(built) != 1:
            err = (
                "Expected to find one collection tarball in"
                f"{collection.build_dir}, found {len(built)}"
            )
            raise RuntimeError(err)
        tarball = built[0]

        if collection.site_pkg_path.exists():
            msg = f"Removing installed {collection.site_pkg_path}"
            self._output.debug(msg)
            if collection.site_pkg_path.is_symlink():
                collection.site_pkg_path.unlink()
            else:
                shutil.rmtree(collection.site_pkg_path)

        info_dirs = [
            entry
            for entry in self._config.site_pkg_collections_path.iterdir()
            if entry.is_dir()
            and entry.name.endswith(".info")
            and entry.name.startswith(collection.name)
        ]
        for info_dir in info_dirs:
            msg = f"Removing installed {info_dir}"
            self._output.debug(msg)
            shutil.rmtree(info_dir)

        command = (
            f"{self._config.galaxy_bin} collection"
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
                output=self._output,
            )
        except subprocess.CalledProcessError as exc:
            err = f"Failed to install collection: {format_process(exc)}"
            self._output.critical(err)
            raise SystemError(err) from exc  # pragma: no cover # critical exits

        # ansible-galaxy collection install does not include the galaxy.yml for version
        # nor does it create an info file that can be used to determine the version.
        # preserve the MANIFEST.json file for editable installs
        if not self._config.args.editable:
            shutil.copy(
                collection.build_dir / "galaxy.yml",
                collection.site_pkg_path / "galaxy.yml",
            )
        else:
            shutil.copy(
                collection.site_pkg_path / "MANIFEST.json",
                collection.cache_dir / "MANIFEST.json",
            )

        installed = self.RE_GALAXY_INSTALLED.findall(proc.stdout)
        msg = f"Installed collections include: {oxford_join(installed)}"
        self._output.note(msg)

    def _swap_editable_collection(self, collection: Collection) -> None:
        """Swap the installed collection with the current working directory.

        Args:
            collection: The collection object.

        """
        msg = f"Swapping {collection.name} with {collection.path}"
        self._output.info(msg)

        msg = f"Removing installed {collection.site_pkg_path}"
        self._output.debug(msg)
        if collection.site_pkg_path.exists():
            if collection.site_pkg_path.is_symlink():
                collection.site_pkg_path.unlink()
            else:
                shutil.rmtree(collection.site_pkg_path)

        msg = f"Symlinking {collection.site_pkg_path} to {collection.path}"
        self._output.debug(msg)
        collection.site_pkg_path.symlink_to(collection.path)

    def _pip_install(self) -> None:
        """Install the dependencies."""
        msg = "Installing python requirements."
        self._output.info(msg)

        command = f"{self._config.venv_pip_install_cmd} -r {self._config.discovered_python_reqs}"

        msg = f"Installing python requirements from {self._config.discovered_python_reqs}"
        self._output.debug(msg)
        work = "Installing python requirements"
        try:
            subprocess_run(
                command=command,
                verbose=self._config.args.verbose,
                msg=work,
                output=self._output,
            )
        except subprocess.CalledProcessError as exc:
            err = (
                "Failed to install requirements from"
                f" {self._config.discovered_python_reqs}: {format_process(exc)}"
            )
            self._output.critical(err)
        else:
            msg = "All python requirements are installed."
            self._output.note(msg)
