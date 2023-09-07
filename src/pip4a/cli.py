"""CLI entrypoint."""

from __future__ import annotations

import logging
import os
import site
import sys

from pathlib import Path
from typing import TYPE_CHECKING

from .arg_parser import parse
from .checker import Checker
from .config import Config
from .inspector import Inspector
from .installer import Installer
from .lister import Lister
from .logger import ColoredFormatter, ExitOnExceptionHandler
from .uninstaller import UnInstaller


if TYPE_CHECKING:
    from argparse import Namespace


class Cli:
    """The Cli class."""

    def __init__(self: Cli) -> None:
        """Initialize the CLI and parse CLI args."""
        self.args: Namespace
        self.config: Config

    def parse_args(self: Cli) -> None:
        """Parse the command line arguments."""
        self.args = parse()

    def init_logger(self: Cli) -> None:
        """Initialize the logger."""
        logger = logging.getLogger("pip4a")
        ch = ExitOnExceptionHandler()
        ch.setLevel(logging.DEBUG)
        cf = ColoredFormatter(
            "%(levelname)s %(message)s",
        )
        ch.setFormatter(cf)
        logger.addHandler(ch)

        if self.args.verbose:
            logger.setLevel(logging.DEBUG)
        else:
            logger.setLevel(logging.INFO)

    def ensure_isolated(self: Cli) -> None:
        """Ensure the environment is isolated."""
        logger = logging.getLogger("pip4a")
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
            logger.warning(err)
            for error in errors:
                err = f"- {error}"
                logger.warning(err)
            err = "Exiting."
            logger.critical(err)

    def run(self: Cli) -> None:
        """Run the application."""
        logger = logging.getLogger("pip4a")

        self.config = Config(args=self.args)

        if self.config.args.subcommand == "check":
            self.config.init()
            checker = Checker(config=self.config)
            checker.run()
            sys.exit(0)

        if self.config.args.subcommand == "inspect":
            self.config.init()
            inspector = Inspector(config=self.config)
            inspector.run()
            sys.exit(0)

        if self.config.args.subcommand == "list":
            self.config.init()
            lister = Lister(config=self.config, output_format="list")
            lister.run()
            sys.exit(0)

        if "," in self.config.args.collection_specifier:
            err = "Multiple optional dependencies are not supported at this time."
            logger.critical(err)
            sys.exit(1)

        if self.config.args.subcommand == "install":
            self.config.init(create_venv=True)
            installer = Installer(self.config)
            installer.run()
            sys.exit(0)

        if self.config.args.subcommand == "uninstall":
            self.config.init()
            uninstaller = UnInstaller(self.config)
            uninstaller.run()
            sys.exit(0)


def main() -> None:
    """Entry point for ansible-creator CLI."""
    cli = Cli()
    cli.parse_args()
    cli.init_logger()
    cli.ensure_isolated()
    cli.run()


if __name__ == "__main__":
    main()
