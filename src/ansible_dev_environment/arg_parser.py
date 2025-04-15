"""Parse the command line arguments."""

from __future__ import annotations

import argparse
import contextlib
import logging
import os
import sys
import warnings

from argparse import HelpFormatter
from pathlib import Path
from typing import TYPE_CHECKING

from .utils import str_to_bool


try:
    import argcomplete

    HAS_ARGCOMPLETE = True
except ImportError:  # pragma: no cover
    HAS_ARGCOMPLETE = False


logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from typing import Any


ENVVAR_MAPPING: dict[str, str] = {
    "ansi": "NO_COLOR",
    "isolation_mode": "ADE_ISOLATION_MODE",
    "seed": "ADE_SEED",
    "uv": "ADE_UV",
    "venv": "VIRTUAL_ENV",
    "verbose": "ADE_VERBOSE",
}

try:
    from ._version import version as __version__  # type: ignore[unused-ignore,import-not-found]
except ImportError:  # pragma: no cover
    try:
        import pkg_resources

        __version__ = pkg_resources.get_distribution(
            "ansible_dev_environment",
        ).version
    except Exception:  # pylint: disable=broad-except # noqa: BLE001
        # this is the fallback SemVer version picked by setuptools_scm when tag
        # information is not available.
        __version__ = "0.1.dev1"


def common_args(parser: ArgumentParser) -> None:
    """Add common arguments to the parser.

    Args:
        parser: The parser to add the arguments to
    """
    parser.add_argument(
        "--ansi",
        action=argparse.BooleanOptionalAction,
        default=True,
        dest="ansi",
        help="Enable or disable the use of ANSI codes for terminal hyperlink generation and color.",
    )

    parser.add_argument(
        "--lf",
        "--log-file <file>",
        dest="log_file",
        default=str(Path.cwd() / "ansible-dev-environment.log"),
        help="Log file to write to.",
    )
    parser.add_argument(
        "--ll",
        "--log-level <level>",
        dest="log_level",
        default="notset",
        choices=["notset", "debug", "info", "warning", "error", "critical"],
        help="Log level for file output.",
    )
    parser.add_argument(
        "--la",
        "--log-append <bool>",
        dest="log_append",
        choices=["true", "false"],
        default="true",
        help="Append to log file.",
    )
    parser.add_argument(
        "--uv",
        dest="uv",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable or disable the use of uv as the python package manager if found.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Give more CLI output. Option is additive, and can be used up to 3 times.",
    )


def parse() -> argparse.Namespace:
    """Parse the command line arguments.

    Returns:
        The arguments
    """
    parser = ArgumentParser(
        description="A pip-like ansible collection installer.",
        formatter_class=CustomHelpFormatter,
    )

    common_args(parser)

    parser.add_argument(
        "-V",
        "--version",
        action="version",
        help="Show version and exit.",
        version=__version__,
    )

    subparsers = parser.add_subparsers(
        title="Commands",
        dest="subcommand",
        metavar="",
        required=True,
    )

    level1 = ArgumentParser(add_help=False)

    level1.add_argument(
        "--venv <directory>",
        help="Target virtual environment. Created with 'ade install' if not found.",
        default=".venv",
        dest="venv",
    )

    level1.add_argument(
        "--cpi",
        "--collection-pre-install",
        help="Pre install collections from source, reads source-requirements.yml file.",
        default=False,
        action="store_true",
    )

    level1.add_argument(
        "--ssp",
        "--system-site-packages",
        help="When building a virtual environment, give access to the system site-packages dir.",
        default=False,
        dest="system_site_packages",
        action="store_true",
    )

    common_args(level1)

    _check = subparsers.add_parser(
        "check",
        formatter_class=CustomHelpFormatter,
        parents=[level1],
        help="Check installed collections",
    )

    _inspect = subparsers.add_parser(
        "inspect",
        formatter_class=CustomHelpFormatter,
        parents=[level1],
        help="Inspect installed collections",
    )

    _list = subparsers.add_parser(
        "list",
        formatter_class=CustomHelpFormatter,
        parents=[level1],
        help="List installed collections",
    )

    _tree = subparsers.add_parser(
        "tree",
        formatter_class=CustomHelpFormatter,
        parents=[level1],
        help="Generate a dependency tree",
    )

    level2 = ArgumentParser(add_help=False, parents=[level1])
    level2.add_argument(
        "collection_specifier",
        help="Collection name or path to collection with extras.",
        nargs="*",
    )
    level2.add_argument(
        "-r",
        "--requirement <file>",
        dest="requirement",
        help="Install from the given requirements file.",
        required=False,
    )

    install = subparsers.add_parser(
        "install",
        formatter_class=CustomHelpFormatter,
        parents=[level2],
        help="Install a collection.",
    )
    install.add_argument(
        "-e",
        "--editable",
        action="store_true",
        help="Install editable.",
    )

    install.add_argument(
        "--seed",
        action=argparse.BooleanOptionalAction,
        default=True,
        dest="seed",
        help="Install seed packages inside the virtual environment (ansible-dev-tools).",
    )

    install.add_argument(
        "--im",
        "--isolation-mode",
        dest="isolation_mode",
        help=(
            "Isolation mode to use. restrictive: Exit if collections are found in ansible home or the system collection directory. "
            " cfg: Update or add an ansible.cfg file in the current working directory to isolate the workspace"
            " none: No isolation, not recommended."
        ),
        default="restrictive",
        choices=["restrictive", "cfg", "none"],
        type=str,
    )

    _uninstall = subparsers.add_parser(
        "uninstall",
        formatter_class=CustomHelpFormatter,
        parents=[level2],
        help="Uninstall a collection.",
    )

    _group_titles(parser)
    for subparser in subparsers.choices.values():
        _group_titles(subparser)

    args = sys.argv[1:]
    for param in ("--adt", "--ansible-dev-tools"):
        with contextlib.suppress(ValueError):
            args[args.index(param)] = "--seed"
            err = f"The parameter '{param}' is deprecated, use 'ADE_SEED or '--seed' instead."
            warnings.warn(err, DeprecationWarning, stacklevel=2)

    if skip_uv := os.environ.get("SKIP_UV"):
        os.environ["ADE_UV"] = skip_uv
        err = "The environment variable 'SKIP_UV' is deprecated, use 'ADE_UV' or '--no-uv' instead."
        warnings.warn(err, DeprecationWarning, stacklevel=2)

    if HAS_ARGCOMPLETE:
        argcomplete.autocomplete(parser)

    return apply_envvars(args=args, parser=parser)


def _get_action(actions: list[argparse.Action], dest: str) -> argparse.Action | None:
    """Get the action for a given destination.

    Args:
        actions: The list of actions
        dest: The destination to get the action for

    Returns:
        The action for the given destination

    """
    for action in actions:
        if action.dest == dest:
            return action
        if isinstance(action, argparse._SubParsersAction):  # noqa: SLF001
            for subparser in action.choices.values():
                sub_action = _get_action(subparser._actions, dest)  # noqa: SLF001
                if sub_action is not None:
                    return sub_action

    return None


def apply_envvars(args: list[str], parser: ArgumentParser) -> argparse.Namespace:
    """Apply the environment variables to the arguments.

    Special handling exists NO_COLOR since it's value shouldn't matter.
    Also account for a space in some option strings when checking for presence in sys.argv.

    Args:
        args: The cli arguments
        parser: The argument parser

    Returns:
        The resulting namespace

    Raises:
        NotImplementedError: If the action type is not implemented
    """
    cli_result = parser.parse_args(args)

    for dest, envvar in ENVVAR_MAPPING.items():
        if (action := _get_action(parser._actions, dest)) is None:  # noqa: SLF001
            err = f"Action for {dest} not found in parser"
            raise NotImplementedError(err)

        present = any(
            option
            for option in action.option_strings
            if any(arg for arg in args if arg.startswith(option.split()[0]))
        )
        envvar_value = os.environ.get(envvar)

        if present or envvar_value is None:
            continue

        final_value: bool | int | str | None = None
        named_type = "not set"

        with contextlib.suppress(ValueError):
            if envvar == "NO_COLOR" and envvar_value != "":
                final_value = False
            elif isinstance(action, (argparse.BooleanOptionalAction, argparse._StoreTrueAction)):  # noqa: SLF001
                named_type = "boolean"
                final_value = str_to_bool(envvar_value)
            elif isinstance(action, argparse._CountAction) or action.type is int:  # noqa: SLF001
                named_type = "int"
                final_value = int(envvar_value)
            elif action.type is str or action.type is None:
                named_type = "str"
                final_value = envvar_value
            else:
                err = f"Action type {action.type} not implemented for envvar {envvar}"
                raise NotImplementedError(err)

        err = f"ade: error: environment variable {envvar}: invalid value: '{envvar_value}' "
        if final_value is None:
            err += f"could not convert to {named_type}\n"
            parser.exit(1, err)
        if action.choices and final_value not in action.choices:
            err += f"(choose from {', '.join(map(repr, action.choices))})\n"
            parser.exit(1, err)

        setattr(cli_result, dest, final_value)

    return cli_result


def _group_titles(parser: ArgumentParser) -> None:
    """Set the group titles to be capitalized.

    Args:
        parser: The parser to set the group titles for
    """
    for group in parser._action_groups:  # noqa: SLF001
        if group.title is None:
            continue
        group.title = group.title.capitalize()


class ArgumentParser(argparse.ArgumentParser):
    """A custom argument parser."""

    def add_argument(  # type: ignore[override]
        self,
        *args: Any,  # noqa: ANN401
        **kwargs: Any,  # noqa: ANN401
    ) -> None:
        """Add an argument.

        Args:
            *args: The arguments
            **kwargs: The keyword arguments
        """
        if "choices" in kwargs:
            kwargs["help"] += f" (choices: {', '.join(kwargs['choices'])})"
        if kwargs.get("dest") in ENVVAR_MAPPING:
            envvar = ENVVAR_MAPPING[kwargs["dest"]]
            kwargs["help"] += f" (env: {envvar})"
        if "default" in kwargs and kwargs["default"] != "==SUPPRESS==":
            kwargs["help"] += f" (default: {kwargs['default']})"
        kwargs["help"] = kwargs["help"][0].upper() + kwargs["help"][1:]
        super().add_argument(*args, **kwargs)


class CustomHelpFormatter(HelpFormatter):
    """A custom help formatter."""

    def __init__(self, prog: str) -> None:
        """Initialize the help formatter.

        Args:
            prog: The program name
        """
        long_string = "--abc  --really_really_really_log"
        # 3 here accounts for the spaces in the ljust(6) below
        HelpFormatter.__init__(
            self,
            prog=prog,
            indent_increment=1,
            max_help_position=len(long_string) + 3,
        )

    def _format_action_invocation(
        self,
        action: argparse.Action,
    ) -> str:
        """Format the action invocation.

        Args:
            action: The action to format

        Raises:
            ValueError: If more than 2 options are given

        Returns:
            The formatted action invocation
        """
        if not action.option_strings:
            default = self._get_default_metavar_for_positional(action)
            (metavar,) = self._metavar_formatter(action, default)(1)
            return metavar

        if len(action.option_strings) == 1:
            return action.option_strings[0]

        max_variations = 2
        if len(action.option_strings) == max_variations:
            # Account for a --1234 --long-option-name
            return f"{action.option_strings[0].ljust(6)} {action.option_strings[1]}"
        msg = "Too many option strings"
        raise ValueError(msg)
