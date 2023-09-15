"""Parse the command line arguments."""
import argparse


try:
    from ._version import version as __version__
except ImportError:  # pragma: no cover
    try:
        import pkg_resources

        __version__ = pkg_resources.get_distribution("pip4a").version
    except Exception:  # pylint: disable=broad-except # noqa: BLE001
        # this is the fallback SemVer version picked by setuptools_scm when tag
        # information is not available.
        __version__ = "0.1.dev1"


def parse() -> argparse.Namespace:
    """Parse the command line arguments.

    Returns:
        The arguments
    """
    parser = argparse.ArgumentParser(
        description="A pip-like ansible collection installer.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        help="Show version and exit.",
        version=__version__,
    )

    subparsers = parser.add_subparsers(
        title="subcommands",
        description="valid subcommands",
        dest="subcommand",
        required=True,
    )

    level1 = argparse.ArgumentParser(add_help=False)
    level1.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Give more output. Option is additive, and can be used up to 3 times.",
    )
    level1.add_argument(
        "--venv",
        help="Target virtual environment.",
    )

    level1.add_argument(
        "--no-ansi",
        action="store_true",
        default=False,
        help="Disable the use of ANSI codes for terminal hyperlink generation and color.",
    )

    _check = subparsers.add_parser(
        "check",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[level1],
        help="Check installed collections",
    )

    _inspect = subparsers.add_parser(
        "inspect",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[level1],
        help="Inspect installed collections",
    )

    _list = subparsers.add_parser(
        "list",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[level1],
        help="List installed collections",
    )

    _tree = subparsers.add_parser(
        "tree",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[level1],
        help="Generate a dependency tree",
    )

    level2 = argparse.ArgumentParser(add_help=False, parents=[level1])
    spec_or_req = level2.add_mutually_exclusive_group(required=True)
    spec_or_req.add_argument(
        "collection_specifier",
        help="Collection name or path to collection with extras.",
        nargs="?",
    )
    spec_or_req.add_argument(
        "-r",
        "--requirement",
        help="Install from the given requirements file.",
        required=False,
    )

    install_usage = """Usage:
        pip4a install .
        pip4a install -e .
        pip4a install -e .[test]
        python -m pip4a install ansible.utils"""

    install = subparsers.add_parser(
        "install",
        epilog=install_usage,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[level2],
        help="Install a collection.",
    )
    install.add_argument(
        "-e",
        "--editable",
        action="store_true",
        help="Install editable.",
    )

    _uninstall = subparsers.add_parser(
        "uninstall",
        epilog=install_usage,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[level2],
        help="Uninstall a collection.",
    )

    return parser.parse_args()
