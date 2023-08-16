"""Parse the command line arguments."""
import argparse


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
        "--verbose",
        action="store_true",
        help="Increase output verbosity.",
    )

    subparsers = parser.add_subparsers(
        title="subcommands",
        description="valid subcommands",
        help="additional help",
        dest="subcommand",
    )

    install_usage = """Usage:
        pipc install .
        pipc install -e .
        pipc install -e .[test]
        python -m pipc install ansible.utils"""

    install = subparsers.add_parser(
        "install",
        epilog=install_usage,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    install.add_argument(
        "-e",
        "--editable",
        action="store_true",
        help="Install editable.",
    )
    install.add_argument(
        "collection_specifier",
        help="Collection to install.",
    )

    uninstall = subparsers.add_parser(
        "uninstall",
        epilog=install_usage,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    uninstall.add_argument(
        "collection_specifier",
        help="Collection to uninstall.",
    )

    return parser.parse_args()
