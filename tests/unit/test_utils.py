"""Unit test for the utilities module."""

from __future__ import annotations

from pathlib import Path

import pytest

from pip4a.utils import CollectionSpec, parse_collection_request


scenarios = (
    ("ansible.utils", CollectionSpec(cname="utils", cnamespace="ansible", local=False)),
    (
        "ansible.utils:1.0.0",
        CollectionSpec(
            cname="utils",
            cnamespace="ansible",
            specifier=":1.0.0",
            local=False,
        ),
    ),
    (
        "ansible.utils>=1.0.0",
        CollectionSpec(
            cname="utils",
            cnamespace="ansible",
            specifier=">=1.0.0",
            local=False,
        ),
    ),
    (
        "/",
        CollectionSpec(
            specifier=None,
            local=True,
            path=Path("/"),
        ),
    ),
    (
        "/[test]",
        CollectionSpec(
            specifier=None,
            local=True,
            path=Path("/"),
            opt_deps="test",
        ),
    ),
    (
        "/foo/bar",
        None,
    ),
    (
        "abcdefg",
        None,
    ),
)


@pytest.mark.parametrize("scenario", scenarios)
def test_parse_collection_request(scenario: tuple[str, CollectionSpec | None]) -> None:
    """Test that the parse_collection_request function works as expected."""
    string, spec = scenario
    if spec is None:
        with pytest.raises(SystemExit):
            parse_collection_request(string)
    else:
        assert parse_collection_request(string) == spec
