"""Utility functions."""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess

from typing import TYPE_CHECKING

import subprocess_tee


if TYPE_CHECKING:
    from pathlib import Path

    from .config import Config

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
        venv_cache_dir: The directory to look for manifests in.

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


def builder_introspect(config: Config) -> None:
    """Introspect a collection.

    Args:
        config: The configuration object.
    """
    command = (
        f"ansible-builder introspect {config.site_pkg_path}"
        f" --write-pip {config.discovered_python_reqs}"
        f" --write-bindep {config.discovered_bindep_reqs}"
        " --sanitize"
    )
    if hasattr(config.args, "collection_specifier"):
        opt_deps = re.match(r".*\[msg(.*)\]", config.args.collection_specifier)
        if opt_deps:
            dep_paths = opt_deps_to_files(
                collection_path=config.collection_path,
                dep_str=opt_deps.group(1),
            )
            for dep_path in dep_paths:
                command += f" --user-pip {dep_path}"
    msg = f"Writing discovered python requirements to: {config.discovered_python_reqs}"
    logger.debug(msg)
    msg = f"Writing discovered system requirements to: {config.discovered_bindep_reqs}"
    logger.debug(msg)
    try:
        subprocess_run(command=command, verbose=config.args.verbose)
    except subprocess.CalledProcessError as exc:
        err = f"Failed to discover requirements: {exc} {exc.stderr}"
        logger.critical(err)


def note(string: str) -> None:
    """Print a green note.

    Args:
        string: The string to print.
    """
    logger.debug(string)
    _note = f"NOTE: {string}"
    if os.environ.get("NOCOLOR"):
        print(_note)  # noqa: T201
    else:
        print(f"\033[92m{_note}\033[0m")  # noqa: T201


def hint(string: str) -> None:
    """Print a magenta hint.

    Args:
        string: The string to print.
    """
    logger.debug(string)
    _hint = f"HINT: {string}"
    if os.environ.get("NOCOLOR"):
        print(_hint)  # noqa: T201
    else:
        print(f"\033[95m{_hint}\033[0m")  # noqa: T201
