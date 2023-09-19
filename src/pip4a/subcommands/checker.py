"""The dependency checker."""

from __future__ import annotations

import json
import subprocess

from typing import TYPE_CHECKING

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import Version

from pip4a.utils import (
    builder_introspect,
    collect_manifests,
    oxford_join,
    subprocess_run,
)


if TYPE_CHECKING:
    from pip4a.config import Config
    from pip4a.output import Output


class Checker:
    """The dependency checker."""

    def __init__(self: Checker, config: Config, output: Output) -> None:
        """Initialize the checker.

        Args:
            config: The application configuration.
            output: The application output object.
        """
        self._config: Config = config
        self._collections_missing: bool
        self._output: Output = output
        self._system_dep_missing: bool

    def run(self: Checker) -> None:
        """Run the checker."""
        builder_introspect(config=self._config)
        self._collection_deps()
        self.system_deps()
        self._python_deps()

    def _collection_deps(self: Checker) -> None:  # noqa: C901, PLR0912, PLR0915
        """Check collection dependencies."""
        collections = collect_manifests(
            target=self._config.site_pkg_collections_path,
            venv_cache_dir=self._config.venv_cache_dir,
        )
        missing = False
        for collection_name, details in collections.items():
            error = "Collection {collection_name} has malformed metadata."
            if not isinstance(details, dict):
                self._output.error(error)
                continue
            if not isinstance(details["collection_info"], dict):
                self._output.error(error)
                continue
            if not isinstance(details["collection_info"]["dependencies"], dict):
                self._output.error(error)
                continue

            msg = f"Checking dependencies for {collection_name}."
            self._output.debug(msg)

            deps = details["collection_info"]["dependencies"]

            if not deps:
                msg = f"Collection {collection_name} has no dependencies."
                self._output.debug(msg)
                continue
            for dep, version in deps.items():
                if not isinstance(version, str):
                    err = (
                        f"Collection {collection_name} has malformed"
                        f" dependency version for {dep}."
                    )
                    self._output.error(err)
                    continue
                try:
                    spec = SpecifierSet(version)
                except InvalidSpecifier:
                    spec = SpecifierSet(">=0.0.0")
                    msg = f"Invalid version specifier {version}, assuming >=0.0.0."
                    self._output.debug(msg)
                if dep in collections:
                    dependency = collections[dep]
                    error = "Collection {dep} has malformed metadata."
                    if not isinstance(dependency, dict):
                        self._output.error(error)
                        continue
                    if not isinstance(dependency["collection_info"], dict):
                        self._output.error(error)
                        continue

                    dep_version = dependency["collection_info"]["version"]
                    if not isinstance(dep_version, str):
                        self._output.error(error)
                        continue
                    dep_spec = Version(dep_version)
                    if not spec.contains(dep_spec):
                        err = (
                            f"Collection {collection_name} requires {dep} {version}"
                            f" but {dep} {dep_version} is installed."
                        )
                        self._output.error(err)
                        missing = True

                    else:
                        msg = (
                            f"Collection {collection_name} requires {dep} {version}"
                            f" and {dep} {dep_version} is installed."
                        )
                        self._output.debug(msg)
                else:
                    err = (
                        f"Collection {collection_name} requires"
                        f" {dep} {version} but it is not installed."
                    )
                    self._output.error(err)
                    msg = f"Try running `pip4a install {dep}`"
                    self._output.hint(msg)
                    missing = True

        if not missing:
            msg = "All dependant collections are installed."
            self._output.note(msg)
        self._collections_missing = missing

    def _python_deps(self: Checker) -> None:
        """Check Python dependencies."""
        if self._system_dep_missing:
            msg = "System packages are missing. Python dependency checking may fail."
            self._output.warning(msg)
            msg = "Install system packages and re-run `pip4a check`."
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
                term_features=self._config.term_features,
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

    def system_deps(self: Checker) -> None:
        """Check the bindep file."""
        msg = "Checking system packages."
        self._output.info(msg)

        command = f"bindep -b -f {self._config.discovered_bindep_reqs}"
        work = "Checking system package requirements"
        try:
            subprocess_run(
                command=command,
                verbose=self._config.args.verbose,
                msg=work,
                term_features=self._config.term_features,
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
