"""Global conftest.py for pytest.

The root package import below happens before the pytest workers are forked, so it
picked up by the initial coverage process for a source match.

Without it, coverage reports the following false positive error:

CoverageWarning: No data was collected. (no-data-collected)

This works in conjunction with the coverage source_pkg set to the package such that
a `coverage run --debug trace` shows the source package and file match.

<...>
Imported source package 'ansible_dev_environment' as '/**/src/<package>/__init__.py'
<...>
Tracing '/**/src/<package>/__init__.py'
"""
from __future__ import annotations

import json
import os
import shutil
import tarfile
import tempfile
import warnings

from collections.abc import Generator
from pathlib import Path
from urllib.request import HTTPError, urlopen

import pytest
import yaml

import ansible_dev_environment  # noqa: F401

from ansible_dev_environment.cli import Cli
from ansible_dev_environment.config import Config


GALAXY_CACHE = Path(__file__).parent.parent / ".cache" / ".galaxy_cache"
REQS_FILE_NAME = "requirements.yml"


@pytest.fixture()
def galaxy_cache() -> Path:
    """Return the galaxy cache directory.

    Returns:
        The galaxy cache directory.
    """
    return GALAXY_CACHE


def check_download_collection(name: str, dest: Path) -> None:
    """Download a collection if necessary.

    Args:
        name: The collection name.
        dest: The destination directory.
    """
    namespace, name = name.split(".")
    base_url = "https://galaxy.ansible.com/api/v3/plugin/ansible/content/published/collections"

    url = f"{base_url}/index/{namespace}/{name}/versions/?is_highest=true"
    try:
        with urlopen(url) as response:  # noqa: S310
            body = response.read()
    except HTTPError:
        err = f"Failed to check collection version: {name}"
        pytest.fail(err)
    with urlopen(url) as response:  # noqa: S310
        body = response.read()
    json_response = json.loads(body)
    version = json_response["data"][0]["version"]
    file_name = f"{namespace}-{name}-{version}.tar.gz"
    file_path = dest / file_name
    if file_path.exists():
        return
    for found_file in dest.glob(f"{namespace}-{name}-*"):
        found_file.unlink()
    url = f"{base_url}/artifacts/{file_name}"
    warnings.warn(f"Downloading collection: {file_name}", stacklevel=0)
    try:
        with urlopen(url) as response, file_path.open(mode="wb") as file:  # noqa: S310
            file.write(response.read())
    except HTTPError:
        err = f"Failed to download collection: {name}"
        pytest.fail(err)


def pytest_sessionstart(session: pytest.Session) -> None:
    """Start the server.

    Args:
        session: The pytest session.
    """
    if session.config.option.collectonly:
        return

    if os.environ.get("PYTEST_XDIST_WORKER"):
        return

    if not GALAXY_CACHE.exists():
        GALAXY_CACHE.mkdir(parents=True, exist_ok=True)

    for collection in ("ansible.utils", "ansible.scm", "ansible.posix"):
        check_download_collection(collection, GALAXY_CACHE)

    reqs: dict[str, list[dict[str, str]]] = {"collections": []}

    for found_file in GALAXY_CACHE.glob("*.tar.gz"):
        reqs["collections"].append({"name": str(found_file)})

    requirements = GALAXY_CACHE / REQS_FILE_NAME
    requirements.write_text(yaml.dump(reqs))


@pytest.fixture(name="monkey_session", scope="session")
def fixture_monkey_session() -> Generator[pytest.MonkeyPatch, None, None]:
    """Session scoped monkeypatch fixture.

    Yields:
        pytest.MonkeyPatch: The monkeypatch fixture.
    """
    monkey_patch = pytest.MonkeyPatch()
    yield monkey_patch
    monkey_patch.undo()


@pytest.fixture(name="session_dir", scope="session")
def fixture_session_dir() -> Generator[Path, None, None]:
    """A session scoped temporary directory.

    Yields:
        Path: Temporary directory.
    """
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture()
def installable_local_collection(tmp_path: Path) -> Path:
    """Provide a local collection that can be installed.

    Args:
        tmp_path: Temporary directory.

    Returns:
        The path to the local collection.
    """
    src_dir = tmp_path / "ansible.posix"
    tar_file_path = next(GALAXY_CACHE.glob("ansible-posix*"))
    with tarfile.open(tar_file_path, "r") as tar:
        try:
            tar.extractall(src_dir, filter="data")
        except TypeError:
            tar.extractall(src_dir)  # noqa: S202
    galaxy_contents = {
        "authors": "author",
        "name": "posix",
        "namespace": "ansible",
        "readme": "readme",
        "version": "1.0.0",
    }
    yaml.dump(galaxy_contents, (src_dir / "galaxy.yml").open("w"))
    return src_dir


@pytest.fixture(scope="session")
def session_venv(session_dir: Path, monkey_session: pytest.MonkeyPatch) -> Config:
    """Create a temporary venv for the session.

    Add some common collections to the venv.

    Since this is a session level fixture, care should be taken to not manipulate it
    or the resulting config in a way that would affect other tests.

    Args:
        session_dir: Temporary directory.
        monkey_session: Pytest monkeypatch fixture.

    Returns:
        The configuration object for the venv.
    """
    venv_path = session_dir / "venv"
    monkey_session.setattr(
        "sys.argv",
        [
            "ade",
            "install",
            "-r",
            str(GALAXY_CACHE / REQS_FILE_NAME),
            "--venv",
            str(venv_path),
            "--ll",
            "debug",
            "--la",
            "true",
            "--lf",
            str(session_dir / "ade.log"),
            "-vvv",
        ],
    )
    cli = Cli()
    cli.parse_args()
    cli.init_output()
    cli.args_sanity()
    cli.ensure_isolated()
    with pytest.raises(SystemExit):
        cli.run()
    return cli.config


@pytest.fixture()
def function_venv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Config:
    """Create a temporary venv for the session.

    Add some common collections to the venv.

    Since this is a session level fixture, care should be taken to not manipulate it
    or the resulting config in a way that would affect other tests.

    Args:
        tmp_path: Temporary directory.
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        The configuration object for the venv.
    """
    venv_path = tmp_path / "venv"
    monkeypatch.setattr(
        "sys.argv",
        [
            "ade",
            "install",
            "-r",
            str(GALAXY_CACHE / REQS_FILE_NAME),
            "--venv",
            str(venv_path),
            "--ll",
            "debug",
            "--la",
            "true",
            "--lf",
            str(tmp_path / "ade.log"),
            "-vvv",
        ],
    )
    cli = Cli()
    cli.parse_args()
    cli.init_output()
    cli.args_sanity()
    cli.ensure_isolated()
    with pytest.raises(SystemExit):
        cli.run()
    return cli.config
