"""Unit test for the utilities module."""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path

import pytest

from ansible_dev_environment.collection import (
    Collection,
    parse_collection_request,
)
from ansible_dev_environment.config import Config
from ansible_dev_environment.output import Output
from ansible_dev_environment.utils import TermFeatures


term_features = TermFeatures(color=False, links=False)

output = Output(
    log_file=str(Path.cwd() / "ansible-dev-environment.log"),
    log_level="notset",
    log_append="true",
    term_features=term_features,
    verbosity=0,
)
config = Config(
    args=Namespace(),
    term_features=term_features,
    output=output,
)

FIXTURE_DIR = Path(__file__).parent.parent.resolve() / "fixtures"
scenarios = (
    (
        "ansible.utils",
        Collection(
            config=config,
            cname="utils",
            cnamespace="ansible",
            local=False,
            original="ansible.utils",
            specifier="",
            path=Path(),
            opt_deps="",
            csource=[],
        ),
    ),
    (
        "ansible.utils:1.0.0",
        Collection(
            config=config,
            cname="utils",
            cnamespace="ansible",
            specifier=":1.0.0",
            local=False,
            original="ansible.utils:1.0.0",
            path=Path(),
            opt_deps="",
            csource=[],
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
            original="ansible.utils>=1.0.0",
            path=Path(),
            opt_deps="",
            csource=[],
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
            specifier="",
            original=str(FIXTURE_DIR),
            opt_deps="",
            csource=[],
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
            specifier="",
            original=str(FIXTURE_DIR) + "/[test]",
            csource=[],
        ),
    ),
    ("/foo/bar", None),
    ("abcdefg", None),
    ("/12345678901234567890[test]", None),
    ("not_a_collection_name", None),
)


@pytest.mark.parametrize("scenario", scenarios)
def test_parse_collection_request(scenario: tuple[str, Collection | None]) -> None:
    """Test that the parse_collection_request function works as expected.

    Args:
        scenario: A tuple containing the string to parse and the expected result.
    """
    string, spec = scenario
    if spec is None:
        with pytest.raises(SystemExit):
            parse_collection_request(string=string, config=config, output=output)
    else:
        assert parse_collection_request(string=string, config=config, output=output) == spec
