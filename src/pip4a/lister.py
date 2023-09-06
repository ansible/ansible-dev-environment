"""Lister module for pip4a."""

from __future__ import annotations

import logging

from typing import TYPE_CHECKING

import yaml


if TYPE_CHECKING:
    from .config import Config


logger = logging.getLogger(__name__)


class Lister:
    """The Lister class."""

    def __init__(self: Lister, config: Config, output_format: str) -> None:
        """Initialize the Lister.

        Args:
            config: The application configuration.
            output_format: The output format to use.
        """
        self._config: Config = config
        self._output_format: str = output_format

    def run(self: Lister) -> None:
        """Run the Lister."""
        # pylint: disable=too-many-locals
        all_info_dirs = [
            entry
            for entry in self._config.site_pkg_collections_path.iterdir()
            if entry.name.endswith(".info")
        ]

        collections = {}
        for namespace_dir in self._config.site_pkg_collections_path.iterdir():
            if not namespace_dir.is_dir():
                continue

            for name_dir in namespace_dir.iterdir():
                if not name_dir.is_dir():
                    continue
                some_info_dirs = [
                    info_dir
                    for info_dir in all_info_dirs
                    if f"{namespace_dir.name}.{name_dir.name}" in info_dir.name
                ]
                if some_info_dirs:
                    info_dir = some_info_dirs[0]
                    with (info_dir / "GALAXY.yml").open() as info_file:
                        info = yaml.safe_load(info_file)
                        collections[f"{namespace_dir.name}.{name_dir.name}"] = {
                            "version": info["version"],
                            "editable_location": "",
                        }
                elif (name_dir / "galaxy.yml").exists():
                    location = name_dir.resolve() if name_dir.is_symlink() else ""
                    with (name_dir / "galaxy.yml").open() as info_file:
                        info = yaml.safe_load(info_file)
                        collections[f"{namespace_dir.name}.{name_dir.name}"] = {
                            "version": info["version"],
                            "editable_location": f"{location}",
                        }
                else:
                    collections[f"{namespace_dir.name}.{name_dir.name}"] = {
                        "version": "unknown",
                        "editable_location": "",
                    }

        if self._output_format == "list":
            column1_width = 30
            column2_width = 10
            column3_width = 25

            print(  # noqa: T201
                f"{'Collection': <{column1_width}}"
                f" {'Version': <{column2_width}}"
                f" {'Editable project location': <{column3_width}}",
            )
            print(  # noqa: T201
                f"{'-' * (column1_width)}"
                f" {'-' * (column2_width)}"
                f" {'-' * (column3_width)}",
            )

            sorted_keys = sorted(collections.keys())
            for collection_name in sorted_keys:
                details = collections[collection_name]
                print(  # noqa: T201
                    f"{collection_name: <{column1_width}}"
                    f" {details['version']: <{column2_width}}",
                    f" {details['editable_location']: <{column3_width}}",
                )
