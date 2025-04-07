"""Some common definitions."""

from __future__ import annotations

from configparser import ConfigParser
from dataclasses import dataclass
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path


@dataclass
class AnsibleCfg:
    """ansible.cfg file abstraction.

    Attributes:
        path: Path to the ansible.cfg file.
    """

    path: Path

    @property
    def exists(self) -> bool:
        """Check if the ansible.cfg file exists."""
        return self.path.exists()

    @property
    def collections_path_is_dot(self) -> bool:
        """Check if the collection path is a dot.

        Returns:
            bool: True if the collection path is a dot.
        """
        config = ConfigParser()
        config.read(self.path)
        return config.get("defaults", "collections_path", fallback=None) == "."

    def set_or_update_collection_path(self) -> None:
        """Set or update the collection path in the ansible.cfg file.

        The configparser doesn't preserve comments, so we need to read the file
        and write it back with the new collection path.
        """
        config = ConfigParser()
        config.read(self.path)
        if not config.has_section("defaults"):
            with self.path.open(mode="r+") as file:
                content_str = file.read()
                file.seek(0, 0)
                file.truncate()
                file.write("[defaults]\ncollections_path = .\n" + content_str)
                file.write("\n")
            return

        if not config.has_option("defaults", "collections_path"):
            with self.path.open(mode="r+") as file:
                content_list = file.read().splitlines()
                idx = content_list.index("[defaults]") + 1
                content_list.insert(idx, "collections_path = .")
                file.seek(0, 0)
                file.truncate()
                file.write("\n".join(content_list))
                file.write("\n")
            return

        with self.path.open(mode="r+") as file:
            content_list = file.read().splitlines()
            idx = next(
                i for i, line in enumerate(content_list) if line.startswith("collections_path")
            )
            content_list[idx] = "collections_path = ."
            file.seek(0, 0)
            file.truncate()
            file.write("\n".join(content_list))
            file.write("\n")
        return

    def author_new(self) -> None:
        """Author the file and update it."""
        config = ConfigParser()
        config.add_section("defaults")
        config.set("defaults", "collections_path", ".")
        with self.path.open(mode="w") as f:
            config.write(f)
