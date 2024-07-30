"""Tests for the collection module."""

from __future__ import annotations

from argparse import Namespace
from typing import TYPE_CHECKING

import pytest

from ansible_dev_environment.collection import Collection, get_galaxy
from ansible_dev_environment.config import Config
from ansible_dev_environment.utils import TermFeatures


if TYPE_CHECKING:
    from pathlib import Path

    from ansible_dev_environment.output import Output


@pytest.mark.usefixtures("_wide_console")
def test_get_galaxy_missing(
    tmp_path: Path,
    output: Output,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test when the galaxy.yml file is missing.

    Args:
        tmp_path: Temporary directory.
        output: Output class object.
        capsys: Pytest fixture
    """
    config = Config(
        args=Namespace(),
        term_features=TermFeatures(color=False, links=False),
        output=output,
    )
    collection = Collection(
        config=config,
        path=tmp_path,
        cname="utils",
        cnamespace="ansible",
        local=False,
        original="ansible.utils",
        specifier="",
        opt_deps="",
        csource=[],
    )
    with pytest.raises(SystemExit):
        get_galaxy(collection, output)

    captured = capsys.readouterr()
    assert f"Failed to find {tmp_path / 'galaxy.yml'} in {tmp_path}\n" in captured.err


@pytest.mark.usefixtures("_wide_console")
def test_get_galaxy_no_meta(
    tmp_path: Path,
    output: Output,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test when the galaxy.yml file is name/namespace.

    Args:
        tmp_path: Temporary directory.
        output: Output class object.
        capsys: Pytest fixture
    """
    (tmp_path / "galaxy.yml").write_text("corrupt: yaml\n")
    config = Config(
        args=Namespace(),
        term_features=TermFeatures(color=False, links=False),
        output=output,
    )
    collection = Collection(
        config=config,
        path=tmp_path,
        cname="utils",
        cnamespace="ansible",
        local=False,
        original="ansible.utils",
        specifier="",
        opt_deps="",
        csource=[],
    )
    with pytest.raises(SystemExit):
        get_galaxy(collection, output)

    captured = capsys.readouterr()
    assert (
        f"Failed to find collection name in {tmp_path / 'galaxy.yml'}: 'namespace'\n"
        in captured.err
    )


@pytest.mark.usefixtures("_wide_console")
def test_get_galaxy_corrupt(
    tmp_path: Path,
    output: Output,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test when the galaxy.yml file is missing.

    Args:
        tmp_path: Temporary directory.
        output: Output class object.
        capsys: Pytest fixture
    """
    (tmp_path / "galaxy.yml").write_text(",")
    config = Config(
        args=Namespace(),
        term_features=TermFeatures(color=False, links=False),
        output=output,
    )
    collection = Collection(
        config=config,
        path=tmp_path,
        cname="utils",
        cnamespace="ansible",
        local=False,
        original="ansible.utils",
        specifier="",
        opt_deps="",
        csource=[],
    )
    with pytest.raises(SystemExit):
        get_galaxy(collection, output)

    captured = capsys.readouterr()
    assert "Failed to load yaml file:" in captured.err
