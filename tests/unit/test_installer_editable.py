"""Test that editable installs exclude virtual environments from symlinking."""

from __future__ import annotations

import shutil
import subprocess

from typing import TYPE_CHECKING

import yaml

from ansible_dev_environment.arg_parser import parse
from ansible_dev_environment.collection import Collection
from ansible_dev_environment.config import Config
from ansible_dev_environment.subcommands.installer import Installer


if TYPE_CHECKING:
    from pathlib import Path

    import pytest

    from ansible_dev_environment.output import Output


def test_editable_excludes_venv_directories(
    tmp_path: Path,
    installable_local_collection: Path,
    monkeypatch: pytest.MonkeyPatch,
    output: Output,
) -> None:
    """Test that all virtual environment directory variants are excluded.

    Args:
        tmp_path: A temporary directory.
        installable_local_collection: The installable_local_collection fixture.
        monkeypatch: The monkeypatch fixture.
        output: The output fixture.
    """
    venv_variants = [".venv", "venv", ".virtualenv", "virtualenv"]
    for dir_name in venv_variants:
        (installable_local_collection / dir_name).mkdir()
        (installable_local_collection / dir_name / "marker.txt").write_text("venv")

    venv_path = tmp_path / "external_venv"

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
    installer = Installer(config=config, output=config._output)
    installer.run()

    collection_site_pkg = config.site_pkg_collections_path / "ansible" / "posix"

    for dir_name in venv_variants:
        assert not (collection_site_pkg / dir_name).exists(), (
            f"{dir_name} should be excluded to avoid recursion"
        )

    assert (collection_site_pkg / "galaxy.yml").exists()


def test_editable_works_with_venv_as_active_environment(
    installable_local_collection: Path,
    monkeypatch: pytest.MonkeyPatch,
    output: Output,
) -> None:
    """Test editable install when using venv inside the collection as active environment.

    This tests the scenario where:
    /path/to/collection/.venv/ <-- venv is here and is the active one

    Args:
        installable_local_collection: The installable_local_collection fixture.
        monkeypatch: The monkeypatch fixture.
        output: The output fixture.
    """
    venv_path = installable_local_collection / ".venv"

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
    installer = Installer(config=config, output=config._output)
    installer.run()

    collection_site_pkg = config.site_pkg_collections_path / "ansible" / "posix"

    assert (collection_site_pkg / "galaxy.yml").exists()
    assert (collection_site_pkg / "galaxy.yml").is_symlink()

    venv_symlink = collection_site_pkg / ".venv"
    assert not venv_symlink.exists(), ".venv should not be symlinked to avoid recursion"


def test_editable_excludes_python_artifacts(
    tmp_path: Path,
    installable_local_collection: Path,
    monkeypatch: pytest.MonkeyPatch,
    output: Output,
) -> None:
    """Test that Python artifacts with extension patterns are excluded.

    Args:
        tmp_path: A temporary directory.
        installable_local_collection: The installable_local_collection fixture.
        monkeypatch: The monkeypatch fixture.
        output: The output fixture.
    """
    (installable_local_collection / "test.pyc").write_text("compiled")
    (installable_local_collection / "test.pyo").write_text("optimized")
    (installable_local_collection / "__pycache__").mkdir()
    (installable_local_collection / ".git").mkdir()

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
    installer = Installer(config=config, output=config._output)
    installer.run()

    collection_site_pkg = config.site_pkg_collections_path / "ansible" / "posix"

    assert not (collection_site_pkg / "test.pyc").exists()
    assert not (collection_site_pkg / "test.pyo").exists()
    assert not (collection_site_pkg / "__pycache__").exists()
    assert (collection_site_pkg / "galaxy.yml").exists()


def test_editable_cleans_up_legacy_symlink(
    tmp_path: Path,
    installable_local_collection: Path,
    monkeypatch: pytest.MonkeyPatch,
    output: Output,
) -> None:
    """Test that old-style single symlink is cleaned up correctly.

    Args:
        tmp_path: A temporary directory.
        installable_local_collection: The installable_local_collection fixture.
        monkeypatch: The monkeypatch fixture.
        output: The output fixture.
    """
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
    installer = Installer(config=config, output=config._output)
    installer.run()

    collection_site_pkg = config.site_pkg_collections_path / "ansible" / "posix"
    assert collection_site_pkg.is_dir()
    assert (collection_site_pkg / "galaxy.yml").is_symlink()

    shutil.rmtree(collection_site_pkg)
    collection_site_pkg.symlink_to(installable_local_collection)
    assert collection_site_pkg.is_symlink()

    args = parse()
    config = Config(args=args, output=output, term_features=output.term_features)
    config.init()
    installer = Installer(config=config, output=config._output)
    installer.run()

    assert collection_site_pkg.is_dir()
    assert not collection_site_pkg.is_symlink()
    assert (collection_site_pkg / "galaxy.yml").is_symlink()


def test_editable_no_items_to_symlink_fails(
    tmp_path: Path,
    installable_local_collection: Path,
    monkeypatch: pytest.MonkeyPatch,
    output: Output,
) -> None:
    """Test that editable install fails when filtered discovery returns no items.

    Args:
        tmp_path: A temporary directory.
        installable_local_collection: The installable_local_collection fixture.
        monkeypatch: The monkeypatch fixture.
        output: The output fixture.

    Raises:
        AssertionError: If SystemExit is not raised as expected.
    """
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
    installer = Installer(config=config, output=config._output)

    original_get_filtered = installer._get_filtered_root_items

    def mock_get_filtered_empty(col: Collection) -> set[str]:
        original_get_filtered(col)
        return set()

    monkeypatch.setattr(installer, "_get_filtered_root_items", mock_get_filtered_empty)

    try:
        installer.run()
        msg = "Expected SystemExit to be raised"
        raise AssertionError(msg)
    except SystemExit:
        pass


def test_editable_uses_git_discovery(
    tmp_path: Path,
    installable_local_collection: Path,
    monkeypatch: pytest.MonkeyPatch,
    output: Output,
) -> None:
    """Test that editable install uses git ls-files when available.

    Args:
        tmp_path: A temporary directory.
        installable_local_collection: The installable_local_collection fixture.
        monkeypatch: The monkeypatch fixture.
        output: The output fixture.
    """
    subprocess.run(
        args=["git", "init"],
        cwd=installable_local_collection,
        check=False,
        capture_output=True,
    )
    subprocess.run(
        args=["git", "add", "--all"],
        cwd=installable_local_collection,
        check=False,
        capture_output=True,
    )

    venv_in_collection = installable_local_collection / ".venv"
    venv_in_collection.mkdir()

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
    installer = Installer(config=config, output=config._output)
    installer.run()

    collection_site_pkg = config.site_pkg_collections_path / "ansible" / "posix"

    assert (collection_site_pkg / "galaxy.yml").exists()
    assert (collection_site_pkg / "galaxy.yml").is_symlink()
    assert not (collection_site_pkg / ".venv").exists()


def test_editable_skips_nonexistent_source_items(
    tmp_path: Path,
    installable_local_collection: Path,
    monkeypatch: pytest.MonkeyPatch,
    output: Output,
) -> None:
    """Test that nonexistent source items are skipped during symlinking.

    Args:
        tmp_path: A temporary directory.
        installable_local_collection: The installable_local_collection fixture.
        monkeypatch: The monkeypatch fixture.
        output: The output fixture.
    """
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
    installer = Installer(config=config, output=config._output)
    installer.run()

    collection_site_pkg = config.site_pkg_collections_path / "ansible" / "posix"
    assert (collection_site_pkg / "plugins").is_symlink()

    plugins_dir = installable_local_collection / "plugins"
    if plugins_dir.exists():
        shutil.rmtree(plugins_dir)

    args = parse()
    config = Config(args=args, output=output, term_features=output.term_features)
    config.init()
    installer = Installer(config=config, output=config._output)
    installer.run()

    assert (collection_site_pkg / "galaxy.yml").exists()
    assert (collection_site_pkg / "galaxy.yml").is_symlink()
    assert not (collection_site_pkg / "plugins").exists()


def test_editable_adds_build_ignore_entries(
    tmp_path: Path,
    installable_local_collection: Path,
    monkeypatch: pytest.MonkeyPatch,
    output: Output,
) -> None:
    """Test that editable install adds .venv, collections, .tox to build_ignore.

    Args:
        tmp_path: A temporary directory.
        installable_local_collection: The installable_local_collection fixture.
        monkeypatch: The monkeypatch fixture.
        output: The output fixture.
    """
    galaxy_file = installable_local_collection / "galaxy.yml"
    galaxy_data = yaml.safe_load(galaxy_file.read_text())
    galaxy_data["build_ignore"] = [".gitignore"]
    yaml.dump(galaxy_data, galaxy_file.open("w"))

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
    installer = Installer(config=config, output=config._output)
    installer.run()

    updated = yaml.safe_load(galaxy_file.read_text())
    build_ignore = updated.get("build_ignore", [])
    assert ".venv" in build_ignore
    assert "collections" in build_ignore
    assert ".tox" in build_ignore
    assert ".gitignore" in build_ignore


def test_editable_build_ignore_idempotent(
    tmp_path: Path,
    installable_local_collection: Path,
    monkeypatch: pytest.MonkeyPatch,
    output: Output,
) -> None:
    """Test that running editable install twice does not duplicate build_ignore entries.

    Args:
        tmp_path: A temporary directory.
        installable_local_collection: The installable_local_collection fixture.
        monkeypatch: The monkeypatch fixture.
        output: The output fixture.
    """
    galaxy_file = installable_local_collection / "galaxy.yml"
    galaxy_data = yaml.safe_load(galaxy_file.read_text())
    galaxy_data["build_ignore"] = [".gitignore", ".venv", "collections", ".tox"]
    yaml.dump(galaxy_data, galaxy_file.open("w"))

    original_content = galaxy_file.read_text()

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
    installer = Installer(config=config, output=config._output)
    installer.run()

    assert galaxy_file.read_text() == original_content


def test_editable_build_ignore_no_existing_section(
    tmp_path: Path,
    installable_local_collection: Path,
    monkeypatch: pytest.MonkeyPatch,
    output: Output,
) -> None:
    """Test that build_ignore section is created when it does not exist.

    Args:
        tmp_path: A temporary directory.
        installable_local_collection: The installable_local_collection fixture.
        monkeypatch: The monkeypatch fixture.
        output: The output fixture.
    """
    galaxy_file = installable_local_collection / "galaxy.yml"
    galaxy_data = yaml.safe_load(galaxy_file.read_text())
    galaxy_data.pop("build_ignore", None)
    yaml.dump(galaxy_data, galaxy_file.open("w"))

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
    installer = Installer(config=config, output=config._output)
    installer.run()

    updated = yaml.safe_load(galaxy_file.read_text())
    build_ignore = updated.get("build_ignore", [])
    assert ".venv" in build_ignore
    assert "collections" in build_ignore
    assert ".tox" in build_ignore


def _make_installer(
    tmp_path: Path,
    installable_local_collection: Path,
    monkeypatch: pytest.MonkeyPatch,
    output: Output,
) -> Installer:
    """Create an Installer instance after a successful run.

    Args:
        tmp_path: A temporary directory.
        installable_local_collection: The installable_local_collection fixture.
        monkeypatch: The monkeypatch fixture.
        output: The output fixture.

    Returns:
        A configured Installer instance.
    """
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
    installer = Installer(config=config, output=config._output)
    installer.run()
    return installer


def _make_mock_collection(
    config: Config,
    installable_local_collection: Path,
) -> Collection:
    """Create a mock Collection pointing at the test collection path.

    Args:
        config: The configuration object.
        installable_local_collection: The collection path.

    Returns:
        A Collection object.
    """
    return Collection(
        config=config,
        path=installable_local_collection,
        opt_deps="",
        local=True,
        cnamespace="ansible",
        cname="posix",
        csource=[],
        specifier="",
        original=".",
    )


def test_editable_build_ignore_skips_missing_galaxy(
    tmp_path: Path,
    installable_local_collection: Path,
    monkeypatch: pytest.MonkeyPatch,
    output: Output,
) -> None:
    """Test that _ensure_build_ignore skips when galaxy.yml does not exist.

    Args:
        tmp_path: A temporary directory.
        installable_local_collection: The installable_local_collection fixture.
        monkeypatch: The monkeypatch fixture.
        output: The output fixture.
    """
    installer = _make_installer(
        tmp_path,
        installable_local_collection,
        monkeypatch,
        output,
    )
    galaxy_file = installable_local_collection / "galaxy.yml"
    galaxy_file.unlink()

    mock_collection = _make_mock_collection(installer._config, installable_local_collection)
    installer._ensure_build_ignore(collection=mock_collection)
    assert not galaxy_file.exists()


def test_editable_build_ignore_skips_invalid_yaml(
    tmp_path: Path,
    installable_local_collection: Path,
    monkeypatch: pytest.MonkeyPatch,
    output: Output,
) -> None:
    """Test that _ensure_build_ignore skips when galaxy.yml has invalid YAML.

    Args:
        tmp_path: A temporary directory.
        installable_local_collection: The installable_local_collection fixture.
        monkeypatch: The monkeypatch fixture.
        output: The output fixture.
    """
    installer = _make_installer(
        tmp_path,
        installable_local_collection,
        monkeypatch,
        output,
    )
    galaxy_file = installable_local_collection / "galaxy.yml"
    galaxy_file.write_text(": [\ninvalid yaml\n")

    mock_collection = _make_mock_collection(installer._config, installable_local_collection)
    installer._ensure_build_ignore(collection=mock_collection)
    assert galaxy_file.read_text() == ": [\ninvalid yaml\n"


def test_editable_build_ignore_skips_empty_yaml(
    tmp_path: Path,
    installable_local_collection: Path,
    monkeypatch: pytest.MonkeyPatch,
    output: Output,
) -> None:
    """Test that _ensure_build_ignore skips when galaxy.yml is empty.

    Args:
        tmp_path: A temporary directory.
        installable_local_collection: The installable_local_collection fixture.
        monkeypatch: The monkeypatch fixture.
        output: The output fixture.
    """
    installer = _make_installer(
        tmp_path,
        installable_local_collection,
        monkeypatch,
        output,
    )
    galaxy_file = installable_local_collection / "galaxy.yml"
    galaxy_file.write_text("")

    mock_collection = _make_mock_collection(installer._config, installable_local_collection)
    installer._ensure_build_ignore(collection=mock_collection)
    assert galaxy_file.read_text() == ""


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
