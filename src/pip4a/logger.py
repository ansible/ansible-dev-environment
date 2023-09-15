"""Produce pretty logs."""

from __future__ import annotations

import logging

from copy import copy


MAPPING = {
    "DEBUG": "30",  # grey
    "INFO": "94",  # bright cyan
    "WARNING": "93",  # bright yellow
    "ERROR": "31;1",  # bold red
    "CRITICAL": "91;1",  # bold bright red
}

PREFIX = "\033["
SUFFIX = "\033[0m"


class ColoredFormatter(logging.Formatter):
    """A colorful formatter."""

    def __init__(self: ColoredFormatter, pattern: str) -> None:
        """Initialize the formatter.

        Args:
            pattern: The log format
        """
        logging.Formatter.__init__(self, pattern)

    def format(  # noqa: A003
        self: ColoredFormatter,
        record: logging.LogRecord,
    ) -> str:
        """Format the log record.

        Args:
            record: The log record

        Returns:
            The formatted log record
        """
        colored_record = copy(record)
        levelname = colored_record.levelname
        seq = MAPPING.get(levelname, 37)  # default white
        colored_levelname = (
            f"{PREFIX}{seq}m{levelname.lower().capitalize() + ':':<9}{SUFFIX}"
        )
        colored_record.levelname = colored_levelname
        colored_msg = f"{PREFIX}{seq}m{record.msg}{SUFFIX}"
        colored_record.msg = colored_msg
        return logging.Formatter.format(self, colored_record)


class ExitOnExceptionHandler(logging.StreamHandler):  # type: ignore[type-arg]
    """Exit on exception handler."""

    def emit(self: ExitOnExceptionHandler, record: logging.LogRecord) -> None:
        """Emit the log record.

        Args:
            record: The log record

        Raises:
            SystemExit: If the log record is an error or critical
        """
        super().emit(record)
        if record.levelno == logging.CRITICAL:
            raise SystemExit(1)
