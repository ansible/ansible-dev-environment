"""Utility functions."""

from __future__ import annotations

import logging
import subprocess

from typing import TYPE_CHECKING

import subprocess_tee


if TYPE_CHECKING:
    from pathlib import Path


logger = logging.getLogger(__name__)


def subprocess_run(
    command: str,
    verbose: bool,  # noqa: FBT001
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a subprocess command."""
    msg = f"Running command: {command}"
    logger.debug(msg)
    if verbose:
        return subprocess_tee.run(
            command,
            check=True,
            cwd=cwd,
            shell=True,  # noqa: S604
            text=True,
        )
    return subprocess.run(
        command,
        check=True,
        cwd=cwd,
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


def opt_deps_to_files(collection_path: Path, dep_str: str) -> list[Path]:
    """Convert a string of optional dependencies to a list of files.

    :param dep_str: A string of optional dependencies
    :return: A list of files
    """
    deps = dep_str.split(",")
    files = []
    for dep in deps:
        _dep = dep.strip()
        variant1 = collection_path / f"{_dep}-requirements.txt"
        if variant1.exists():
            files.append(variant1)
            continue
        variant2 = collection_path / f"requirements-{_dep}.txt"
        if variant2.exists():
            files.append(variant2)
            continue
        msg = (
            f"Failed to find optional dependency file for '{_dep}'."
            f" Checked for '{variant1.name}' and '{variant2.name}'. Skipping."
        )
        logger.warning(msg)
    return files
