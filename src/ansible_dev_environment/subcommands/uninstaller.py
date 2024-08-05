"""The installer."""

from __future__ import annotations

import shutil

from pathlib import Path
from typing import TYPE_CHECKING

from ansible_dev_environment.collection import (
    Collection,
    parse_collection_request,
)
from ansible_dev_environment.utils import collections_from_requirements


if TYPE_CHECKING:
    from ansible_dev_environment.config import Config
    from ansible_dev_environment.output import Output


class UnInstaller:
    """The uninstaller class."""

    def __init__(self: UnInstaller, config: Config, output: Output) -> None:
        """Initialize the installer.

        Args:
            config: The application configuration.
            output: The application output object.
        """
        self._config = config
        self._output = output
        self._collection: Collection

    def run(self: UnInstaller) -> None:
        """Run the uninstaller."""
        if len(self._config.args.collection_specifier) > 1:
            msg = "Only one collection can be uninstalled at a time."
            self._output.critical(msg)

        if self._config.args.requirement:
            requirements_path = Path(self._config.args.requirement)
            if not requirements_path.exists():
                err = f"Failed to find requirements file: {requirements_path}"
                self._output.critical(err)
            collections = collections_from_requirements(requirements_path)
            for collection in collections:
                self._collection = parse_collection_request(
                    string=collection["name"],
                    config=self._config,
                    output=self._output,
                )
                self._remove_collection()
        else:
            self._collection = parse_collection_request(
                string=self._config.args.collection_specifier[0],
                config=self._config,
                output=self._output,
            )
            self._remove_collection()

    def _remove_collection(self: UnInstaller) -> None:
        """Remove the collection."""
        msg = f"Checking {self._collection.name} at {self._collection.site_pkg_path}"
        self._output.debug(msg)

        if self._collection.site_pkg_path.exists():
            msg = f"Exists: {self._collection.site_pkg_path}"
            self._output.debug(msg)

            if self._collection.site_pkg_path.is_symlink():
                self._collection.site_pkg_path.unlink()
            else:
                shutil.rmtree(self._collection.site_pkg_path)
            msg = f"Removed {self._collection.name}"
            self._output.note(msg)
        else:
            err = f"Failed to find {self._collection.name}: {self._collection.site_pkg_path}"
            self._output.warning(err)

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
                self._output.debug(msg)

        collection_namespace_root = self._collection.site_pkg_path.parent

        if collection_namespace_root.exists():
            try:
                collection_namespace_root.rmdir()
                msg = f"Removed collection namespace root: {collection_namespace_root}"
                self._output.debug(msg)
            except OSError as exc:
                msg = f"Failed to remove collection namespace root: {exc}"
                self._output.debug(msg)

        if self._config.site_pkg_collections_path.exists():
            try:
                self._config.site_pkg_collections_path.rmdir()
                msg = f"Removed collection root: {self._config.site_pkg_collections_path}"
                self._output.debug(msg)
            except OSError as exc:
                msg = f"Failed to remove collection root: {exc}"
                self._output.debug(msg)
