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
        contents = self.path.read_text().splitlines()
        collections_path = "collections_path = ."

        if "[defaults]" not in contents:
            contents.insert(0, "[defaults]")

        idx = [i for i, line in enumerate(contents) if line.startswith("collections_path")]

        if idx:
            contents[idx[0]] = collections_path
        else:
            insert_at = contents.index("[defaults]") + 1
            contents.insert(insert_at, collections_path)

        with self.path.open(mode="w") as file:
            file.write("\n".join(contents) + "\n")

    def author_new(self) -> None:
        """Author the file and update it."""
        contents = ["[defaults]", "collections_path = ."]
        with self.path.open(mode="w") as file:
            file.write("\n".join(contents) + "\n")
