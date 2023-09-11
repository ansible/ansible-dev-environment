"""Utility functions."""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys

from dataclasses import dataclass
from typing import TYPE_CHECKING

import subprocess_tee
import yaml


if TYPE_CHECKING:
    from .config import Config

from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)


def subprocess_run(
    command: str,
    verbose: int,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a subprocess command."""
    msg = f"Running command: {command}"
    logger.debug(msg)
    log_level = logging.ERROR - (verbose * 10)
    if log_level == logging.DEBUG:
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
    words.sort()
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
        logger.error(msg)
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
    if (
        hasattr(config.args, "collection_specifier")
        and hasattr(config, "collection")
        and config.collection.opt_deps
        and config.collection.path
    ):
        dep_paths = opt_deps_to_files(
            collection_path=config.collection.path,
            dep_str=config.collection.opt_deps,
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
    _note = f"{'Note:':<9} {string}"
    if os.environ.get("NOCOLOR"):
        print(_note)  # noqa: T201
    else:
        print(f"\033[92m{_note}\033[0m")  # noqa: T201


def hint(string: str) -> None:
    """Print a magenta hint.

    Args:
        string: The string to print.
    """
    _hint = f"{'Hint:':<9} {string}"
    if os.environ.get("NOCOLOR"):
        print(_hint)  # noqa: T201
    else:
        print(f"\033[95m{_hint}\033[0m")  # noqa: T201


@dataclass
class CollectionSpec:
    """A collection request specification."""

    path: Path | None = None
    opt_deps: str | None = None
    local: bool | None = None
    cnamespace: str | None = None
    cname: str | None = None
    specifier: str | None = None

    @property
    def name(self: CollectionSpec) -> str:
        """Return the collection name."""
        return f"{self.cnamespace}.{self.cname}"


def parse_collection_request(string: str) -> CollectionSpec:  # noqa: PLR0915
    """Parse a collection request str."""
    collection_spec = CollectionSpec()
    # spec with dep, local
    if "[" in string and "]" in string:
        msg = f"Found optional dependencies in collection request: {string}"
        logger.debug(msg)
        path = Path(string.split("[")[0]).expanduser().resolve()
        if not path.exists():
            msg = "Provide an existing path to a collection when specifying optional dependencies."
            hint(msg)
            msg = f"Failed to find collection path: {path}"
            logger.critical(msg)
        msg = f"Found local collection request with dependencies: {string}"
        logger.debug(msg)
        collection_spec.path = path
        msg = f"Setting collection path: {collection_spec.path}"
        collection_spec.opt_deps = string.split("[")[1].split("]")[0]
        msg = f"Setting optional dependencies: {collection_spec.opt_deps}"
        logger.debug(msg)
        collection_spec.local = True
        msg = "Setting request as local"
        logger.debug(msg)
        return collection_spec
    # spec without dep, local
    path = Path(string).expanduser().resolve()
    if path.exists():
        msg = f"Found local collection request without dependencies: {string}"
        logger.debug(msg)
        msg = f"Setting collection path: {path}"
        logger.debug(msg)
        collection_spec.path = path
        msg = "Setting request as local"
        logger.debug(msg)
        collection_spec.local = True
        return collection_spec
    non_local_re = re.compile(
        r"""
        (?P<cnamespace>[A-Za-z0-9]+)    # collection name
        \.                              # dot
        (?P<cname>[A-Za-z0-9]+)         # collection name
        (?P<specifier>[^A-Za-z0-9].*)?   # optional specifier
        """,
        re.VERBOSE,
    )
    matched = non_local_re.match(string)
    if not matched:
        msg = (
            "Specify a valid collection name (ns.n) with an optional version specifier"
        )
        hint(msg)
        msg = f"Failed to parse collection request: {string}"
        logger.critical(msg)
        sys.exit(1)
    msg = f"Found non-local collection request: {string}"
    logger.debug(msg)

    collection_spec.cnamespace = matched.group("cnamespace")
    msg = f"Setting collection namespace: {collection_spec.cnamespace}"
    logger.debug(msg)

    collection_spec.cname = matched.group("cname")
    msg = f"Setting collection name: {collection_spec.cname}"
    logger.debug(msg)

    if matched.group("specifier"):
        collection_spec.specifier = matched.group("specifier")
        msg = f"Setting collection specifier: {collection_spec.specifier}"
        logger.debug(msg)

    collection_spec.local = False
    msg = "Setting request as non-local"
    logger.debug(msg)

    return collection_spec


def collections_from_requirements(file: Path) -> list[dict[str, str]]:
    """Build a list of collections from a requirements file."""
    collections = []
    try:
        with file.open() as requirements_file:
            requirements = yaml.safe_load(requirements_file)
    except yaml.YAMLError as exc:
        err = f"Failed to load yaml file: {exc}"
        logger.critical(err)

    for requirement in requirements["collections"]:
        if isinstance(requirement, str):
            collections.append({"name": requirement})
        elif isinstance(requirement, dict):
            collections.append(requirement)
    return collections
