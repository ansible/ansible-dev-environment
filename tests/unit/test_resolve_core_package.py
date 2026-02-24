"""Tests for _resolve_core_package."""

from __future__ import annotations

import pytest

from ansible_dev_environment.subcommands.installer import (
    ANSIBLE_CORE_REPO_URL,
    _resolve_core_package,
)


@pytest.mark.parametrize(
    ("core_version", "expected"),
    (
        ("2.16.0", "ansible-core==2.16.0"),
        ("2.19.3", "ansible-core==2.19.3"),
        ("2.16.14", "ansible-core==2.16.14"),
        ("devel", f"{ANSIBLE_CORE_REPO_URL}/devel.tar.gz"),
        ("milestone", f"{ANSIBLE_CORE_REPO_URL}/milestone.tar.gz"),
        ("stable-2.16", f"{ANSIBLE_CORE_REPO_URL}/stable-2.16.tar.gz"),
        ("stable-2.19", f"{ANSIBLE_CORE_REPO_URL}/stable-2.19.tar.gz"),
        (
            "https://github.com/ansible/ansible/archive/devel.tar.gz",
            "https://github.com/ansible/ansible/archive/devel.tar.gz",
        ),
        (
            "https://github.com/ansible/ansible/archive/stable-2.16.tar.gz",
            "https://github.com/ansible/ansible/archive/stable-2.16.tar.gz",
        ),
        (
            "http://example.com/custom-ansible.tar.gz",
            "http://example.com/custom-ansible.tar.gz",
        ),
    ),
    ids=[
        "pypi-three-part",
        "pypi-three-part-recent",
        "pypi-three-part-patch",
        "branch-devel",
        "branch-milestone",
        "branch-stable-2.16",
        "branch-stable-2.19",
        "url-github-devel",
        "url-github-stable",
        "url-custom",
    ],
)
def test_resolve_core_package(core_version: str, expected: str) -> None:
    """Verify _resolve_core_package maps versions, branches, and URLs correctly.

    Args:
        core_version: The input to _resolve_core_package.
        expected: The expected pip-installable package specifier.
    """
    assert _resolve_core_package(core_version) == expected
