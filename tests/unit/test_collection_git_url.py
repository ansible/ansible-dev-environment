"""Tests for Git URL support in collection parsing.

This module contains comprehensive tests for the Git URL detection and parsing
functionality in the collection module, ensuring proper handling of various
Git URL formats and edge cases.
"""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from ansible_dev_environment.collection import (
    is_git_url,
    parse_collection_request,
    parse_git_url_collection_name,
)
from ansible_dev_environment.config import Config
from ansible_dev_environment.utils import TermFeatures


if TYPE_CHECKING:
    from ansible_dev_environment.output import Output


class TestIsGitUrl:
    """Test the is_git_url function with various URL formats."""

    @pytest.mark.parametrize(
        ("url", "expected"),
        [
            # Git+HTTPS URLs
            ("git+https://github.com/user/repo.git", True),
            ("git+https://gitlab.com/user/repo.git", True),
            ("git+https://example.com/user/repo.git", True),
            # Git+SSH URLs
            ("git+ssh://git@github.com/user/repo.git", True),
            ("git+ssh://git@gitlab.com/user/repo.git", True),
            # HTTPS .git URLs
            ("https://github.com/user/repo.git", True),
            ("https://gitlab.com/user/repo.git", True),
            # SSH Git URLs
            ("git@github.com:user/repo.git", True),
            ("git@gitlab.com:user/repo.git", True),
            # Non-Git URLs
            ("https://github.com/user/repo", False),
            ("https://example.com/path", False),
            ("community.general", False),
            ("./local/path", False),
            ("/absolute/path", False),
            ("", False),
        ],
    )
    def test_detects_git_urls_correctly(self, url: str, *, expected: bool) -> None:
        """Test that is_git_url correctly identifies Git URLs.

        Args:
            url: The URL to test
            expected: Whether the URL should be detected as a Git URL
        """
        assert is_git_url(url) == expected


class TestParseGitUrlCollectionName:
    """Test the parse_git_url_collection_name function."""

    @pytest.mark.parametrize(
        ("git_url", "expected_namespace", "expected_name"),
        [
            # GitHub URLs
            (
                "git+https://github.com/redhat-cop/ansible.mcp_builder.git",
                "redhat_cop",
                "mcp_builder",
            ),
            ("https://github.com/ansible/community.general.git", "ansible", "community.general"),
            ("git@github.com:user/ansible-collection-test.git", "user", "collection_test"),
            # GitLab URLs
            (
                "git+https://gitlab.com/group/ansible_collection_name.git",
                "group",
                "collection_name",
            ),
            ("https://gitlab.com/user/my-collection.git", "user", "my_collection"),
            # Generic Git URLs
            ("https://git.example.com/org/ansible.test.git", "org", "test"),
            ("git+ssh://git@git.company.com/team/collection.git", "team", "collection"),
            # Edge cases
            ("https://github.com/user/ansible-test.git", "user", "test"),
            ("git+https://github.com/org/ansible.prefix.name.git", "org", "prefix.name"),
            # Malformed URLs (fallback behavior)
            ("invalid-url", "", ""),
            ("https://example.com", "unknown", "example.com"),  # Fallback extracts from path
        ],
    )
    def test_parses_collection_names_correctly(
        self,
        git_url: str,
        expected_namespace: str,
        expected_name: str,
    ) -> None:
        """Test that collection names are correctly parsed from Git URLs.

        Args:
            git_url: The Git URL to parse
            expected_namespace: Expected namespace
            expected_name: Expected collection name
        """
        namespace, name = parse_git_url_collection_name(git_url)
        assert namespace == expected_namespace
        assert name == expected_name


class TestParseCollectionRequestGitUrl:
    """Test parse_collection_request with Git URLs."""

    def test_parses_git_url_without_dependencies(
        self,
        tmp_path: Path,
        output: Output,
    ) -> None:
        """Test parsing a Git URL without optional dependencies.

        Args:
            tmp_path: Temporary directory fixture
            output: Output fixture
        """
        config = Config(
            args=Namespace(),
            term_features=TermFeatures(color=False, links=False),
            output=output,
        )
        git_url = "git+https://github.com/redhat-cop/ansible.mcp_builder.git"

        collection = parse_collection_request(
            string=git_url,
            config=config,
            output=output,
        )

        assert collection.original == git_url
        assert not collection.local
        assert collection.cnamespace == "redhat_cop"
        assert collection.cname == "mcp_builder"
        assert collection.csource == [git_url]
        assert collection.opt_deps == ""
        assert collection.specifier == ""
        assert collection.path == Path()

    def test_parses_git_url_with_dependencies(
        self,
        tmp_path: Path,
        output: Output,
    ) -> None:
        """Test parsing a Git URL with optional dependencies.

        Args:
            tmp_path: Temporary directory fixture
            output: Output fixture
        """
        config = Config(
            args=Namespace(),
            term_features=TermFeatures(color=False, links=False),
            output=output,
        )
        git_url_with_deps = "git+https://github.com/user/collection.git[dev,test]"

        collection = parse_collection_request(
            string=git_url_with_deps,
            config=config,
            output=output,
        )

        assert collection.original == git_url_with_deps
        assert not collection.local
        assert collection.cnamespace == "user"
        assert collection.cname == "collection"
        assert collection.csource == ["git+https://github.com/user/collection.git"]
        assert collection.opt_deps == "dev,test"
        assert collection.specifier == ""
        assert collection.path == Path()

    @pytest.mark.parametrize(
        "git_url",
        [
            "git+https://github.com/ansible/community.general.git",
            "https://gitlab.com/user/collection.git",
            "git@github.com:org/ansible-test.git",
            "git+ssh://git@git.example.com/team/collection.git",
        ],
    )
    def test_handles_various_git_url_formats(
        self,
        git_url: str,
        tmp_path: Path,
        output: Output,
    ) -> None:
        """Test that various Git URL formats are handled correctly.

        Args:
            git_url: The Git URL to test
            tmp_path: Temporary directory fixture
            output: Output fixture
        """
        config = Config(
            args=Namespace(),
            term_features=TermFeatures(color=False, links=False),
            output=output,
        )
        collection = parse_collection_request(
            string=git_url,
            config=config,
            output=output,
        )

        assert collection.original == git_url
        assert not collection.local
        assert collection.csource == [git_url]
        assert collection.cnamespace != ""  # Should parse some namespace
        assert collection.cname != ""  # Should parse some name

    def test_git_url_takes_precedence_over_local_path(
        self,
        tmp_path: Path,
        output: Output,
    ) -> None:
        """Test that Git URL detection takes precedence over local path checking.

        Even if a Git URL happens to match a local path name, it should be
        treated as a Git URL, not a local collection.

        Args:
            tmp_path: Temporary directory fixture
            output: Output fixture
        """
        config = Config(
            args=Namespace(),
            term_features=TermFeatures(color=False, links=False),
            output=output,
        )
        # Create a local directory that looks like a Git URL
        git_url_dir = tmp_path / "git+https:"
        git_url_dir.mkdir(parents=True)

        git_url = "git+https://github.com/user/collection.git"

        collection = parse_collection_request(
            string=git_url,
            config=config,
            output=output,
        )

        # Should be treated as Git URL, not local path
        assert not collection.local
        assert collection.csource == [git_url]

    def test_mixed_collection_types_in_installer_flow(
        self,
        tmp_path: Path,
        output: Output,
    ) -> None:
        """Test that Git URLs work alongside other collection types.

        This simulates the installer flow where multiple collection types
        might be specified together.

        Args:
            tmp_path: Temporary directory fixture
            output: Output fixture
        """
        config = Config(
            args=Namespace(),
            term_features=TermFeatures(color=False, links=False),
            output=output,
        )
        # Create a local collection directory
        local_collection = tmp_path / "local_collection"
        local_collection.mkdir()
        galaxy_yml = local_collection / "galaxy.yml"
        galaxy_yml.write_text("""
namespace: test
name: local
version: 1.0.0
""")

        # Test different collection specifier types
        specifiers = [
            "community.general",  # Galaxy collection
            str(local_collection),  # Local collection
            "git+https://github.com/user/git_collection.git",  # Git URL
        ]

        collections = []
        for spec in specifiers:
            collection = parse_collection_request(
                string=spec,
                config=config,
                output=output,
            )
            collections.append(collection)

        # Verify each collection type is handled correctly
        galaxy_collection = collections[0]
        assert not galaxy_collection.local
        assert galaxy_collection.cnamespace == "community"
        assert galaxy_collection.cname == "general"
        assert galaxy_collection.csource == []

        local_collection_obj = collections[1]
        assert local_collection_obj.local
        assert local_collection_obj.cnamespace == "test"
        assert local_collection_obj.cname == "local"

        git_collection = collections[2]
        assert not git_collection.local
        assert git_collection.cnamespace == "user"
        assert git_collection.cname == "git_collection"
        assert git_collection.csource == ["git+https://github.com/user/git_collection.git"]
