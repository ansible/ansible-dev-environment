"""Utility functions."""

from __future__ import annotations

import logging

from pathlib import Path

import yaml


logger = logging.getLogger(__name__)


def get_galaxy() -> tuple[str, dict[str, str]]:
    """Retreive the collection name from the galaxy.yml file.

    Returns:
        str: The collection name and dependencies
    """
    file_name = Path("galaxy.yml").resolve()
    if not file_name.exists():
        err = f"Failed to find {file_name}, please run from the collection root."
        logger.critical(err)

    with file_name.open(encoding="utf-8") as fileh:
        try:
            yaml_file = yaml.safe_load(fileh)
        except yaml.YAMLError as exc:
            err = f"Failed to load yaml file: {exc}"
            logger.critical(err)

    dependencies = yaml_file.get("dependencies", [])
    try:
        collection_name = yaml_file["namespace"] + "." + yaml_file["name"]
        msg = f"Found collection name: {collection_name} from {file_name}."
        logger.info(msg)
        return yaml_file["namespace"] + "." + yaml_file["name"], dependencies
    except KeyError as exc:
        err = f"Failed to find collection name in {file_name}: {exc}"
        logger.critical(err)
    raise SystemExit(1)  # We shouln't be here
