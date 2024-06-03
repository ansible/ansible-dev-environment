"""Fixtures for unit tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from ansible_dev_environment.output import Output
from ansible_dev_environment.utils import TermFeatures


if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture()
def output(tmp_path: Path) -> Output:
    """Create an Output class object as fixture.

    Args:
        tmp_path: Temporary directory.

    Returns:
        Output: Output class object.
    """
    return Output(
        log_file=str(tmp_path) + "ansible-creator.log",
        log_level="notset",
        log_append="false",
        term_features=TermFeatures(color=False, links=False),
        verbosity=0,
    )


@pytest.fixture(name="_wide_console")
def _wide_console(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fixture to set the terminal width to 1000 to prevent wrapping.

    Args:
        monkeypatch: Pytest fixture.
    """

    def _console_width() -> int:
        """Return a large console width.

        Returns:
            int: Console width.
        """
        return 1000

    monkeypatch.setattr(
        "ansible_dev_environment.output.console_width",
        _console_width,
    )
