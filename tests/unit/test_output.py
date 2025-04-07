"""Test the output module."""

from __future__ import annotations

import os

from typing import TYPE_CHECKING

import pytest

from ansible_dev_environment.output import Color, Level, Msg, Output, console_width
from ansible_dev_environment.utils import TermFeatures


if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize(
    argnames=("width", "expected"),
    argvalues=((79, 79), (131, 81), (133, 132)),
)
def test_console_width(width: int, expected: int, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test the console width function."""

    def mock_get_terminal_size(
        fallback: tuple[int, int] = (80, 24),  # noqa: ARG001
    ) -> tuple[int, int]:
        """Mock the get_terminal_size function.

        Args:
            fallback: Default terminal size.

        Returns:
            Mocked terminal size.
        """
        return os.terminal_size((width, 24))

    monkeypatch.setattr("shutil.get_terminal_size", mock_get_terminal_size)

    monkeypatch.delenv("COLUMNS", raising=False)

    assert console_width() == expected


@pytest.mark.parametrize(
    "params",
    (
        (Level.CRITICAL, Color.BRIGHT_RED),
        (Level.DEBUG, Color.GREY),
        (Level.ERROR, Color.RED),
        (Level.HINT, Color.CYAN),
        (Level.INFO, Color.MAGENTA),
        (Level.NOTE, Color.GREEN),
        (Level.WARNING, Color.YELLOW),
    ),
    ids=("critical", "debug", "error", "hint", "info", "note", "warning"),
)
def test_color_mapping(params: tuple[Level, Color]) -> None:
    """Test the color mapping for Msg in the output module.

    Args:
        params: Tuple of Level and Color.
    """
    assert Msg(message="", prefix=params[0]).color == str(params[1])


@pytest.mark.parametrize("level", ("info", "warning", "error", "debug", "critical", "hint", "note"))
def test_console_output(level: str, capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    """Test the console output function.

    Args:
        level: Log level.
        capsys: Pytest fixture.
        tmp_path: Pytest fixture
    """
    output = Output(
        log_file=str(tmp_path / "test.log"),
        log_level="debug",
        log_append="false",
        term_features=TermFeatures(color=True, links=True),
        verbosity=3,
    )
    message = f"{level} message"
    msg = Msg(message=message, prefix=getattr(Level, level.upper()))
    if level == "critical":
        with pytest.raises(SystemExit):
            getattr(output, level)(message)
    else:
        getattr(output, level)(message)
    captured = capsys.readouterr()
    standard_x = captured.err if level in ("critical", "error") else captured.out
    assert standard_x.startswith(msg.color)
    assert standard_x.endswith(Color.END + "\n")
    assert level.capitalize() in standard_x
    assert message in standard_x


def test_output_log_exists(tmp_path: Path) -> None:
    """Test the log file is reinitialized if append is false.

    Args:
        tmp_path: Pytest fixture.
    """
    log_file = tmp_path / "test.log"
    log_file.write_text("test")
    pre_stat = log_file.stat()
    Output(
        log_file=str(log_file),
        log_level="debug",
        log_append="false",
        term_features=TermFeatures(color=True, links=True),
        verbosity=3,
    )
    post_stat = log_file.stat()
    assert pre_stat.st_size > 0
    assert post_stat.st_size != pre_stat.st_size
    assert post_stat.st_size == 0
