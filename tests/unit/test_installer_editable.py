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
    assert not (collection_site_pkg / ".git").exists()
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
