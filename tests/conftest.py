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

import shutil
import tempfile

from collections.abc import Generator
from pathlib import Path

import pytest

import ansible_dev_environment  # noqa: F401

from ansible_dev_environment.cli import Cli
from ansible_dev_environment.config import Config


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
            "ansible.utils",
            "ansible.scm",
            "ansible.posix",
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
