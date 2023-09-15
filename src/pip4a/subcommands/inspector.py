"""The collection inspect command."""

from __future__ import annotations

import json
import logging

from typing import TYPE_CHECKING

from pip4a.utils import collect_manifests


if TYPE_CHECKING:
    from pip4a.config import Config

try:
    from pip._vendor.rich import print_json

    HAS_RICH = True
except ImportError:
    HAS_RICH = False


logger = logging.getLogger(__name__)


class Inspector:
    """The Inspector class."""

    def __init__(self: Inspector, config: Config) -> None:
        """Initialize the Inspector."""
        self._config: Config = config

    def run(self: Inspector) -> None:
        """Run the Inspector."""
        # pylint: disable=too-many-locals
        collections = collect_manifests(
            target=self._config.site_pkg_collections_path,
            venv_cache_dir=self._config.venv_cache_dir,
        )

        output = json.dumps(collections, indent=4, sort_keys=True)
        if HAS_RICH and self._config.term_features.color:
            print_json(output)
        else:
            print(output)  # noqa: T201
