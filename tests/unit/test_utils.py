"""Unit test for the utilities module."""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path

import pytest

from pip4a.collection import Collection, parse_collection_request
from pip4a.config import Config
from pip4a.utils import TermFeatures


config = Config(args=Namespace(), term_features=TermFeatures(color=False, links=False))

FIXTURE_DIR = Path(__file__).parent.parent.resolve() / "fixtures"
scenarios = (
    (
        "ansible.utils",
        Collection(config=config, cname="utils", cnamespace="ansible", local=False),
    ),
    (
        "ansible.utils:1.0.0",
        Collection(
            config=config,
            cname="utils",
            cnamespace="ansible",
            specifier=":1.0.0",
            local=False,
        ),
    ),
    (
        "ansible.utils>=1.0.0",
        Collection(
            config=config,
            cname="utils",
            cnamespace="ansible",
            specifier=">=1.0.0",
            local=False,
        ),
    ),
    (
        str(FIXTURE_DIR),
        Collection(
            cname="cname",
            cnamespace="cnamespace",
            config=config,
            local=True,
            path=FIXTURE_DIR,
            specifier=None,
        ),
    ),
    (
        str(FIXTURE_DIR) + "/[test]",
        Collection(
            cname="cname",
            cnamespace="cnamespace",
            config=config,
            local=True,
            opt_deps="test",
            path=FIXTURE_DIR,
            specifier=None,
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
def test_parse_collection_request(scenario: tuple[str, Collection | None]) -> None:
    """Test that the parse_collection_request function works as expected."""
    string, spec = scenario
    if spec is None:
        with pytest.raises(SystemExit):
            parse_collection_request(string=string, config=config)
    else:
        assert parse_collection_request(string=string, config=config) == spec
