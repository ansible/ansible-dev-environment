"""CLI entrypoint."""

from __future__ import annotations

import logging
import os
import site
import sys

from pathlib import Path
from typing import TYPE_CHECKING

from pip4a import subcommands

from .arg_parser import parse
from .config import Config
from .logger import ColoredFormatter, ExitOnExceptionHandler
from .utils import TermFeatures


if TYPE_CHECKING:
    from argparse import Namespace


class LogType:
    """A log type."""

    def __init__(self: LogType) -> None:
        """Initialize the log type."""
        self.errors = 0


class LogCount(logging.Handler):
    """A log counter."""

    def __init__(self: LogCount) -> None:
        """Initialize the log counter."""
        super().__init__()
        self.count = LogType()
        self.name = "counter"

    def emit(self: LogCount, record: logging.LogRecord) -> None:
        """Emit the log record.

        Args:
            record: The log record
        """
        if record.levelname == "ERROR":
            self.count.errors += 1


class Cli:
    """The Cli class."""

    def __init__(self: Cli) -> None:
        """Initialize the CLI and parse CLI args."""
        self.args: Namespace
        self.config: Config
        self.logger: logging.Logger

    def parse_args(self: Cli) -> None:
        """Parse the command line arguments."""
        self.args = parse()
        if hasattr(self.args, "requirement") and self.args.requirement:
            self.args.requirement = Path(self.args.requirement).expanduser().resolve()

    def init_logger(self: Cli) -> None:
        """Initialize the logger."""
        self.logger = logging.getLogger("pip4a")
        count = LogCount()
        self.logger.addHandler(count)

        ch = ExitOnExceptionHandler()
        cf = ColoredFormatter(
            "%(levelname)s %(message)s",
        )
        ch.setFormatter(cf)
        self.logger.addHandler(ch)

        max_verbosity = 3
        if self.args.verbose > max_verbosity:
            self.args.verbose = 3

        log_level = logging.ERROR - (self.args.verbose * 10)
        self.logger.setLevel(log_level)

    def args_sanity(self: Cli) -> None:
        """Perform some sanity checking on the args."""
        if (
            hasattr(self.args, "requirement")
            and self.args.requirement
            and not self.args.requirement.exists()
        ):
            err = f"Requirements file not found: {self.args.requirement}"
            self.logger.critical(err)

    def ensure_isolated(self: Cli) -> None:
        """Ensure the environment is isolated."""
        env_vars = os.environ
        errors = []
        if "ANSIBLE_COLLECTIONS_PATHS" in env_vars:
            err = "ANSIBLE_COLLECTIONS_PATHS is set"
            errors.append(err)
        if "ANSIBLE_COLLECTION_PATH" in env_vars:
            err = "ANSIBLE_COLLECTION_PATH is set"
            errors.append(err)

        home_coll = Path.home() / ".ansible/collections/ansible_collections"
        if home_coll.exists() and tuple(home_coll.iterdir()):
            err = f"Collections found in {home_coll}"
            errors.append(err)

        usr_coll = Path("/usr/share/ansible/collections")
        if usr_coll.exists() and tuple(usr_coll.iterdir()):
            err = f"Collections found in {usr_coll}"
            errors.append(err)

        if "VIRTUAL_ENV" not in env_vars and not self.args.venv:
            err = (
                "Unable to use user site packages directory:"
                f" {site.getusersitepackages()}, please activate or specify a virtual environment"
            )
            errors.append(err)

        if errors:
            err = (
                "The development environment is not isolated,"
                " please resolve the following errors:"
            )
            self.logger.error(err)
            for error in errors:
                err = f"- {error}"
                self.logger.error(err)
            err = "Exiting."
            self.logger.critical(err)

    def run(self: Cli) -> None:
        """Run the application."""
        logging.getLogger("pip4a")

        if not sys.stdout.isatty():
            term_features = TermFeatures(color=False, links=False)
        else:
            term_features = TermFeatures(
                color=False if os.environ.get("NO_COLOR") else not self.args.no_ansi,
                links=not self.args.no_ansi,
            )

        self.config = Config(args=self.args, term_features=term_features)
        self.config.init()

        subcommand_cls = getattr(subcommands, self.config.args.subcommand.capitalize())
        subcommand = subcommand_cls(config=self.config)
        subcommand.run()
        self._exit()

    def _exit(self: Cli) -> None:
        """Exit the application setting the return code."""
        logger = logging.getLogger("pip4a")
        status = 0
        for handler in logger.handlers:
            if handler.name == "counter":
                status = int(bool(handler.count.errors))  # type: ignore[attr-defined]
        sys.exit(status)


def main() -> None:
    """Entry point for ansible-creator CLI."""
    cli = Cli()
    cli.parse_args()
    cli.init_logger()
    cli.args_sanity()
    cli.ensure_isolated()
    cli.run()


if __name__ == "__main__":
    main()
