"""The installer."""

from __future__ import annotations

import logging
import shutil

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from .config import Config


logger = logging.getLogger(__name__)


class UnInstaller:
    """The uninstaller class."""

    def __init__(self: UnInstaller, config: Config) -> None:
        """Initialize the installer.

        Args:
            config: The application configuration.
        """
        self._config = config

    def run(self: UnInstaller) -> None:
        """Run the uninstaller."""
        self._remove_collection()

    def _remove_collection(self: UnInstaller) -> None:
        """Remove the collection."""
        msg = f"Checking {self._config.collection_name} at {self._config.site_pkg_collection_path}"
        logger.debug(msg)

        if self._config.site_pkg_collection_path.exists():
            msg = f"Exists: {self._config.site_pkg_collection_path}"
            logger.debug(msg)

            if self._config.site_pkg_collection_path.is_symlink():
                self._config.site_pkg_collection_path.unlink()
            else:
                shutil.rmtree(self._config.site_pkg_collection_path)
            msg = f"Removed {self._config.collection_name}: {self._config.site_pkg_collection_path}"
            logger.info(msg)
        else:
            msg = (
                f"Failed to find {self._config.collection_name}:"
                f" {self._config.site_pkg_collection_path}"
            )
            logger.debug(msg)


        for entry in self._config.site_pkg_collections_path.iterdir():
            if all(
                (
                    entry.is_dir(),
                    entry.name.startswith(self._config.collection_name),
                    entry.suffix == ".info",
                ),
            ):
                shutil.rmtree(entry)
                msg = f"Removed {self._config.collection_name}*.info: {entry}"
                logger.info(msg)

        collection_namespace_root = self._config.site_pkg_collection_path.parent
        try:
            collection_namespace_root.rmdir()
            msg = f"Removed collection namespace root: {collection_namespace_root}"
            logger.info(msg)
        except FileNotFoundError:
            pass
        except OSError as exc:
            err = f"Failed to remove collection namespace root: {exc}"
            logger.warning(err)

        try:
            self._config.site_pkg_collections_path.rmdir()
            msg = f"Removed collection root: {self._config.site_pkg_collections_path}"
            logger.info(msg)
        except FileNotFoundError:
            pass
        except OSError as exc:
            msg = f"Failed to remove collection root: {exc}"
            logger.debug(msg)

