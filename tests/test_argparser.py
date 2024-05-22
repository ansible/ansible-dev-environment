"""Tests for the arg_parser module."""

import pytest

from ansible_dev_environment.arg_parser import (
    ArgumentParser,
    CustomHelpFormatter,
    _group_titles,
)


def test_no_option_string(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test an argument without an option string.

    Args:
        capsys (pytest.CaptureFixture[str]): Pytest fixture.
    """
    parser = ArgumentParser(
        formatter_class=CustomHelpFormatter,
    )
    parser.add_argument(
        dest="test",
        action="store_true",
        help="Test this",
    )
    parser.print_help()
    captured = capsys.readouterr()
    assert "Test this" in captured.out


def test_one_string(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test an argument without an option string.

    Args:
        capsys (pytest.CaptureFixture[str]): Pytest fixture.
    """
    parser = ArgumentParser(
        formatter_class=CustomHelpFormatter,
    )
    parser.add_argument(
        "-t",
        dest="test",
        action="store_true",
        help="Test this",
    )
    parser.print_help()
    captured = capsys.readouterr()
    assert "-t             Test this" in captured.out


def test_too_many_string(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test an argument with too many option strings.

    Args:
        monkeypatch (pytest.MonkeyPatch): Pytest fixture.
    """
    monkeypatch.setattr("sys.argv", ["prog", "--help"])

    parser = ArgumentParser(
        formatter_class=CustomHelpFormatter,
    )
    parser.add_argument(
        "-t",
        "-test",
        "--test",
        action="store_true",
        help="Test this",
    )
    with pytest.raises(ValueError, match="Too many option strings"):
        parser.parse_args()


def test_group_no_title(capsys: pytest.CaptureFixture[str]) -> None:
    """Test a group without a title.

    Args:
        capsys (pytest.CaptureFixture[str]): Pytest fixture.
    """
    parser = ArgumentParser(
        formatter_class=CustomHelpFormatter,
    )
    parser.add_argument_group()
    _group_titles(parser)
    parser.print_help()
    captured = capsys.readouterr()
    assert "--help" in captured.out
