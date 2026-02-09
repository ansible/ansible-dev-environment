"""A collection abstraction."""

from __future__ import annotations

import re

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import yaml


if TYPE_CHECKING:
    from .config import Config
    from .output import Output


@dataclass
class Collection:  # pylint: disable=too-many-instance-attributes
    """A collection request specification.

    Attributes:
        config: The configuration object
        path: The collection path
        opt_deps: The optional dependencies
        local: A boolean indicating if the collection is local
        cnamespace: The collection namespace
        cname: The collection name
        csource: The collection source
        specifier: The collection specifier
        original: The original collection request
    """

    config: Config
    path: Path
    opt_deps: str
    local: bool
    cnamespace: str
    cname: str
    csource: list[str]
    specifier: str
    original: str

    @property
    def name(self) -> str:
        """Return the collection name."""
        return f"{self.cnamespace}.{self.cname}"

    @property
    def cache_dir(self) -> Path:
        """Return the collection cache directory."""
        collection_cache_dir = self.config.venv_cache_dir / self.name
        if not collection_cache_dir.exists():
            collection_cache_dir.mkdir()
        return collection_cache_dir

    @property
    def build_dir(self) -> Path:
        """Return the collection cache directory."""
        collection_build_dir = self.cache_dir / "build"
        if not collection_build_dir.exists():
            collection_build_dir.mkdir()
        return collection_build_dir

    @property
    def site_pkg_path(self) -> Path:
        """Return the site packages collection path.

        Returns:
            The site packages collection path
        """
        return self.config.site_pkg_collections_path / self.cnamespace / self.cname


def is_git_url(string: str) -> bool:
    """Check if string is a Git URL.

    Args:
        string: The string to check

    Returns:
        True if the string appears to be a Git URL, False otherwise
    """
    git_patterns = [
        r"^git\+https?://",  # git+https://github.com/user/repo.git
        r"^git\+ssh://",  # git+ssh://git@github.com/user/repo.git
        r"^https?://.*\.git$",  # https://github.com/user/repo.git
        r"^git@.*:.*\.git$",  # git@github.com:user/repo.git
    ]
    return any(re.match(pattern, string) for pattern in git_patterns)


def parse_git_url_collection_name(git_url: str) -> tuple[str, str]:
    """Extract collection namespace and name from Git URL.

    For now, we'll use a simple heuristic based on the repository name.
    In the future, this could be enhanced to clone and read galaxy.yml.

    Args:
        git_url: The Git URL to parse

    Returns:
        Tuple of (namespace, name) - may be empty strings if cannot be determined
    """
    # Extract repo name from various Git URL formats
    patterns = [
        r"github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?(?:\[.*\])?$",  # GitHub
        r"gitlab\.com[:/]([^/]+)/([^/]+?)(?:\.git)?(?:\[.*\])?$",  # GitLab
        r"[:/]([^/]+)/([^/]+?)(?:\.git)?(?:\[.*\])?$",  # Generic
    ]

    for pattern in patterns:
        match = re.search(pattern, git_url)
        if match:
            namespace = match.group(1).replace("-", "_")  # Convert hyphens to underscores
            name = match.group(2).replace("-", "_")
            # Remove common prefixes that might not be part of collection name
            if name.startswith("ansible_"):
                name = name[8:]  # Remove 'ansible_' prefix
            elif name.startswith("ansible."):
                name = name[8:]  # Remove 'ansible.' prefix
            return namespace, name

    # Fallback: use 'unknown' namespace and extract just the repo name
    repo_match = re.search(r"/([^/]+?)(?:\.git)?(?:\[.*\])?$", git_url)
    if repo_match:
        name = repo_match.group(1).replace("-", "_")
        if name.startswith(("ansible_", "ansible.")):
            name = name[8:]
        return "unknown", name

    return "", ""


def parse_collection_request(  # noqa: PLR0915
    string: str,
    config: Config,
    output: Output,
) -> Collection:
    """Parse a collection request str.

    Args:
        string: The collection request string
        config: The configuration object
        output: The output object

    Raises:
        SystemExit: If the collection request is invalid
    Returns:
        A collection object
    """
    # spec with dep, local or git
    if "[" in string and "]" in string:
        msg = f"Found optional dependencies in collection request: {string}"
        output.debug(msg)
        base_spec = string.split("[", maxsplit=1)[0]
        opt_deps = string.split("[")[1].split("]")[0]
        msg = f"Setting optional dependencies: {opt_deps}"
        output.debug(msg)

        # Check if it's a Git URL with optional dependencies
        if is_git_url(base_spec):
            msg = f"Found Git URL collection request with dependencies: {string}"
            output.debug(msg)
            cnamespace, cname = parse_git_url_collection_name(base_spec)
            msg = f"Parsed Git URL - namespace: {cnamespace}, name: {cname}"
            output.debug(msg)
            local = False
            msg = "Setting request as non-local (Git URL)"
            output.debug(msg)
            return Collection(
                config=config,
                path=Path(),
                opt_deps=opt_deps,
                local=local,
                cnamespace=cnamespace,
                cname=cname,
                csource=[base_spec],  # Store the Git URL
                specifier="",
                original=string,
            )
        # Local path with dependencies
        path = Path(base_spec).expanduser().resolve()
        if not path.exists():
            msg = "Provide an existing path to a collection when specifying optional dependencies."
            output.hint(msg)
            msg = f"Failed to find collection path: {path}"
            output.critical(msg)
        msg = f"Found local collection request with dependencies: {string}"
        output.debug(msg)
        msg = f"Setting collection path: {path}"
        output.debug(msg)
        local = True
        msg = "Setting request as local"
        output.debug(msg)
        collection = Collection(
            config=config,
            path=path,
            opt_deps=opt_deps,
            local=local,
            cnamespace="",
            cname="",
            csource=[],
            specifier="",
            original=string,
        )
        get_galaxy(collection=collection, output=output)
        return collection
    # Check if it's a Git URL without dependencies
    if is_git_url(string):
        msg = f"Found Git URL collection request without dependencies: {string}"
        output.debug(msg)
        cnamespace, cname = parse_git_url_collection_name(string)
        msg = f"Parsed Git URL - namespace: {cnamespace}, name: {cname}"
        output.debug(msg)
        local = False
        msg = "Setting request as non-local (Git URL)"
        output.debug(msg)
        return Collection(
            config=config,
            path=Path(),
            opt_deps="",
            local=local,
            cnamespace=cnamespace,
            cname=cname,
            csource=[string],  # Store the Git URL
            specifier="",
            original=string,
        )

    # spec without dep, local
    path = Path(string).expanduser().resolve()
    if path.exists():
        msg = f"Found local collection request without dependencies: {string}"
        output.debug(msg)
        msg = f"Setting collection path: {path}"
        output.debug(msg)
        msg = "Setting request as local"
        output.debug(msg)
        local = True
        collection = Collection(
            config=config,
            path=path,
            opt_deps="",
            local=local,
            cnamespace="",
            cname="",
            csource=[],
            specifier="",
            original=string,
        )
        get_galaxy(collection=collection, output=output)
        return collection
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
        msg = "Specify a valid collection name (ns.n) with an optional version specifier"
        output.hint(msg)
        msg = f"Failed to parse collection request: {string}"
        output.critical(msg)
        raise SystemExit(1)  # pragma: no cover # (critical is a sys.exit)
    msg = f"Found non-local collection request: {string}"
    output.debug(msg)

    cnamespace = matched.group("cnamespace")
    msg = f"Setting collection namespace: {cnamespace}"
    output.debug(msg)

    cname = matched.group("cname")
    msg = f"Setting collection name: {cname}"
    output.debug(msg)

    if matched.group("specifier"):
        specifier = matched.group("specifier")
        msg = f"Setting collection specifier: {specifier}"
        output.debug(msg)
    else:
        specifier = ""
        msg = "Setting collection specifier as empty"
        output.debug(msg)

    local = False
    msg = "Setting request as non-local"
    output.debug(msg)

    return Collection(
        config=config,
        path=Path(),
        opt_deps="",
        local=local,
        cnamespace=cnamespace,
        cname=cname,
        csource=[],
        specifier=specifier,
        original=string,
    )


def get_galaxy(collection: Collection, output: Output) -> None:
    """Retrieve the collection name from the galaxy.yml file.

    Args:
        collection: A collection object
        output: The output object
    Raises:
        SystemExit: If the collection name is not found
    """
    file_name = collection.path / "galaxy.yml"
    if not file_name.exists():
        err = f"Failed to find {file_name} in {collection.path}"
        output.critical(err)

    with file_name.open(encoding="utf-8") as fileh:
        try:
            yaml_file = yaml.safe_load(fileh)
        except yaml.YAMLError as exc:
            err = f"Failed to load yaml file: {exc}"
            output.critical(err)

    try:
        collection.cnamespace = yaml_file["namespace"]
        collection.cname = yaml_file["name"]
        msg = f"Found collection name: {collection.name} from {file_name}."
        output.debug(msg)
    except KeyError as exc:
        err = f"Failed to find collection name in {file_name}: {exc}"
        output.critical(err)
    else:
        return
    raise SystemExit(1)  # pragma: no cover # (critical is a sys.exit)
