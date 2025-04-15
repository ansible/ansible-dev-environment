"""CLI entrypoint."""

from __future__ import annotations

import os
import sys
import warnings

from pathlib import Path
from typing import TYPE_CHECKING

from ansible_dev_environment import subcommands

from .arg_parser import parse
from .config import Config
from .definitions import COLLECTIONS_PATH as CP
from .definitions import AnsibleCfg
from .output import Output
from .utils import TermFeatures


if TYPE_CHECKING:
    from argparse import Namespace


class Cli:
    """The Cli class."""

    def __init__(self) -> None:
        """Initialize the CLI and parse CLI args."""
        self.args: Namespace
        self.config: Config
        self.output: Output
        self.term_features: TermFeatures
        self.acfg_cwd = AnsibleCfg(path=Path("./ansible.cfg"))
        self.acfg_home = AnsibleCfg(path=Path("~/.ansible.cfg").expanduser().resolve())
        self.acfg_system = AnsibleCfg(path=Path("/etc/ansible/ansible.cfg"))
        self.acfg_trusted: Path | None

    def parse_args(self) -> None:
        """Parse the command line arguments."""
        self.args = parse()
        if hasattr(self.args, "requirement") and self.args.requirement:
            self.args.requirement = Path(self.args.requirement).expanduser().resolve()
        if self.args.cpi:
            self.args.requirement = Path(".config/source-requirements.yml").expanduser().resolve()

    def init_output(self) -> None:
        """Initialize the output object."""
        if not sys.stdout.isatty():
            self.term_features = TermFeatures(color=False, links=False)
        else:
            self.term_features = TermFeatures(
                color=self.args.ansi,
                links=self.args.ansi,
            )

        self.output = Output(
            log_append=self.args.log_append,
            log_file=self.args.log_file,
            log_level=self.args.log_level,
            term_features=self.term_features,
            verbosity=self.args.verbose,
        )

    def args_sanity(self) -> None:
        """Perform some sanity checking on the args."""
        # Ensure PATH is not broken (~ should not present as many tools do not expand it)
        if "~" in os.environ.get("PATH", ""):
            err = "~ character was found inside PATH, correct your environment configuration to avoid it. See https://stackoverflow.com/a/44704799/99834"
            self.output.critical(err)
        # Missing args
        if (
            hasattr(self.args, "requirement")
            and self.args.requirement
            and not self.args.requirement.exists()
        ):
            err = f"Requirements file not found: {self.args.requirement}"
            self.output.critical(err)

        # Multiple editable collections
        if (
            hasattr(self.args, "collection_specifier")
            and len(self.args.collection_specifier) > 1
            and hasattr(self.args, "editable")
            and self.args.editable
        ):
            err = "Editable can only be used with a single collection specifier."
            self.output.critical(err)

        # Editable with requirements file
        if (
            hasattr(self.args, "requirement")
            and self.args.requirement
            and hasattr(self.args, "editable")
            and self.args.editable
        ):
            err = "Editable can not be used with a requirements file."
            self.output.critical(err)

        self.output.debug("Arguments sanity check passed.")
        for arg in vars(self.args):
            self.output.debug(f"{arg}: {getattr(self.args, arg)}")

    def isolation_check(self) -> bool:
        """Check the environment for isolation.

        Returns:
            True if ade can continue, false otherwise.
        """
        if not hasattr(self.args, "isolation_mode"):
            return True
        if self.args.isolation_mode == "restrictive":
            return self.isolation_restrictive()
        if self.args.isolation_mode == "cfg":
            return self.isolation_cfg()
        if self.args.isolation_mode == "none":
            return self.isolation_none()
        self.acfg_trusted = None
        return False

    def isolation_cfg(self) -> bool:
        """Ensure the environment is isolated using cfg isolation.

        Returns:
            True if ade can continue, false otherwise.
        """
        if os.environ.get("ANSIBLE_CONFIG"):
            err = "ANSIBLE_CONFIG is set"
            self.output.error(err)
            hint = "Run `unset ANSIBLE_CONFIG` to unset it using cfg isolation mode."
            self.output.hint(hint)
            self.acfg_trusted = None
            return False

        if self.acfg_cwd.exists:
            if self.acfg_cwd.collections_path_is_dot:
                msg = f"{self.acfg_cwd.path} has '{CP}' which isolates this workspace."
                self.output.info(msg)
            else:
                self.acfg_cwd.set_or_update_collections_path()
                msg = f"{self.acfg_cwd.path} updated with '{CP}' to isolate this workspace."
                self.output.warning(msg)
            self.acfg_trusted = self.acfg_cwd.path
            return True

        if self.acfg_home.exists:
            if self.acfg_home.collections_path_is_dot:
                msg = f"{self.acfg_home.path} has '{CP}' which isolates this and all workspaces."
                self.output.info(msg)
            else:
                self.acfg_home.set_or_update_collections_path()
                msg = (
                    f"{self.acfg_home.path} updated with '{CP}' to isolate this and all workspaces."
                )
                self.output.warning(msg)
            self.acfg_trusted = self.acfg_home.path
            return True

        if self.acfg_system.exists and self.acfg_system.collections_path_is_dot:
            msg = f"{self.acfg_system.path} has '{CP}' which isolates this and all workspaces."
            self.output.info(msg)
            self.acfg_trusted = self.acfg_system.path
            return True

        self.acfg_cwd.author_new()
        msg = f"{self.acfg_cwd.path} created with '{CP}' to isolate this workspace."
        self.output.info(msg)
        self.acfg_trusted = self.acfg_cwd.path
        return True

    def isolation_none(self) -> bool:
        """No isolation.

        Returns:
            True if ade can continue, false otherwise.
        """
        self.output.warning(
            "An unisolated development environment can cause issues with conflicting dependency"
            " versions and the use of incompatible collections.",
        )
        self.acfg_trusted = None
        return True

    def isolation_restrictive(self) -> bool:
        """Ensure the environment is isolated.

        Returns:
            True if ade can continue, false otherwise.
        """
        env_vars = os.environ
        errored = False
        if "ANSIBLE_COLLECTIONS_PATHS" in env_vars:
            err = "ANSIBLE_COLLECTIONS_PATHS is set"
            self.output.error(err)
            hint = "Run `unset ANSIBLE_COLLECTIONS_PATHS` to unset it."
            self.output.hint(hint)
            errored = True
        if "ANSIBLE_COLLECTION_PATH" in env_vars:
            err = "ANSIBLE_COLLECTION_PATH is set"
            self.output.error(err)
            hint = "Run `unset ANSIBLE_COLLECTION_PATH` to unset it."
            self.output.hint(hint)
            errored = True

        home_coll = (
            Path(os.environ.get("ANSIBLE_HOME", "~/.ansible")).expanduser()
            / "collections/ansible_collections"
        )
        if home_coll.exists() and tuple(home_coll.iterdir()):
            err = f"Collections found in {home_coll}"
            self.output.error(err)
            hint = f"Run `rm -rf {home_coll}` to remove them or configure ANSIBLE_HOME to point to a different location."
            self.output.hint(hint)
            errored = True

        usr_coll = Path("/usr/share/ansible/collections")
        if usr_coll.exists() and tuple(usr_coll.iterdir()):
            err = f"Collections found in {usr_coll}"
            self.output.error(err)
            hint = "Run `sudo rm -rf /usr/share/ansible/collections` to remove them."
            self.output.hint(hint)
            errored = True
        if errored:
            err = "The development environment is not isolated, please resolve the above errors."
            self.output.warning(err)
            return False
        return True

    def run(self) -> None:
        """Run the application."""
        self.config = Config(
            args=self.args,
            output=self.output,
            term_features=self.term_features,
        )
        self.config.init()

        subcommand_cls = getattr(subcommands, self.config.args.subcommand.capitalize())
        subcommand = subcommand_cls(config=self.config, output=self.output)
        subcommand.run()
        self.exit()

    def exit(self) -> None:
        """Exit the application setting the return code."""
        if self.output.call_count["error"]:
            sys.exit(1)
        if self.output.call_count["warning"]:
            sys.exit(2)
        sys.exit(0)


def main(*, dry: bool = False) -> None:
    """Entry point for ansible-creator CLI.

    Args:
        dry: Skip main execution, used internally for testing.
    """
    with warnings.catch_warnings(record=True) as warns:
        warnings.simplefilter(action="default")
        cli = Cli()
        cli.parse_args()
        cli.init_output()
    for warn in warns:
        cli.output.warning(str(warn.message))
    warnings.resetwarnings()
    cli.args_sanity()
    if not cli.isolation_check():
        cli.exit()
    if not dry:
        cli.run()
