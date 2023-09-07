"""The dependency checker."""

from __future__ import annotations

import logging

from typing import TYPE_CHECKING

from packaging.specifiers import SpecifierSet
from packaging.version import Version

from .utils import collect_manifests


if TYPE_CHECKING:
    from .config import Config


logger = logging.getLogger(__name__)


class Checker:
    """The dependency checker."""

    def __init__(self: Checker, config: Config) -> None:
        """Initialize the checker."""
        self.config: Config = config

    def run(self: Checker) -> None:
        """Run the checker."""
        logger.info("Running dependency checker.")
        collections = collect_manifests(
            target=self.config.site_pkg_collections_path,
            venv_cache_dir=self.config.venv_cache_dir,
        )
        breakpoint()
        for collection_name, details in collections.items():
            msg = f"Checking dependencies for {collection_name}."
            logger.debug(msg)
            deps = details["collection_info"]["dependencies"]
            if not deps:
                msg = f"Collection {collection_name} has no dependencies."
                logger.debug(msg)
                continue
            for dep, version in deps.items():
                spec = SpecifierSet(version)
                if dep in collections:
                    dep_version = collections[dep]["collection_info"]["version"]
                    dep_spec = Version(dep_version)
                    if not spec.contains(dep_spec):
                        err = (
                            f"Collection {collection_name} requires {dep} {version}"
                            f" but {dep} {dep_version} is installed."
                        )
                        logger.warning(err)
                    else:
                        msg = (
                            f"Collection {collection_name} requires {dep} {version}"
                            f" and {dep} {dep_version} is installed."
                        )
                        logger.debug(msg)
