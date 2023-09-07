"""The collection inspect command."""

from __future__ import annotations

import json
import logging
import os

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from .config import Config

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

    def run(self: Inspector) -> None:  # noqa: C901, PLR0912
        """Run the Inspector."""
        # pylint: disable=too-many-locals
        collections = {}
        for namespace_dir in self._config.site_pkg_collections_path.iterdir():
            if not namespace_dir.is_dir():
                continue

            for name_dir in namespace_dir.iterdir():
                if not name_dir.is_dir():
                    continue
                manifest = name_dir / "MANIFEST.json"
                if not manifest.exists():
                    manifest = (
                        self._config.venv_cache_dir
                        / f"{namespace_dir.name}.{name_dir.name}"
                        / "MANIFEST.json"
                    )
                if not manifest.exists():
                    msg = f"Manifest not found for {namespace_dir.name}.{name_dir.name}"
                    logger.debug(msg)
                    continue
                with manifest.open() as manifest_file:
                    manifest_json = json.load(manifest_file)

                cname = f"{namespace_dir.name}.{name_dir.name}"

                collections[cname] = manifest_json
                c_info = collections[cname].get("collection_info", {})
                if not c_info:
                    collections[cname]["collection_info"] = {}
                    c_info = collections[cname]["collection_info"]
                c_info["requirements"] = {"python": {}, "system": []}

                python_requirements = c_info["requirements"]["python"]
                system_requirements = c_info["requirements"]["system"]

                for file in name_dir.iterdir():
                    if not file.is_file():
                        continue
                    if not file.name.endswith(".txt"):
                        continue
                    if "requirements" in file.name:
                        with file.open() as requirements_file:
                            requirements = requirements_file.read().splitlines()
                            python_requirements[file.stem] = requirements
                    if file.stem == "bindep":
                        with file.open() as requirements_file:
                            requirements = requirements_file.read().splitlines()
                            system_requirements.extend(requirements)

        output = json.dumps(collections, indent=4, sort_keys=True)
        if HAS_RICH and not os.environ.get("NOCOLOR"):
            print_json(output)
        else:
            print(output)  # noqa: T201
