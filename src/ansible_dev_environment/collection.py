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
    # spec with dep, local
    if "[" in string and "]" in string:
        msg = f"Found optional dependencies in collection request: {string}"
        output.debug(msg)
        path = Path(string.split("[")[0]).expanduser().resolve()
        if not path.exists():
            msg = "Provide an existing path to a collection when specifying optional dependencies."
            output.hint(msg)
            msg = f"Failed to find collection path: {path}"
            output.critical(msg)
        msg = f"Found local collection request with dependencies: {string}"
        output.debug(msg)
        msg = f"Setting collection path: {path}"
        output.debug(msg)
        opt_deps = string.split("[")[1].split("]")[0]
        msg = f"Setting optional dependencies: {opt_deps}"
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
