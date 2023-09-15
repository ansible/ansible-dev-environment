"""Lister module for pip4a."""

from __future__ import annotations

import logging

from typing import TYPE_CHECKING

from pip4a.utils import collect_manifests, term_link


if TYPE_CHECKING:
    from pip4a.config import Config


logger = logging.getLogger(__name__)


class Lister:
    """The Lister class."""

    def __init__(self: Lister, config: Config) -> None:
        """Initialize the Lister.

        Args:
            config: The application configuration.
        """
        self._config: Config = config

    def run(self: Lister) -> None:
        """Run the Lister."""
        # pylint: disable=too-many-locals
        collections = collect_manifests(
            target=self._config.site_pkg_collections_path,
            venv_cache_dir=self._config.venv_cache_dir,
        )

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

        for fqcn, collection in collections.items():
            err = f"Collection {fqcn} has malformed metadata."
            ci = collection["collection_info"]
            if not isinstance(ci, dict):
                logger.error(err)
                continue
            collection_name = ci["name"]
            collection_namespace = ci["namespace"]
            collection_version = ci["version"]
            if not isinstance(collection_name, str):
                logger.error(err)
                continue
            if not isinstance(collection_namespace, str):
                logger.error(err)
                continue
            if not isinstance(collection_version, str):
                logger.error(err)
                continue

            collection_path = (
                self._config.site_pkg_collections_path
                / collection_namespace
                / collection_name
            )
            if collection_path.is_symlink():
                editable_location = str(collection_path.resolve())
            else:
                editable_location = ""

            docs = ci.get("documentation")
            homepage = ci.get("homepage")
            repository = ci.get("repository")
            issues = ci.get("issues")
            link = docs or homepage or repository or issues or "http://ansible.com"
            if not isinstance(link, str):
                msg = "Link is not a string."
                raise TypeError(msg)
            fqcn_linked = term_link(
                uri=link,
                label=fqcn,
                term_features=self._config.term_features,
            )

            print(  # noqa: T201
                fqcn_linked + " " * (column1_width - len(fqcn)),
                f"{ci['version']: <{column2_width}}",
                f"{editable_location: <{column3_width}}",
            )
