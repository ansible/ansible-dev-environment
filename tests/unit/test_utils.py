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
from ansible_dev_environment.utils import (
    TermFeatures,
    builder_introspect,
    opt_deps_to_files,
    str_to_bool,
)


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


def test_builder_found(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    session_venv: Config,
) -> None:
    """Test that builder is found.

    Args:
        tmp_path: A temporary path
        monkeypatch: The pytest Monkeypatch fixture
        session_venv: The session venv

    Raises:
        AssertionError: if either file is not found
    """

    @property  # type: ignore[misc]
    def cache_dir(_self: Config) -> Path:
        """Return a temporary cache directory.

        Args:
            _self: The Config object

        Returns:
            A temporary cache directory.
        """
        return tmp_path

    monkeypatch.setattr(Config, "cache_dir", cache_dir)

    args = Namespace(
        venv=session_venv.venv,
        system_site_packages=False,
        verbose=0,
        subcommand="check",
        uv=True,
    )

    cfg = Config(
        args=args,
        term_features=term_features,
        output=output,
    )
    cfg.init()

    builder_introspect(cfg, output)

    assert cfg.discovered_bindep_reqs.exists() is True
    assert cfg.discovered_python_reqs.exists() is True


def test_str_to_bool() -> None:
    """Test the str_to_bool function.

    This function tests the conversion of string values to boolean values.
    """
    assert str_to_bool("true") is True
    assert str_to_bool("True") is True
    assert str_to_bool("1") is True
    assert str_to_bool("yes") is True
    assert str_to_bool("y") is True
    assert str_to_bool("on") is True

    assert str_to_bool("false") is False
    assert str_to_bool("False") is False
    assert str_to_bool("0") is False
    assert str_to_bool("no") is False
    assert str_to_bool("n") is False
    assert str_to_bool("off") is False

    assert str_to_bool("anything else") is None


def test_opt_deps_to_files(tmp_path: Path, capsys: pytest.LogCaptureFixture) -> None:
    """Test the opt_deps_to_files function.

    Args:
        tmp_path: A temporary path
    """
    # Create a temporary file with some content
    f1 = tmp_path / "test-requirements.txt"
    f1.touch()
    f2 = tmp_path / "requirements-dev.txt"
    f2.touch()

    collection = Collection(
        config=config,
        cname="cname",
        cnamespace="cnamespace",
        local=True,
        path=tmp_path,
        specifier="",
        original=str(tmp_path),
        opt_deps="test,dev,foo",
        csource=[],
    )

    result = opt_deps_to_files(collection, output)

    captured = capsys.readouterr()

    assert result[0] == f1
    assert result[1] == f2
    assert "Error: Failed to find optional dependency file for 'foo'." in captured.err
