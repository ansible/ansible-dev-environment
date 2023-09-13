"""Lister module for pip4a."""

from __future__ import annotations

import logging

from typing import TYPE_CHECKING

from pip4a.utils import collections_meta


if TYPE_CHECKING:
    from pip4a.config import Config


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
        collections = collections_meta(self._config)

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
