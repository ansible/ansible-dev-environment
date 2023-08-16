"""CLI entrypoint."""

from __future__ import annotations

import logging
import os

from pathlib import Path
from typing import TYPE_CHECKING

from .app import App
from .arg_parser import parse
from .installer import Installer
from .logger import ColoredFormatter, ExitOnExceptionHandler
from .uninstaller import UnInstaller
from .utils import get_galaxy


if TYPE_CHECKING:
    from argparse import Namespace


class Cli:
    """The Cli class."""

    def __init__(self: Cli) -> None:
        """Initialize the CLI and parse CLI args."""
        self.args: Namespace
        self.app: App

    def parse_args(self: Cli) -> None:
        """Parse the command line arguments."""
        self.args = parse()

    def init_logger(self: Cli) -> None:
        """Initialize the logger."""
        logger = logging.getLogger("pipc")
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
        logger = logging.getLogger("pipc")
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
        collection_name, dependencies = get_galaxy()

        self.app = App(
            args=self.args,
            collection_name=collection_name,
            collection_dependencies=dependencies,
        )
        if self.app.args.subcommand == "install":
            installer = Installer(self.app)
            installer.run()

        if self.app.args.subcommand == "uninstall":
            uninstaller = UnInstaller(self.app)
            uninstaller.run()


def main() -> None:
    """Entry point for ansible-creator CLI."""
    cli = Cli()
    cli.parse_args()
    cli.init_logger()
    cli.ensure_isolated()
    cli.run()


if __name__ == "__main__":
    main()
