"""Test the config module."""

from __future__ import annotations

import argparse

from typing import TYPE_CHECKING

import pytest

from ansible_dev_environment.config import Config
from ansible_dev_environment.output import Output
from ansible_dev_environment.utils import TermFeatures


if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize(
    "system_site_packages",
    ((True, False)),
    ids=["ssp_true", "ssp_false"],
)
def test_paths(tmpdir: Path, system_site_packages: bool) -> None:  # noqa: FBT001
    """Test the paths.

    Several of the found directories should have a parent of the tmpdir / test_venv

    Args:
        tmpdir: A temporary directory.
        system_site_packages: Whether to include system site packages.
    """
    venv = tmpdir / "test_venv"
    args = argparse.Namespace(
        venv=str(venv),
        system_site_packages=system_site_packages,
        verbose=0,
    )
    term_features = TermFeatures(color=False, links=False)

    output = Output(
        log_file=str(tmpdir / "test_log.log"),
        log_level="debug",
        log_append="false",
        term_features=term_features,
        verbosity=0,
    )

    config = Config(args=args, output=output, term_features=term_features)
    config.init()

    assert config.venv == venv
    for attr in (
        "site_pkg_collections_path",
        "site_pkg_path",
        "venv_bindir",
        "venv_cache_dir",
        "venv_interpreter",
    ):
        assert venv in getattr(config, attr).parents
