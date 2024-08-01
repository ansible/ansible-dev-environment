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

import os
import shutil
import subprocess
import tempfile
import warnings

from collections.abc import Generator
from datetime import datetime, timedelta
from pathlib import Path

import pytest
import yaml

import ansible_dev_environment  # noqa: F401

from ansible_dev_environment.cli import Cli
from ansible_dev_environment.config import Config


TESTING_CACHE = Path(__file__).parent.parent / ".cache" / ".galaxy_cache"


def pytest_sessionstart(session: pytest.Session) -> None:
    """Start the server.

    Args:
        session: The pytest session.
    """
    if session.config.option.collectonly:
        return

    if os.environ.get("PYTEST_XDIST_WORKER"):
        return

    if not TESTING_CACHE.exists():
        TESTING_CACHE.mkdir(parents=True, exist_ok=True)

    warnings.warn(f"Checking the galaxy cache: {TESTING_CACHE}", stacklevel=0)
    update_needed = not any(TESTING_CACHE.iterdir())
    warnings.warn(f"Update needed: {update_needed}", stacklevel=0)
    tz = datetime.now().astimezone().tzinfo
    one_week_ago = datetime.now(tz) - timedelta(weeks=1)

    if not update_needed:
        for file in TESTING_CACHE.glob("*"):
            file_creation = datetime.fromtimestamp(file.stat().st_mtime, tz=tz)
            warnings.warn(f"File: {file.name}, created: {file_creation}", stacklevel=0)
            if file_creation < one_week_ago:
                update_needed = True
                break

    if not update_needed:
        warnings.warn("Galaxy cache is up to date.", stacklevel=0)
        return

    warnings.warn("Updating the galaxy cache.", stacklevel=0)
    shutil.rmtree(TESTING_CACHE, ignore_errors=True)
    TESTING_CACHE.mkdir(parents=True, exist_ok=True)

    command = (
        "ansible-galaxy collection download"
        f" ansible.utils ansible.scm ansible.posix -p {TESTING_CACHE}/ -vvv"
    )
    warnings.warn(f"Running: {command}", stacklevel=0)
    subprocess.run(command, shell=True, check=True)

    files = ",".join(str(f.name) for f in list(TESTING_CACHE.glob("*")))
    warnings.warn(f"Galaxy cache updated, contains: {files}", stacklevel=0)

    requirements = TESTING_CACHE / "requirements.yml"
    contents = yaml.load(requirements.read_text(), Loader=yaml.SafeLoader)
    for collection in contents["collections"]:
        collection["name"] = f"file://{TESTING_CACHE / collection['name']}"
    requirements.write_text(yaml.dump(contents))


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
            str(TESTING_CACHE / "requirements.yml"),
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
