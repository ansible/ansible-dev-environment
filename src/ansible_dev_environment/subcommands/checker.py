"""The dependency checker."""

from __future__ import annotations

import json
import subprocess
import sys

from typing import TYPE_CHECKING, Any

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import Version

from ansible_dev_environment.utils import (
    builder_introspect,
    collect_manifests,
    oxford_join,
    subprocess_run,
)


if TYPE_CHECKING:
    from ansible_dev_environment.config import Config
    from ansible_dev_environment.output import Output


class Checker:
    """The dependency checker."""

    def __init__(self, config: Config, output: Output) -> None:
        """Initialize the checker.

        Args:
            config: The application configuration.
            output: The application output object.
        """
        self._config: Config = config
        self._collections_missing: bool
        self._output: Output = output
        self._system_dep_missing: bool

    def run(self) -> None:
        """Run the checker."""
        builder_introspect(config=self._config, output=self._output)
        self._collection_deps()
        self.system_deps()
        self._python_deps()

    def _validate_collection_info(self, details: dict[str, Any], error_msg: str) -> bool:
        """Validate collection metadata structure.

        Args:
            details: Collection details dictionary.
            error_msg: Error message to display if validation fails.

        Returns:
            True if valid, False otherwise.
        """
        if not isinstance(details, dict):  # pragma: no cover
            self._output.error(error_msg)
            return False
        ci = details.get("collection_info")
        if not isinstance(ci, dict):  # pragma: no cover
            self._output.error(error_msg)
            return False
        if not isinstance(ci.get("dependencies"), dict):  # pragma: no cover
            self._output.error(error_msg)
            return False
        return True

    def _check_installed_dependency(
        self,
        collection_name: str,
        dep: str,
        version: str,
        spec: SpecifierSet,
        dependency: dict[str, Any],
    ) -> bool:
        """Check version of an installed dependency.

        Args:
            collection_name: Name of the collection requiring the dependency.
            dep: Name of the dependency.
            version: Required version specifier.
            spec: Parsed SpecifierSet for version.
            dependency: Dependency collection details.

        Returns:
            True if version mismatch (missing), False otherwise.
        """
        error = f"Collection {dep} has malformed metadata."
        if not isinstance(dependency, dict):  # pragma: no cover
            self._output.error(error)
            return False
        dep_ci = dependency.get("collection_info")
        if not isinstance(dep_ci, dict):  # pragma: no cover
            self._output.error(error)
            return False

        dep_version = dep_ci.get("version")
        if not isinstance(dep_version, str):  # pragma: no cover
            self._output.error(error)
            return False
        dep_spec = Version(dep_version)
        if not spec.contains(dep_spec):
            err = (
                f"Collection {collection_name} requires {dep} {version}"
                f" but {dep} {dep_version} is installed."
            )
            self._output.error(err)
            return True

        msg = (
            f"Collection {collection_name} requires {dep} {version}"
            f" and {dep} {dep_version} is installed."
        )
        self._output.debug(msg)
        return False

    def _check_dependency(
        self,
        collection_name: str,
        dep: str,
        version: str,
        collections: dict[str, Any],
    ) -> bool:
        """Check a single dependency.

        Args:
            collection_name: Name of the collection requiring the dependency.
            dep: Name of the dependency.
            version: Required version specifier.
            collections: Dictionary of all collections.

        Returns:
            True if dependency missing or version mismatch, False otherwise.
        """
        if not isinstance(version, str):  # pragma: no cover
            err = f"Collection {collection_name} has malformed dependency version for {dep}."
            self._output.error(err)
            return False
        try:
            spec = SpecifierSet(version)
        except InvalidSpecifier:
            spec = SpecifierSet(">=0.0.0")
            msg = f"Invalid version specifier {version}, assuming >=0.0.0."
            self._output.debug(msg)
        if dep in collections:
            dependency = collections[dep]
            return self._check_installed_dependency(collection_name, dep, version, spec, dependency)
        err = f"Collection {collection_name} requires {dep} {version} but it is not installed."
        self._output.error(err)
        msg = f"Try running `ade install {dep}`"
        self._output.hint(msg)
        return True

    def _collection_deps(self) -> None:
        """Check collection dependencies."""
        collections = collect_manifests(
            target=self._config.site_pkg_collections_path,
            venv_cache_dir=self._config.venv_cache_dir,
        )
        missing = False
        for collection_name, details in collections.items():
            error = f"Collection {collection_name} has malformed metadata."
            if not self._validate_collection_info(details, error):
                continue

            msg = f"Checking dependencies for {collection_name}."
            self._output.debug(msg)

            ci: dict[str, Any] = details["collection_info"]  # type: ignore[assignment]
            deps: dict[str, str] = ci["dependencies"]

            if not deps:
                msg = f"Collection {collection_name} has no dependencies."
                self._output.debug(msg)
                continue
            for dep, version in deps.items():
                if self._check_dependency(collection_name, dep, version, collections):
                    missing = True

        if not missing:
            msg = "All dependant collections are installed."
            self._output.note(msg)
        self._collections_missing = missing

    def _python_deps(self) -> None:
        """Check Python dependencies."""
        if self._system_dep_missing:
            msg = "System packages are missing. Python dependency checking may fail."
            self._output.warning(msg)
            msg = "Install system packages and re-run `ade check`."
            self._output.hint(msg)
        missing_file = self._config.venv_cache_dir / "pip-report.txt"
        command = (
            f"{self._config.venv_interpreter} -m pip install -r"
            f" {self._config.discovered_python_reqs} --dry-run"
            f" --report {missing_file}"
        )
        work = "Building python package dependency tree"

        try:
            subprocess_run(
                command=command,
                verbose=self._config.args.verbose,
                msg=work,
                output=self._output,
            )
        except subprocess.CalledProcessError as exc:
            err = f"Failed to check python dependencies: {exc}"
            self._output.critical(err)
        with missing_file.open() as file:
            pip_report = json.load(file)

        if self._collections_missing:
            msg = "Python packages required by missing collections are not included."
            self._output.note(msg)

        if "install" not in pip_report or not pip_report["install"]:
            if not self._collections_missing:
                msg = "All python dependencies are installed."
                self._output.note(msg)
            return

        missing = [
            f"{package['metadata']['name']}=={package['metadata']['version']}"
            for package in pip_report["install"]
        ]

        err = f"Missing python dependencies: {oxford_join(missing)}"
        self._output.error(err)
        msg = f"Try running `pip install {' '.join(missing)}`."
        self._output.hint(msg)

    def system_deps(self) -> None:
        """Check the bindep file."""
        msg = "Checking system packages."
        self._output.info(msg)

        command = f"{sys.executable} -m bindep -b -f {self._config.discovered_bindep_reqs}"
        work = "Checking system package requirements"
        try:
            subprocess_run(
                command=command,
                verbose=self._config.args.verbose,
                msg=work,
                output=self._output,
            )
        except subprocess.CalledProcessError as exc:
            if exc.stderr:
                msg = f"Bindep failed to find required system packages. {exc.stderr}"
                self._output.error(msg)
                msg = "Check the format of the bindep.txt file."
                self._output.hint(msg)
                self._system_dep_missing = True
                return
            lines = exc.stdout.splitlines()
            msg = (
                "Required system packages are missing."
                " Please use the system package manager to install them."
                "\n- "
            )
            msg += "\n- ".join(lines)
            self._output.warning(msg)
            self._system_dep_missing = True
        else:
            msg = "All required system packages are installed."
            self._output.note(msg)
            self._system_dep_missing = False
            return
