"""Utility functions."""

from __future__ import annotations

import itertools
import json
import logging
import os
import subprocess
import sys
import threading
import time

from dataclasses import dataclass
from typing import TYPE_CHECKING, Union

import subprocess_tee
import yaml


if TYPE_CHECKING:
    from pathlib import Path
    from types import TracebackType

    from .config import Config

from typing import Any


logger = logging.getLogger(__name__)


ScalarVal = Union[bool, str, float, int, None]
JSONVal = Union[ScalarVal, list["JSONVal"], dict[str, "JSONVal"]]


@dataclass
class TermFeatures:
    """Terminal features."""

    color: bool
    links: bool

    def any_enabled(self: TermFeatures) -> bool:
        """Return True if any features are enabled."""
        return any((self.color, self.links))


def term_link(uri: str, term_features: TermFeatures, label: str) -> str:
    """Return a link.

    Args:
        uri: The URI to link to
        term_features: The terminal features to enable
        label: The label to use for the link
    Returns:
        The link
    """
    if not term_features.links:
        return label

    parameters = ""

    # OSC 8 ; params ; URI ST <name> OSC 8 ;; ST
    escape_mask = "\x1b]8;{};{}\x1b\\{}\x1b]8;;\x1b\\"
    link_str = escape_mask.format(parameters, uri, label)
    if not term_features.color:
        return link_str
    return f"{Ansi.BLUE}{link_str}{Ansi.RESET}"


class Ansi:
    """ANSI escape codes."""

    BLUE = "\x1B[34m"
    BOLD = "\x1B[1m"
    CYAN = "\x1B[36m"
    GREEN = "\x1B[32m"
    ITALIC = "\x1B[3m"
    MAGENTA = "\x1B[35m"
    RED = "\x1B[31m"
    RESET = "\x1B[0m"
    REVERSED = "\x1B[7m"
    UNDERLINE = "\x1B[4m"
    WHITE = "\x1B[37m"
    YELLOW = "\x1B[33m"
    GREY = "\x1B[90m"


def subprocess_run(  # noqa: PLR0913
    command: str,
    verbose: int,
    msg: str,
    term_features: TermFeatures,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a subprocess command."""
    cmd = f"Running command: {command}"
    logger.debug(cmd)
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
    with Spinner(message=msg, term_features=term_features):
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
) -> dict[str, dict[str, JSONVal]]:
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
    work = "Persisting requirements to file system"
    try:
        subprocess_run(
            command=command,
            verbose=config.args.verbose,
            msg=work,
            term_features=config.term_features,
        )
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


def collections_meta(config: Config) -> dict[str, dict[str, Any]]:
    """Collect metadata about installed collections.

    Args:
        config: The configuration object.
    Returns:
        A dictionary of metadata about installed collections.
    """
    all_info_dirs = [
        entry
        for entry in config.site_pkg_collections_path.iterdir()
        if entry.name.endswith(".info")
    ]

    collections = {}
    for namespace_dir in config.site_pkg_collections_path.iterdir():
        if not namespace_dir.is_dir():
            continue

        for name_dir in namespace_dir.iterdir():
            if not name_dir.is_dir():
                continue
            some_info_dirs = [
                info_dir
                for info_dir in all_info_dirs
                if f"{namespace_dir.name}.{name_dir.name}" in info_dir.name
            ]
            file = None
            if some_info_dirs:
                file = some_info_dirs[0] / "GALAXY.yml"
                editable_location = ""

            elif (name_dir / "galaxy.yml").exists():
                file = name_dir / "galaxy.yml"
                editable_location = (
                    str(name_dir.resolve()) if name_dir.is_symlink() else ""
                )

            if file:
                with file.open() as info_file:
                    info = yaml.safe_load(info_file)
                    collections[f"{namespace_dir.name}.{name_dir.name}"] = {
                        "version": info.get("version", "unknown"),
                        "editable_location": editable_location,
                        "dependencies": info.get("dependencies", []),
                    }
            else:
                collections[f"{namespace_dir.name}.{name_dir.name}"] = {
                    "version": "unknown",
                    "editable_location": "",
                    "dependencies": [],
                }
    return collections


class Spinner:  # pylint: disable=too-many-instance-attributes
    """A spinner."""

    def __init__(
        self: Spinner,
        message: str,
        term_features: TermFeatures,
        delay: float = 0.1,
    ) -> None:
        """Initialize the spinner.

        Args:
            message: The message to display
            term_features: Terminal features
            delay: The delay between characters
        """
        self.spinner = itertools.cycle(["-", "/", "|", "\\"])
        self.delay = delay
        self.busy = False
        self.spinner_visible = False
        self._term_features = term_features
        self._screen_lock = threading.Lock()
        self._start_time: float | None = None
        self.thread: threading.Thread
        self.msg: str = message.rstrip(".").rstrip(":").rstrip()

    def write_next(self: Spinner) -> None:
        """Write the next char."""
        with self._screen_lock:
            if not self.spinner_visible:
                if self._term_features.color:
                    char = f"{Ansi.GREY}{next(self.spinner)}{Ansi.RESET}"
                else:
                    char = next(self.spinner)
                sys.stdout.write(char)
                self.spinner_visible = True
                sys.stdout.flush()

    def remove_spinner(
        self: Spinner,
        cleanup: bool = False,  # noqa: FBT001,FBT002
    ) -> None:
        """Remove the spinner.

        https://github.com/Tagar/stuff/blob/master/spinner.py

        Args:
            cleanup: Should we cleanup after the spinner
        """
        with self._screen_lock:
            if self.spinner_visible:
                sys.stdout.write("\b")
                self.spinner_visible = False
                if cleanup:
                    sys.stdout.write(" ")  # overwrite spinner with blank
                    sys.stdout.write("\r")  # move to next line
                    sys.stdout.write("\033[K")  # clear line
                sys.stdout.flush()

    def spinner_task(self: Spinner) -> None:
        """Spin the spinner."""
        while self.busy:
            self.write_next()
            time.sleep(self.delay)
            self.remove_spinner()

    def __enter__(self: Spinner) -> None:
        """Enter the context handler."""
        # set the start time
        self._start_time = time.time()
        if not self._term_features.any_enabled():
            return
        if self._term_features.color:
            sys.stdout.write(f"{Ansi.GREY}{self.msg}:{Ansi.RESET} ")
        else:
            sys.stdout.write(f"{self.msg}: ")
        # hide the cursor
        sys.stdout.write("\033[?25l")
        if self._term_features.any_enabled():
            self.busy = True
            self.thread = threading.Thread(target=self.spinner_task)
            self.thread.start()

    def __exit__(
        self: Spinner,
        typ: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Exit the context handler.

        Args:
            typ: The exception
            exc: The exception value
            tb: The traceback


        """
        # delay if less than n seconds has elapsed
        if not self._term_features.any_enabled():
            return
        min_show_time = 0.5
        if self._start_time:
            elapsed = time.time() - self._start_time
            if elapsed < min_show_time:
                time.sleep(min_show_time - elapsed)
        if self._term_features.any_enabled():
            self.busy = False
            self.remove_spinner(cleanup=True)
        else:
            sys.stdout.write("\r")
        # show the cursor
        sys.stdout.write("\033[?25h")
