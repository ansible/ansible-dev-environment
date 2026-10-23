"""Tests for Git metadata in editable collection installs."""

from __future__ import annotations

import shutil
import subprocess

from typing import TYPE_CHECKING

from ansible_dev_environment.arg_parser import parse
from ansible_dev_environment.config import Config
from ansible_dev_environment.subcommands.installer import Installer
from tests.unit.test_installer_editable import _make_installer, _make_mock_collection


if TYPE_CHECKING:
    from pathlib import Path

    import pytest

    from ansible_dev_environment.output import Output


def test_editable_seeds_git_file_when_git_present(
    tmp_path: Path,
    installable_local_collection: Path,
    monkeypatch: pytest.MonkeyPatch,
    output: Output,
) -> None:
    """Test that a regular Git repository remains recognized after installation.

    Args:
        tmp_path: A temporary directory.
        installable_local_collection: The installable_local_collection fixture.
        monkeypatch: The monkeypatch fixture.
        output: The output fixture.
    """
    subprocess.run(
        ["git", "init"],
        cwd=installable_local_collection,
        check=True,
        capture_output=True,
    )
    venv_path = tmp_path / "venv"
    monkeypatch.setattr(
        "sys.argv",
        [
            "ade",
            "install",
            "--editable",
            str(installable_local_collection),
            "--venv",
            str(venv_path),
            "-vvv",
        ],
    )
    args = parse()
    config = Config(args=args, output=output, term_features=output.term_features)
    config.init()
    Installer(config=config, output=config._output).run()

    collection_site_pkg = config.site_pkg_collections_path / "ansible" / "posix"
    dest_git = collection_site_pkg / ".git"
    assert dest_git.is_file(), ".git should be a gitdir file in the editable install"
    assert not dest_git.is_symlink()
    assert dest_git.read_text(encoding="utf-8").startswith("gitdir:")
    subprocess.run(
        ["git", "rev-parse", "--git-dir"],
        cwd=collection_site_pkg,
        check=True,
        capture_output=True,
        text=True,
    )


def test_editable_no_git_file_when_no_git(
    tmp_path: Path,
    installable_local_collection: Path,
    monkeypatch: pytest.MonkeyPatch,
    output: Output,
) -> None:
    """Test that no .git file is created when the source has no .git.

    Args:
        tmp_path: A temporary directory.
        installable_local_collection: The installable_local_collection fixture.
        monkeypatch: The monkeypatch fixture.
        output: The output fixture.
    """
    assert not (installable_local_collection / ".git").exists()
    venv_path = tmp_path / "venv"
    monkeypatch.setattr(
        "sys.argv",
        [
            "ade",
            "install",
            "--editable",
            str(installable_local_collection),
            "--venv",
            str(venv_path),
            "-vvv",
        ],
    )
    args = parse()
    config = Config(args=args, output=output, term_features=output.term_features)
    config.init()
    Installer(config=config, output=config._output).run()

    collection_site_pkg = config.site_pkg_collections_path / "ansible" / "posix"
    assert not (collection_site_pkg / ".git").exists(), (
        ".git should not exist in site-packages when source has no .git"
    )


def test_editable_seeds_git_file_for_worktree(
    tmp_path: Path,
    installable_local_collection: Path,
    monkeypatch: pytest.MonkeyPatch,
    output: Output,
) -> None:
    """Test that a real worktree remains recognizable from the editable install.

    Args:
        tmp_path: A temporary directory.
        installable_local_collection: The installable_local_collection fixture.
        monkeypatch: The monkeypatch fixture.
        output: The output fixture.
    """
    # Commit the fixture in a source repo, then recreate the fixture as an actual
    # linked worktree so Git provides realistic worktree metadata.
    repo_path = tmp_path / "repo"
    shutil.copytree(installable_local_collection, repo_path)
    subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "add", "."],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )
    shutil.rmtree(installable_local_collection)
    subprocess.run(  # noqa: S603 - the worktree path is the pytest temporary directory
        [
            "git",
            "worktree",
            "add",
            "--detach",
            str(installable_local_collection),
            "HEAD",
        ],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )
    source_git = installable_local_collection / ".git"
    assert source_git.is_file()
    source_gitdir = source_git.read_text(encoding="utf-8").strip().removeprefix("gitdir: ")
    source_gitdir_path = (installable_local_collection / source_gitdir).resolve()
    assert (source_gitdir_path / "HEAD").is_file()
    assert (source_gitdir_path / "commondir").is_file()

    venv_path = tmp_path / "venv"
    monkeypatch.setattr(
        "sys.argv",
        [
            "ade",
            "install",
            "--editable",
            str(installable_local_collection),
            "--venv",
            str(venv_path),
            "-vvv",
        ],
    )
    args = parse()
    config = Config(args=args, output=output, term_features=output.term_features)
    config.init()
    Installer(config=config, output=config._output).run()

    collection_site_pkg = config.site_pkg_collections_path / "ansible" / "posix"
    dest_git = collection_site_pkg / ".git"
    assert dest_git.exists(), ".git file should exist in the editable install"
    assert not dest_git.is_symlink(), ".git should be a file, not a symlink, for worktrees"
    content = dest_git.read_text(encoding="utf-8").strip()
    assert content.startswith("gitdir:")
    written_gitdir = content[len("gitdir:") :].strip()
    assert source_gitdir_path.is_absolute()
    assert written_gitdir == str(source_gitdir_path)
    subprocess.run(
        ["git", "rev-parse", "--git-dir"],
        cwd=collection_site_pkg,
        check=True,
        capture_output=True,
        text=True,
    )


def test_seed_git_entry_skips_existing_directory(
    tmp_path: Path,
    installable_local_collection: Path,
    monkeypatch: pytest.MonkeyPatch,
    output: Output,
) -> None:
    """Test that _seed_git_entry does nothing when a real .git already exists at dest.

    Args:
        tmp_path: A temporary directory.
        installable_local_collection: The installable_local_collection fixture.
        monkeypatch: The monkeypatch fixture.
        output: The output fixture.
    """
    (installable_local_collection / ".git").mkdir()
    installer = _make_installer(tmp_path, installable_local_collection, monkeypatch, output)
    collection = _make_mock_collection(installer._config, installable_local_collection)

    # Place a real directory at dest to simulate a pre-existing non-symlink .git.
    # _make_installer may have seeded a gitdir file; replace it with a real dir.
    dest_git = collection.site_pkg_path / ".git"
    if dest_git.is_file() or dest_git.is_symlink():
        dest_git.unlink()
    dest_git.mkdir(exist_ok=True)
    sentinel = dest_git / "sentinel"
    sentinel.write_text("do not touch")

    installer._seed_git_entry(collection=collection)

    # The pre-existing directory must be untouched
    assert dest_git.is_dir()
    assert not dest_git.is_symlink()
    assert sentinel.read_text() == "do not touch"


def test_seed_git_skips_unknown_git_file_format(
    tmp_path: Path,
    installable_local_collection: Path,
    monkeypatch: pytest.MonkeyPatch,
    output: Output,
) -> None:
    """Test that unknown .git file content is skipped with a warning.

    Args:
        tmp_path: A temporary directory.
        installable_local_collection: The installable_local_collection fixture.
        monkeypatch: The monkeypatch fixture.
        output: The output fixture.
    """
    # Write a .git file with content that does not start with "gitdir:"
    (installable_local_collection / ".git").write_text("unknown content\n", encoding="utf-8")
    installer = _make_installer(tmp_path, installable_local_collection, monkeypatch, output)
    collection = _make_mock_collection(installer._config, installable_local_collection)

    dest_git = collection.site_pkg_path / ".git"
    if dest_git.exists() or dest_git.is_symlink():
        dest_git.unlink()

    warnings_before = output.call_count["warning"]
    installer._seed_git_entry(collection=collection)

    assert not dest_git.exists()
    assert not dest_git.is_symlink()
    assert output.call_count["warning"] == warnings_before + 1


def test_seed_git_skips_invalid_worktree_gitdir(
    tmp_path: Path,
    installable_local_collection: Path,
    monkeypatch: pytest.MonkeyPatch,
    output: Output,
) -> None:
    """Test that an invalid worktree gitdir is skipped with a warning.

    Args:
        tmp_path: A temporary directory.
        installable_local_collection: The installable_local_collection fixture.
        monkeypatch: The monkeypatch fixture.
        output: The output fixture.
    """
    (installable_local_collection / ".git").write_text(
        "gitdir: missing-worktree-metadata\n",
        encoding="utf-8",
    )
    installer = _make_installer(tmp_path, installable_local_collection, monkeypatch, output)
    collection = _make_mock_collection(installer._config, installable_local_collection)
    dest_git = collection.site_pkg_path / ".git"
    if dest_git.exists() or dest_git.is_symlink():
        dest_git.unlink()

    warnings_before = output.call_count["warning"]
    installer._seed_git_entry(collection=collection)

    assert not dest_git.exists()
    assert not dest_git.is_symlink()
    assert output.call_count["warning"] == warnings_before + 1


def test_seed_git_skips_dangling_source_git_symlink(
    tmp_path: Path,
    installable_local_collection: Path,
    monkeypatch: pytest.MonkeyPatch,
    output: Output,
) -> None:
    """Test that a dangling source .git symlink is skipped with a warning.

    Args:
        tmp_path: A temporary directory.
        installable_local_collection: The installable_local_collection fixture.
        monkeypatch: The monkeypatch fixture.
        output: The output fixture.
    """
    (installable_local_collection / ".git").symlink_to(tmp_path / "missing-gitdir")
    installer = _make_installer(tmp_path, installable_local_collection, monkeypatch, output)
    collection = _make_mock_collection(installer._config, installable_local_collection)
    dest_git = collection.site_pkg_path / ".git"
    if dest_git.exists() or dest_git.is_symlink():
        dest_git.unlink()

    warnings_before = output.call_count["warning"]
    installer._seed_git_entry(collection=collection)

    assert not dest_git.exists()
    assert not dest_git.is_symlink()
    assert output.call_count["warning"] == warnings_before + 1


def test_seed_git_handles_valid_source_git_symlink(
    tmp_path: Path,
    installable_local_collection: Path,
    monkeypatch: pytest.MonkeyPatch,
    output: Output,
) -> None:
    """Test that a valid source .git symlink resolves to a gitdir stub.

    Args:
        tmp_path: A temporary directory.
        installable_local_collection: The installable_local_collection fixture.
        monkeypatch: The monkeypatch fixture.
        output: The output fixture.
    """
    repo_path = tmp_path / "metadata-repo"
    repo_path.mkdir()
    subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)
    source_git = installable_local_collection / ".git"
    source_git.symlink_to(repo_path / ".git", target_is_directory=True)

    installer = _make_installer(tmp_path, installable_local_collection, monkeypatch, output)
    collection = _make_mock_collection(installer._config, installable_local_collection)
    dest_git = collection.site_pkg_path / ".git"

    assert dest_git.is_file()
    assert not dest_git.is_symlink()
    assert dest_git.read_text(encoding="utf-8").strip() == f"gitdir: {repo_path / '.git'}"


def test_seed_git_worktree_stub_updates_when_gitdir_changes(
    tmp_path: Path,
    installable_local_collection: Path,
    monkeypatch: pytest.MonkeyPatch,
    output: Output,
) -> None:
    """Test that a seeded gitdir stub updates when the source target changes.

    Args:
        tmp_path: A temporary directory.
        installable_local_collection: The installable_local_collection fixture.
        monkeypatch: The monkeypatch fixture.
        output: The output fixture.
    """
    gitdir_a = tmp_path / "repo_a" / ".git"
    gitdir_a.parent.mkdir()
    subprocess.run(
        ["git", "init"],
        cwd=gitdir_a.parent,
        check=True,
        capture_output=True,
    )
    gitdir_b = tmp_path / "repo_b" / ".git"
    gitdir_b.parent.mkdir()
    subprocess.run(
        ["git", "init"],
        cwd=gitdir_b.parent,
        check=True,
        capture_output=True,
    )
    source_git = installable_local_collection / ".git"
    source_git.write_text(f"gitdir: {gitdir_a}\n", encoding="utf-8")

    installer = _make_installer(
        tmp_path,
        installable_local_collection,
        monkeypatch,
        output,
    )
    collection = _make_mock_collection(installer._config, installable_local_collection)
    dest_git = collection.site_pkg_path / ".git"

    assert dest_git.is_file()
    assert not dest_git.is_symlink()
    assert dest_git.read_text(encoding="utf-8").strip() == f"gitdir: {gitdir_a}"

    source_git.write_text(f"gitdir: {gitdir_b}\n", encoding="utf-8")
    # A full reinstall removes the previous site-packages directory, including
    # its regular .git file, before seeding the updated source target.
    installer.run()

    assert dest_git.is_file()
    assert not dest_git.is_symlink()
    assert dest_git.read_text(encoding="utf-8").strip() == f"gitdir: {gitdir_b}"
