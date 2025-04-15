"""Test for cli and environment variable precedence."""

from __future__ import annotations

from typing import TypedDict

import pytest

from ansible_dev_environment.cli import Cli


class Data(TypedDict):
    """Test data dictionary.

    Attributes:
        attr: Attribute name.
        args: Command line argument.
        env: Environment variable name.
        cli_expected: Expected value from command line argument.
        env_expected: Expected value from environment variable.

    """

    attr: str
    args: str
    env: str
    cli_expected: bool | int | str
    env_expected: bool | int | str


params: list[Data] = [
    {
        "attr": "ansi",
        "args": "--ansi",
        "env": "NO_COLOR",
        "env_expected": False,
        "cli_expected": True,
    },
    {
        "attr": "seed",
        "args": "--seed",
        "env": "ADE_SEED",
        "env_expected": False,
        "cli_expected": True,
    },
    {"attr": "verbose", "args": "-vvv", "env": "ADE_VERBOSE", "env_expected": 2, "cli_expected": 3},
    {"attr": "uv", "args": "--uv", "env": "ADE_UV", "env_expected": False, "cli_expected": True},
]


@pytest.mark.parametrize("data", params, ids=lambda d: d["attr"])
def test_cli_precedence_flag(
    data: Data,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test CLI precedence over environment variables.

    Args:
        data: Test data dictionary.
        monkeypatch: Pytest fixture.

    """
    cli = Cli()

    args = ["ade", "install"]
    monkeypatch.setenv(data["env"], str(data["env_expected"]))
    monkeypatch.setattr("sys.argv", args)

    cli.parse_args()

    assert getattr(cli.args, data["attr"]) == data["env_expected"]

    args.append(data["args"])
    cli.parse_args()
    assert getattr(cli.args, data["attr"]) == data["cli_expected"]
