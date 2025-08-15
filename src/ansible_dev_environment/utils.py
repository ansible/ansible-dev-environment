"""Utility functions."""

from __future__ import annotations

import itertools
import json
import logging
import re
import subprocess
import sys
import threading
import time

from dataclasses import dataclass
from typing import TYPE_CHECKING

import subprocess_tee
import yaml


if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path
    from types import TracebackType

    from .collection import Collection
    from .config import Config
    from .output import Output


from typing import Any


logger = logging.getLogger(__name__)


ScalarVal = bool | str | float | int | None
JSONVal = ScalarVal | list["JSONVal"] | dict[str, "JSONVal"]


@dataclass
class TermFeatures:
    """Terminal features.

    Attributes:
        color: A boolean indicating if color is enabled
        links: A boolean indicating if links are enabled
    """

    color: bool
    links: bool

    def any_enabled(self) -> bool:
        """Return True if any features are enabled.

        Returns:
            True if any features are enabled
        """
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
    """ANSI escape codes.

    Attributes:
        BLUE: The blue color
        BOLD: The bold style
        CYAN: The cyan color
        GREEN: The green color
        ITALIC: The italic style
        MAGENTA: The magenta color
        RED: The red color
        RESET: The reset style
        REVERSED: The reversed style
        UNDERLINE: The underline style
        WHITE: The white color
        YELLOW: The yellow color
        GREY: The grey color
    """

    BLUE = "\x1b[34m"
    BOLD = "\x1b[1m"
    CYAN = "\x1b[36m"
    GREEN = "\x1b[32m"
    ITALIC = "\x1b[3m"
    MAGENTA = "\x1b[35m"
    RED = "\x1b[31m"
    RESET = "\x1b[0m"
    REVERSED = "\x1b[7m"
    UNDERLINE = "\x1b[4m"
    WHITE = "\x1b[37m"
    YELLOW = "\x1b[33m"
    GREY = "\x1b[90m"


def subprocess_run(  # pylint: disable=too-many-positional-arguments
    command: str,
    verbose: int,
    msg: str,
    output: Output,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a subprocess command.

    Args:
        command: The command to run
        verbose: The verbosity level
        msg: The message to display
        output: The output object
        cwd: The current working directory
        env: The environment variables
    Returns:
        The completed process
    """
    cmd = f"Running command: {command}"
    output.debug(cmd)
    log_level = logging.ERROR - (verbose * 10)
    if log_level == logging.DEBUG:
        return subprocess_tee.run(  # noqa: S604
            command,
            check=True,
            cwd=cwd,
            env=env,
            shell=True,
            text=True,
        )
    with Spinner(message=msg, term_features=output.term_features):
        return subprocess.run(  # noqa: S602
            command,
            check=True,
            cwd=cwd,
            env=env,
            shell=True,
            capture_output=True,
            text=True,
        )


def oxford_join(words: Sequence[str | Path]) -> str:
    """Join a list of words with commas and an oxford comma.

    Args:
        words: A list of words to join
    Returns:
        A string of words joined with commas and an oxford comma
    """
    _words = sorted([str(word) for word in words])
    match _words:
        case [word]:
            return word
        case [word_one, word_two]:
            return f"{word_one} and {word_two}"
        case [*first_words, last_word]:
            return f"{', '.join(first_words)}, and {last_word}"
        case _:
            return ""


def opt_deps_to_files(collection: Collection, output: Output) -> list[Path]:
    """Convert a string of optional dependencies to a list of files.

    Args:
        collection: The collection object
        output: The output object
    Returns:
        A list of paths
    """
    if not collection.opt_deps:
        msg = "No optional dependencies specified."
        output.debug(msg)
        return []

    deps = collection.opt_deps.split(",")
    files = []
    for dep in deps:
        _dep = dep.strip()
        variant1 = collection.path / f"{_dep}-requirements.txt"
        if variant1.exists():
            files.append(variant1)
            continue
        variant2 = collection.path / f"requirements-{_dep}.txt"
        if variant2.exists():
            files.append(variant2)
            continue
        msg = (
            f"Failed to find optional dependency file for '{_dep}'."
            f" Checked for '{variant1.name}' and '{variant2.name}'. Skipping."
        )
        output.error(msg)
    count = len(files)
    msg = f"Found {count} optional dependency file{'s' * (count > 1)}. {oxford_join(files)}"
    output.debug(msg)
    return files


def sort_dict(item: dict[str, Any]) -> dict[str, Any]:
    """Recursively sort a dictionary.

    Args:
        item: The dictionary to sort.

    Returns:
        The sorted dictionary.
    """
    return {k: sort_dict(v) if isinstance(v, dict) else v for k, v in sorted(item.items())}


def collect_manifests(  # noqa: C901
    target: Path,
    venv_cache_dir: Path,
) -> dict[str, dict[str, JSONVal]]:
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
                    venv_cache_dir / f"{namespace_dir.name}.{name_dir.name}" / "MANIFEST.json"
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


def builder_introspect(
    config: Config,
    output: Output,
    opt_dep_paths: list[Path] | None = None,
) -> None:
    """Introspect a collection.

    Use the sys executable to run builder, since it is a direct dependency
    it should be accessible to the current interpreter.

    Args:
        config: The configuration object.
        output: The output object.
        opt_dep_paths: A list of optional dependency paths.
    """
    command = (
        f"{sys.executable} -m ansible_builder introspect {config.site_pkg_path}"
        f" --write-pip {config.discovered_python_reqs}"
        f" --write-bindep {config.discovered_bindep_reqs}"
        " --sanitize"
    )
    for opt_dep_path in opt_dep_paths or []:
        command += f" --user-pip {opt_dep_path}"
    msg = f"Writing discovered python requirements to: {config.discovered_python_reqs}"
    output.debug(msg)
    msg = f"Writing discovered system requirements to: {config.discovered_bindep_reqs}"
    output.debug(msg)
    work = "Persisting requirements to file system"
    try:
        subprocess_run(
            command=command,
            verbose=config.args.verbose,
            msg=work,
            output=output,
        )
    except subprocess.CalledProcessError as exc:
        err = f"Failed to discover requirements: {exc} {exc.stderr}"
        output.critical(err)

    if not config.discovered_python_reqs.exists():
        config.discovered_python_reqs.touch()

    if not config.discovered_bindep_reqs.exists():
        config.discovered_bindep_reqs.touch()


def collections_from_requirements(file: Path) -> list[dict[str, str]]:
    """Build a list of collections from a requirements file.

    Args:
        file: The requirements file
    Returns:
        A list of collections
    """
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
            editable_location = ""
            if some_info_dirs:
                file = some_info_dirs[0] / "GALAXY.yml"
                editable_location = ""

            elif (name_dir / "galaxy.yml").exists():
                file = name_dir / "galaxy.yml"
                editable_location = str(name_dir.resolve()) if name_dir.is_symlink() else ""

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
        self,
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
        self._spinner = itertools.cycle(("|", "/", "-", "\\", "|", "/", "-"))
        self.delay = delay
        self.busy = False
        self.spinner_visible = False
        self._term_features = term_features
        self._screen_lock = threading.Lock()
        self._start_time: float | None = None
        self.thread: threading.Thread
        self.msg: str = message.rstrip(".").rstrip(":").rstrip()

    def write_next(self) -> None:
        """Write the next char."""
        with self._screen_lock:
            if not self.spinner_visible:
                if self._term_features.color:
                    char = f"{Ansi.GREY}{next(self._spinner)}{Ansi.RESET}"
                else:
                    char = next(self._spinner)
                sys.stdout.write(char)
                self.spinner_visible = True
                sys.stdout.flush()

    def remove_spinner(
        self,
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

    def spinner_task(self) -> None:
        """Spin the spinner."""
        while self.busy:
            self.write_next()
            time.sleep(self.delay)
            self.remove_spinner()

    def __enter__(self) -> None:
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
        self,
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


def str_to_bool(value: str) -> bool | None:
    """Converts a string to a boolean based on common truthy and falsy values.

    Args:
        value: The string to convert.

    Returns:
        True for truthy values, False for falsy values, None for invalid values.
    """
    truthy_values = {"true", "1", "yes", "y", "on"}
    falsy_values = {"false", "0", "no", "n", "off"}

    value_lower = value.strip().lower()

    if value_lower in truthy_values:
        return True
    if value_lower in falsy_values:
        return False
    return None


def get_dependency_constraint(
    package_name: str,
    dependency_name: str,
    pip_command: str = "pip",
    timeout: int = 30,
) -> str | None:
    """Get the version constraint for a dependency of a package.

    Uses pip's --dry-run functionality to inspect package dependencies without
    installing anything. Parses the output to find version constraints.

    Args:
        package_name: The package to check dependencies for (e.g., "ansible-dev-tools")
        dependency_name: The dependency to find constraints for (e.g., "ansible-core")
        pip_command: The pip command to use (e.g., "pip", "uv pip")
        timeout: Timeout in seconds for the pip command

    Returns:
        The version constraint string (e.g., ">=2.16.0") or None if not found.

    Examples:
        >>> get_dependency_constraint("ansible-dev-tools", "ansible-core")
        ">=2.16.0"

        >>> get_dependency_constraint("pytest", "pluggy")
        ">=1.5.0"

        >>> get_dependency_constraint("nonexistent-package", "anything")
        None
    """
    try:
        # Use --dry-run to avoid installation (removed --quiet to see dependency info)
        command = f"{pip_command} install --dry-run {package_name}"

        result = subprocess.run(  # noqa: S602
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )

        if result.returncode != 0:
            return None

        # Multiple patterns to catch different constraint formats
        patterns = [
            # Standard format: "package>=1.2.3" (no space between name and constraint)
            rf"{re.escape(dependency_name)}([><=!~]+[\d.]+(?:\.\*)?)",
            # Standard format with space: "package >=1.2.3"
            rf"{re.escape(dependency_name)}\s+([><=!~]+[\d.]+(?:\.\*)?)",
            # With parentheses: "(package>=1.2.3)"
            rf"\(\s*{re.escape(dependency_name)}([><=!~]+[\d.]+(?:\.\*)?)\s*\)",
            # From requirements: "Requirement already satisfied: package>=1.2.3"
            rf"Requirement.*{re.escape(dependency_name)}([><=!~]+[\d.]+(?:\.\*)?)",
            # In dependency list: "package (>=1.2.3)"
            rf"{re.escape(dependency_name)}\s*\(\s*([><=!~]+[\d.]+(?:\.\*)?)\s*\)",
        ]

        # Search through both stdout and stderr as pip may output to either
        combined_output = result.stdout + result.stderr

        for pattern in patterns:
            match = re.search(pattern, combined_output, re.IGNORECASE)
            if match:
                return match.group(1)

    except subprocess.TimeoutExpired:
        # Timeout occurred, return None as documented
        pass
    except Exception:  # noqa: BLE001, S110
        # Any other error (network, parsing, etc.), return None gracefully as documented
        pass

    return None
