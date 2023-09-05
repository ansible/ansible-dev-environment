"""Utility functions."""

from __future__ import annotations

import logging
import subprocess

from pathlib import Path

import subprocess_tee
import yaml


logger = logging.getLogger(__name__)


def get_galaxy() -> tuple[str, dict[str, str]]:
    """Retrieve the collection name from the galaxy.yml file.

    Returns:
        str: The collection name and dependencies

    Raises:
        SystemExit: If the collection name is not found
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
    raise SystemExit(1)  # We shouldn't be here


def subprocess_run(
    verbose: bool,  # noqa: FBT001
    command: str,
) -> subprocess.CompletedProcess[str]:
    """Run a subprocess command."""
    msg = f"Running command: {command}"
    logger.debug(msg)
    if verbose:
        return subprocess_tee.run(
            command,
            check=True,
            shell=True,  # noqa: S604
            text=True,
        )
    return subprocess.run(
        command,
        check=True,
        shell=True,  # noqa: S602
        capture_output=True,
        text=True,
    )


def oxford_join(words: list[str]) -> str:
    """Join a list of words with commas and an oxford comma.

    :param words: A list of words to join
    :return: A string of words joined with commas and an oxford comma
    """
    if not words:
        return ""
    if len(words) == 1:
        return words[0]
    if len(words) == 2:  # noqa: PLR2004
        return " and ".join(words)
    return ", ".join(words[:-1]) + ", and " + words[-1]


def opt_deps_to_files(dep_str: str) -> list[Path]:
    """Convert a string of optional dependencies to a list of files.

    :param dep_str: A string of optional dependencies
    :return: A list of files
    """
    deps = dep_str.split(",")
    files = []
    for dep in deps:
        _dep = dep.strip()
        variant1 = Path.cwd() / f"{_dep}-requirements.txt"
        if variant1.exists():
            files.append(variant1)
            continue
        variant2 = Path.cwd() / f"requirements-{_dep}.txt"
        if variant2.exists():
            files.append(variant2)
            continue
        msg = (
            f"Failed to find optional dependency file for '{_dep}'."
            f" Checked for '{variant1.name}' and '{variant2.name}'. Skipping."
        )
        logger.warning(msg)
    return files
