"""The installer."""

from __future__ import annotations

import logging
import shutil

from pathlib import Path
from typing import TYPE_CHECKING

from pip4a.collection import Collection, parse_collection_request
from pip4a.utils import collections_from_requirements, note


if TYPE_CHECKING:
    from pip4a.config import Config


logger = logging.getLogger(__name__)


class UnInstaller:
    """The uninstaller class."""

    def __init__(self: UnInstaller, config: Config) -> None:
        """Initialize the installer.

        Args:
            config: The application configuration.
        """
        self._config = config
        self._collection: Collection

    def run(self: UnInstaller) -> None:
        """Run the uninstaller."""
        if self._config.args.requirement:
            requirements_path = Path(self._config.args.requirement)
            if not requirements_path.exists():
                err = f"Failed to find requirements file: {requirements_path}"
                logger.critical(err)
            collections = collections_from_requirements(requirements_path)
            for collection in collections:
                self._collection = parse_collection_request(
                    string=collection["name"],
                    config=self._config,
                )
                self._remove_collection()
        else:
            self._collection = parse_collection_request(
                string=self._config.args.collection_specifier,
                config=self._config,
            )
            self._remove_collection()

    def _remove_collection(self: UnInstaller) -> None:
        """Remove the collection."""
        msg = f"Checking {self._collection.name} at {self._collection.site_pkg_path}"
        logger.debug(msg)

        if self._collection.site_pkg_path.exists():
            msg = f"Exists: {self._collection.site_pkg_path}"
            logger.debug(msg)

            if self._collection.site_pkg_path.is_symlink():
                self._collection.site_pkg_path.unlink()
            else:
                shutil.rmtree(self._collection.site_pkg_path)
            msg = f"Removed {self._collection.name}"
            note(msg)
        else:
            err = (
                f"Failed to find {self._collection.name}:"
                f" {self._collection.site_pkg_path}"
            )
            logger.warning(err)

        for entry in self._config.site_pkg_collections_path.iterdir():
            if all(
                (
                    entry.is_dir(),
                    entry.name.startswith(self._collection.name),
                    entry.suffix == ".info",
                ),
            ):
                shutil.rmtree(entry)
                msg = f"Removed {self._collection.name}*.info: {entry}"
                logger.debug(msg)

        collection_namespace_root = self._collection.site_pkg_path.parent
        try:
            collection_namespace_root.rmdir()
            msg = f"Removed collection namespace root: {collection_namespace_root}"
            logger.debug(msg)
        except FileNotFoundError:
            pass
        except OSError as exc:
            msg = f"Failed to remove collection namespace root: {exc}"
            logger.debug(msg)

        try:
            self._config.site_pkg_collections_path.rmdir()
            msg = f"Removed collection root: {self._config.site_pkg_collections_path}"
            logger.debug(msg)
        except FileNotFoundError:
            pass
        except OSError as exc:
            msg = f"Failed to remove collection root: {exc}"
            logger.debug(msg)
