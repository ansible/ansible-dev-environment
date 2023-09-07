"""Utility functions."""

from __future__ import annotations

import json
import logging
import subprocess

from typing import TYPE_CHECKING

import subprocess_tee


if TYPE_CHECKING:
    from pathlib import Path

from typing import Any


logger = logging.getLogger(__name__)


def subprocess_run(
    command: str,
    verbose: bool,  # noqa: FBT001
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a subprocess command."""
    msg = f"Running command: {command}"
    logger.debug(msg)
    if verbose:
        return subprocess_tee.run(
            command,
            check=True,
            cwd=cwd,
            env=env,
            shell=True,  # noqa: S604
            text=True,
        )
    return subprocess.run(
        command,
        check=True,
        cwd=cwd,
        env=env,
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


def sort_dict(item: dict[str, Any]) -> dict[str, Any]:
    """Recursively sort a dictionary.

    Args:
        item: The dictionary to sort.

    Returns:
        The sorted dictionary.
    """
    return {
        k: sort_dict(v) if isinstance(v, dict) else v for k, v in sorted(item.items())
    }


def collect_manifests(  # noqa: C901
    target: Path,
    venv_cache_dir: Path,
) -> dict[str, Any]:
    # pylint: disable=too-many-locals
    """Collect manifests from a target directory.

    Args:
        target: The target directory to collect manifests from.

    Returns:
        A dictionary of manifests.
    """
    collections = {}
    for namespace_dir in target.iterdir():
        if not namespace_dir.is_dir():
            continue

        for name_dir in namespace_dir.iterdir():
            if not name_dir.is_dir():
                continue
            manifest = name_dir / "MANIFEST.json"
            if not manifest.exists():
                manifest = (
                    venv_cache_dir
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

    return sort_dict(collections)
