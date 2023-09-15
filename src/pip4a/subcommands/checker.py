"""The dependency checker."""

from __future__ import annotations

import json
import logging
import subprocess

from typing import TYPE_CHECKING

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import Version

from pip4a.utils import (
    builder_introspect,
    collect_manifests,
    hint,
    note,
    oxford_join,
    subprocess_run,
)


if TYPE_CHECKING:
    from pip4a.config import Config


logger = logging.getLogger(__name__)


class Checker:
    """The dependency checker."""

    def __init__(self: Checker, config: Config) -> None:
        """Initialize the checker."""
        self._config: Config = config
        self._collections_missing: bool

    def run(self: Checker) -> None:
        """Run the checker."""
        self._collection_deps()
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
                logger.error(error)
                continue
            if not isinstance(details["collection_info"], dict):
                logger.error(error)
                continue
            if not isinstance(details["collection_info"]["dependencies"], dict):
                logger.error(error)
                continue

            msg = f"Checking dependencies for {collection_name}."
            logger.debug(msg)

            deps = details["collection_info"]["dependencies"]

            if not deps:
                msg = f"Collection {collection_name} has no dependencies."
                logger.debug(msg)
                continue
            for dep, version in deps.items():
                if not isinstance(version, str):
                    err = (
                        f"Collection {collection_name} has malformed"
                        f" dependency version for {dep}."
                    )
                    logger.error(err)
                    continue
                try:
                    spec = SpecifierSet(version)
                except InvalidSpecifier:
                    spec = SpecifierSet(">=0.0.0")
                    msg = f"Invalid version specifier {version}, assuming >=0.0.0."
                    logger.debug(msg)
                if dep in collections:
                    dependency = collections[dep]
                    error = "Collection {dep} has malformed metadata."
                    if not isinstance(dependency, dict):
                        logger.error(error)
                        continue
                    if not isinstance(dependency["collection_info"], dict):
                        logger.error(error)
                        continue

                    dep_version = dependency["collection_info"]["version"]
                    if not isinstance(dep_version, str):
                        logger.error(error)
                        continue
                    dep_spec = Version(dep_version)
                    if not spec.contains(dep_spec):
                        err = (
                            f"Collection {collection_name} requires {dep} {version}"
                            f" but {dep} {dep_version} is installed."
                        )
                        logger.error(err)
                        missing = True

                    else:
                        msg = (
                            f"Collection {collection_name} requires {dep} {version}"
                            f" and {dep} {dep_version} is installed."
                        )
                        logger.debug(msg)
                else:
                    err = (
                        f"Collection {collection_name} requires"
                        f" {dep} {version} but it is not installed."
                    )
                    logger.error(err)
                    msg = f"Try running `pip4a install {dep}`"
                    hint(msg)
                    missing = True

        if not missing:
            msg = "All dependant collections are installed."
            note(msg)
        self._collections_missing = missing

    def _python_deps(self: Checker) -> None:
        """Check Python dependencies."""
        builder_introspect(config=self._config)

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
            logger.critical(err)
        with missing_file.open() as file:
            pip_report = json.load(file)

        if self._collections_missing:
            msg = "Python packages required by missing collections are not included."
            note(msg)

        if "install" not in pip_report or not pip_report["install"]:
            if not self._collections_missing:
                msg = "All python dependencies are installed."
                note(msg)
            return

        missing = [
            f"{package['metadata']['name']}=={package['metadata']['version']}"
            for package in pip_report["install"]
        ]

        err = f"Missing python dependencies: {oxford_join(missing)}"
        logger.error(err)
        msg = f"Try running `pip install {' '.join(missing)}`."
        hint(msg)
