"""Tests for Automation Hub / galaxy.cfg handling during install (AAP-48435)."""

from __future__ import annotations

import builtins
import json
import subprocess

from argparse import Namespace
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest
import yaml

from ansible_dev_environment.cli import Cli
from ansible_dev_environment.collection import Collection
from ansible_dev_environment.config import Config
from ansible_dev_environment.subcommands.installer import (
    ACCESS_TOKEN_ERROR,
    Installer,
    _installed_collection_version,
    galaxy_dependency_specs,
    parse_galaxy_collection_spec,
)


if TYPE_CHECKING:
    from pathlib import Path

    from ansible_dev_environment.output import Output
    from ansible_dev_environment.utils import JSONVal


def _make_config(tmp_path: Path, output: Output, *, ansible_cfg: Path | None = None) -> Config:
    """Build a Config with paths suitable for installer unit tests.

    Args:
        tmp_path: Temporary directory.
        output: Output fixture.
        ansible_cfg: Optional trusted ansible.cfg path.

    Returns:
        Config instance with site packages and venv paths prepared.
    """
    venv = tmp_path / "venv"
    site_pkg = venv / "lib" / "python3.13" / "site-packages"
    site_pkg.mkdir(parents=True)
    (site_pkg / "ansible_collections").mkdir()
    (venv / "bin").mkdir(parents=True)
    (venv / "bin" / "ansible-galaxy").touch()

    args = Namespace(
        verbose=0,
        venv=str(venv),
        editable=False,
        seed=False,
        subcommand="install",
        collection_specifier=None,
        requirement=None,
        cpi=False,
        uv=False,
    )
    config = Config(args=args, output=output, term_features=output.term_features)
    config.site_pkg_path = site_pkg
    config.venv_interpreter = venv / "bin" / "python"
    config.ansible_cfg = ansible_cfg
    return config


def _make_local_collection(
    config: Config,
    collection_path: Path,
    *,
    dependencies: dict[str, str] | None = None,
) -> Collection:
    """Create a local Collection with galaxy.yml and a fake built tarball.

    Args:
        config: Application config.
        collection_path: Path for the local collection sources.
        dependencies: Optional galaxy.yml dependencies mapping.

    Returns:
        Collection ready for _install_local_collection.
    """
    collection_path.mkdir(parents=True, exist_ok=True)
    galaxy: dict[str, object] = {
        "namespace": "infra",
        "name": "demo",
        "version": "1.0.0",
        "readme": "README.md",
        "authors": ["tester"],
    }
    if dependencies is not None:
        galaxy["dependencies"] = dependencies
    (collection_path / "galaxy.yml").write_text(yaml.dump(galaxy), encoding="utf-8")
    (collection_path / "README.md").write_text("demo", encoding="utf-8")

    collection = Collection(
        config=config,
        path=collection_path,
        opt_deps="",
        local=True,
        cnamespace="infra",
        cname="demo",
        csource=[],
        specifier="",
        original=str(collection_path),
    )
    # Pre-create build dir artifacts so install does not need a real galaxy build/copy.
    collection.build_dir.mkdir(parents=True, exist_ok=True)
    (collection.build_dir / "infra-demo-1.0.0.tar.gz").write_text("fake", encoding="utf-8")
    (collection.build_dir / "galaxy.yml").write_text(yaml.dump(galaxy), encoding="utf-8")
    return collection


def _write_installed_collection_manifest(
    config: Config,
    namespace: str,
    name: str,
    version: str,
) -> None:
    """Place a collection MANIFEST.json under the test site-packages tree.

    Args:
        config: Application config.
        namespace: Collection namespace.
        name: Collection name.
        version: Installed collection version.
    """
    collection_dir = config.site_pkg_collections_path / namespace / name
    collection_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "collection_info": {
            "namespace": namespace,
            "name": name,
            "version": version,
            "dependencies": {},
        },
    }
    (collection_dir / "MANIFEST.json").write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )


def test_parse_galaxy_collection_spec() -> None:
    """Test splitting ansible-galaxy collection specs."""
    assert parse_galaxy_collection_spec("ansible.posix") == ("ansible.posix", None)
    assert parse_galaxy_collection_spec("ansible.posix:>=1.0.0,<2.0.0") == (
        "ansible.posix",
        ">=1.0.0,<2.0.0",
    )
    assert parse_galaxy_collection_spec("ansible.posix:") == ("ansible.posix", None)


def test_installed_collection_version() -> None:
    """Test reading versions from collected manifest data."""
    installed: dict[str, dict[str, JSONVal]] = {
        "ansible.posix": {"collection_info": {"version": "1.5.0"}},
    }
    assert _installed_collection_version(installed, "ansible.posix") == "1.5.0"
    assert _installed_collection_version(installed, "missing") is None
    assert _installed_collection_version({"ansible.posix": {}}, "ansible.posix") is None
    assert (
        _installed_collection_version(
            {"ansible.posix": {"collection_info": {"version": 1}}},
            "ansible.posix",
        )
        is None
    )


def test_dependency_spec_satisfied(tmp_path: Path, output: Output) -> None:
    """Test galaxy.yml dependency satisfaction against installed manifests.

    Args:
        tmp_path: Temporary directory.
        output: Output fixture.
    """
    config = _make_config(tmp_path, output, ansible_cfg=None)
    installer = Installer(config=config, output=output)
    installed: dict[str, dict[str, JSONVal]] = {
        "ansible.posix": {"collection_info": {"version": "1.5.0"}},
    }
    assert installer._dependency_spec_satisfied("ansible.posix:>=1.0.0,<2.0.0", installed)
    assert installer._dependency_spec_satisfied("ansible.posix", installed)
    assert installer._dependency_spec_satisfied("ansible.posix:*", installed)
    assert not installer._dependency_spec_satisfied("ansible.posix:>=2.0.0", installed)
    assert installer._dependency_spec_satisfied("ansible.posix:not-a-specifier", installed)
    assert not installer._dependency_spec_satisfied("missing.collection:>=1.0.0", installed)


def test_collection_dependency_specs_edge_cases(
    tmp_path: Path,
    output: Output,
) -> None:
    """Test reading galaxy.yml dependencies handles missing or invalid files.

    Args:
        tmp_path: Temporary directory.
        output: Output fixture.
    """
    config = _make_config(tmp_path, output, ansible_cfg=None)
    installer = Installer(config=config, output=output)

    missing_galaxy = Collection(
        config=config,
        path=tmp_path / "no.galaxy",
        opt_deps="",
        local=True,
        cnamespace="infra",
        cname="demo",
        csource=[],
        specifier="",
        original=str(tmp_path / "no.galaxy"),
    )
    missing_galaxy.path.mkdir(parents=True)
    assert not installer._collection_dependency_specs(missing_galaxy)

    bad_yaml_path = tmp_path / "bad.yaml"
    bad_yaml_path.mkdir(parents=True)
    (bad_yaml_path / "galaxy.yml").write_text(":\n  bad: [\n", encoding="utf-8")
    bad_yaml = Collection(
        config=config,
        path=bad_yaml_path,
        opt_deps="",
        local=True,
        cnamespace="infra",
        cname="demo",
        csource=[],
        specifier="",
        original=str(bad_yaml_path),
    )
    assert not installer._collection_dependency_specs(bad_yaml)

    list_galaxy_path = tmp_path / "list.galaxy"
    list_galaxy_path.mkdir(parents=True)
    (list_galaxy_path / "galaxy.yml").write_text("- not a mapping\n", encoding="utf-8")
    list_galaxy = Collection(
        config=config,
        path=list_galaxy_path,
        opt_deps="",
        local=True,
        cnamespace="infra",
        cname="demo",
        csource=[],
        specifier="",
        original=str(list_galaxy_path),
    )
    assert not installer._collection_dependency_specs(list_galaxy)


def test_install_missing_collection_dependencies_no_specs(
    tmp_path: Path,
    output: Output,
) -> None:
    """Empty dependency list short-circuits without calling ansible-galaxy.

    Args:
        tmp_path: Temporary directory.
        output: Output fixture.
    """
    config = _make_config(tmp_path, output, ansible_cfg=None)
    installer = Installer(config=config, output=output)
    assert not installer._install_missing_collection_dependencies([])


def test_dependency_specs_to_install_partition(
    tmp_path: Path,
    output: Output,
) -> None:
    """Partition dependency specs using manifests from the venv.

    Args:
        tmp_path: Temporary directory.
        output: Output fixture.
    """
    config = _make_config(tmp_path, output, ansible_cfg=None)
    _write_installed_collection_manifest(config, "ansible", "posix", "1.5.0")
    installer = Installer(config=config, output=output)

    specs_to_install, satisfied = installer._dependency_specs_to_install(
        [
            "ansible.posix:>=1.0.0,<2.0.0",
            "missing.collection:>=1.0.0",
        ],
    )
    assert satisfied == ["ansible.posix"]
    assert specs_to_install == ["missing.collection:>=1.0.0"]


def test_dependency_specs_to_install_cache_only_manifest(
    tmp_path: Path,
    output: Output,
) -> None:
    """Partition recognizes manifests in venv_cache_dir (editable installs).

    After an editable install, site-packages has namespace/name/ but no
    MANIFEST.json; collect_manifests() reads from venv_cache_dir instead.
    _dependency_specs_to_install must still treat this as satisfied.

    Args:
        tmp_path: Temporary directory.
        output: Output fixture.
    """
    config = _make_config(tmp_path, output, ansible_cfg=None)

    # Create the collection directory under site-packages *without* MANIFEST.json
    collection_dir = config.site_pkg_collections_path / "ansible" / "posix"
    collection_dir.mkdir(parents=True, exist_ok=True)

    # Write manifest only to venv_cache_dir (editable-install path)
    cache_manifest_dir = config.venv_cache_dir / "ansible.posix"
    cache_manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "collection_info": {
            "namespace": "ansible",
            "name": "posix",
            "version": "1.5.0",
            "dependencies": {},
        },
    }
    (cache_manifest_dir / "MANIFEST.json").write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )

    installer = Installer(config=config, output=output)
    specs_to_install, satisfied = installer._dependency_specs_to_install(
        ["ansible.posix:>=1.0.0,<2.0.0", "missing.collection:>=1.0.0"],
    )
    assert "ansible.posix" in satisfied
    assert "ansible.posix:>=1.0.0,<2.0.0" not in specs_to_install
    assert specs_to_install == ["missing.collection:>=1.0.0"]


def test_dependency_spec_satisfied_without_packaging(
    tmp_path: Path,
    output: Output,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Version checks fail closed when packaging is unavailable.

    Args:
        tmp_path: Temporary directory.
        output: Output fixture.
        monkeypatch: Pytest monkeypatch fixture.
    """
    real_import = builtins.__import__

    def block_packaging(name: str, *args: object, **kwargs: object) -> object:
        if name.startswith("packaging"):
            raise ImportError(name)
        return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(builtins, "__import__", block_packaging)
    config = _make_config(tmp_path, output, ansible_cfg=None)
    installer = Installer(config=config, output=output)
    installed: dict[str, dict[str, JSONVal]] = {
        "ansible.posix": {"collection_info": {"version": "1.5.0"}},
    }
    assert not installer._dependency_spec_satisfied("ansible.posix:>=1.0.0", installed)


def test_galaxy_dependency_specs() -> None:
    """Test conversion of galaxy.yml dependencies to ansible-galaxy specs."""
    assert not galaxy_dependency_specs(None)
    assert not galaxy_dependency_specs("not-a-dict")
    assert not galaxy_dependency_specs({})
    assert galaxy_dependency_specs(
        {
            "ansible.posix": ">=1.0.0",
            "kubernetes.core": "*",
            "redhat.openshift": None,
            "": "1.0.0",
        },
    ) == [
        "ansible.posix:>=1.0.0",
        "kubernetes.core",
        "redhat.openshift",
    ]


def test_galaxy_env_includes_ansible_config(tmp_path: Path, output: Output) -> None:
    """Trusted ansible.cfg is pinned into galaxy subprocess env.

    Args:
        tmp_path: Temporary directory.
        output: Output fixture.
    """
    cfg = tmp_path / "ansible.cfg"
    cfg.write_text("[defaults]\ncollections_path = .\n", encoding="utf-8")
    config = _make_config(tmp_path, output, ansible_cfg=cfg)
    installer = Installer(config=config, output=output)

    env = installer._galaxy_env()
    assert env["ANSIBLE_CONFIG"] == str(cfg)
    assert env["ANSIBLE_GALAXY_COLLECTIONS_PATH_WARNING"] == "0"


def test_galaxy_env_omits_ansible_config_when_unset(tmp_path: Path, output: Output) -> None:
    """ANSIBLE_CONFIG is omitted when no trusted cfg was selected.

    Args:
        tmp_path: Temporary directory.
        output: Output fixture.
    """
    config = _make_config(tmp_path, output, ansible_cfg=None)
    installer = Installer(config=config, output=output)

    env = installer._galaxy_env()
    assert "ANSIBLE_CONFIG" not in env


def test_local_install_installs_deps_then_uses_no_deps(
    tmp_path: Path,
    output: Output,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Local install installs galaxy.yml deps then the tarball with --no-deps.

    Args:
        tmp_path: Temporary directory.
        output: Output fixture.
        monkeypatch: Pytest monkeypatch fixture.
    """
    cfg = tmp_path / "ansible.cfg"
    cfg.write_text("[defaults]\ncollections_path = .\n", encoding="utf-8")
    config = _make_config(tmp_path, output, ansible_cfg=cfg)
    collection = _make_local_collection(
        config,
        tmp_path / "infra.demo",
        dependencies={
            "ansible.posix": ">=1.0.0",
            "redhat.openshift": ">=4.0.2",
        },
    )
    installer = Installer(config=config, output=output)

    calls: list[dict[str, Any]] = []

    def mock_subprocess_run(**kwargs: Any) -> subprocess.CompletedProcess[str]:  # noqa: ANN401
        calls.append(kwargs)
        command = kwargs["command"]
        if "collection build" in command:
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        if "ansible.posix" in command:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=(
                    "ansible.posix:1.0.0 was installed successfully\n"
                    "redhat.openshift:4.0.2 was installed successfully\n"
                ),
                stderr="",
            )
        collection.site_pkg_path.mkdir(parents=True, exist_ok=True)
        return subprocess.CompletedProcess(
            command,
            0,
            stdout="infra.demo:1.0.0 was installed successfully\n",
            stderr="",
        )

    monkeypatch.setattr(
        "ansible_dev_environment.subcommands.installer.subprocess_run",
        mock_subprocess_run,
    )
    monkeypatch.setattr(installer, "_copy_repo_files", MagicMock())

    installer._install_local_collection(collection)

    galaxy_calls = [c for c in calls if "ansible-galaxy" in c["command"]]
    build_call, deps_call, local_call = galaxy_calls
    assert "collection build" in build_call["command"]
    assert "install 'ansible.posix:>=1.0.0' 'redhat.openshift:>=4.0.2'" in deps_call["command"]
    assert f"-p {config.site_pkg_path}" in deps_call["command"]
    assert deps_call["env"]["ANSIBLE_CONFIG"] == str(cfg)
    assert "--no-deps" not in deps_call["command"]

    assert str(collection.build_dir / "infra-demo-1.0.0.tar.gz") in local_call["command"]
    assert "--no-deps" in local_call["command"]
    assert local_call["env"]["ANSIBLE_CONFIG"] == str(cfg)


def test_local_install_reinstalls_version_mismatched_dependency(
    tmp_path: Path,
    output: Output,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Local install re-runs ansible-galaxy when an installed dep is too old.

    Args:
        tmp_path: Temporary directory.
        output: Output fixture.
        monkeypatch: Pytest monkeypatch fixture.
    """
    config = _make_config(tmp_path, output, ansible_cfg=None)
    _write_installed_collection_manifest(config, "ansible", "posix", "0.9.0")
    collection = _make_local_collection(
        config,
        tmp_path / "infra.demo",
        dependencies={"ansible.posix": ">=1.0.0,<2.0.0"},
    )
    installer = Installer(config=config, output=output)

    calls: list[dict[str, Any]] = []

    def mock_subprocess_run(**kwargs: Any) -> subprocess.CompletedProcess[str]:  # noqa: ANN401
        calls.append(kwargs)
        command = kwargs["command"]
        if "collection build" in command:
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        collection.site_pkg_path.mkdir(parents=True, exist_ok=True)
        return subprocess.CompletedProcess(
            command,
            0,
            stdout="infra.demo:1.0.0 was installed successfully\n",
            stderr="",
        )

    monkeypatch.setattr(
        "ansible_dev_environment.subcommands.installer.subprocess_run",
        mock_subprocess_run,
    )
    monkeypatch.setattr(installer, "_copy_repo_files", MagicMock())

    installer._install_local_collection(collection)

    galaxy_installs = [
        c
        for c in calls
        if "collection install" in c["command"] and "ansible-galaxy" in c["command"]
    ]
    deps_call, local_call = galaxy_installs
    assert "ansible.posix" in deps_call["command"]
    assert "--no-deps" in local_call["command"]


def test_local_install_skips_already_installed_dependencies(
    tmp_path: Path,
    output: Output,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Local install does not re-install galaxy.yml deps already in the venv.

    Args:
        tmp_path: Temporary directory.
        output: Output fixture.
        monkeypatch: Pytest monkeypatch fixture.
    """
    config = _make_config(tmp_path, output, ansible_cfg=None)
    _write_installed_collection_manifest(config, "ansible", "posix", "1.5.0")
    collection = _make_local_collection(
        config,
        tmp_path / "infra.demo",
        dependencies={"ansible.posix": ">=1.0.0,<2.0.0"},
    )
    installer = Installer(config=config, output=output)

    calls: list[dict[str, Any]] = []

    def mock_subprocess_run(**kwargs: Any) -> subprocess.CompletedProcess[str]:  # noqa: ANN401
        calls.append(kwargs)
        command = kwargs["command"]
        if "collection build" in command:
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        collection.site_pkg_path.mkdir(parents=True, exist_ok=True)
        return subprocess.CompletedProcess(
            command,
            0,
            stdout="infra.demo:1.0.0 was installed successfully\n",
            stderr="",
        )

    monkeypatch.setattr(
        "ansible_dev_environment.subcommands.installer.subprocess_run",
        mock_subprocess_run,
    )
    monkeypatch.setattr(installer, "_copy_repo_files", MagicMock())

    installer._install_local_collection(collection)

    galaxy_installs = [
        c
        for c in calls
        if "collection install" in c["command"] and "ansible-galaxy" in c["command"]
    ]
    assert len(galaxy_installs) == 1
    assert "ansible.posix" not in galaxy_installs[0]["command"]
    assert "--no-deps" in galaxy_installs[0]["command"]


def test_local_install_without_deps_skips_no_deps(
    tmp_path: Path,
    output: Output,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Local install without galaxy.yml deps does not use --no-deps.

    Args:
        tmp_path: Temporary directory.
        output: Output fixture.
        monkeypatch: Pytest monkeypatch fixture.
    """
    config = _make_config(tmp_path, output, ansible_cfg=None)
    collection = _make_local_collection(
        config,
        tmp_path / "infra.demo",
        dependencies={},
    )
    installer = Installer(config=config, output=output)

    calls: list[dict[str, Any]] = []

    def mock_subprocess_run(**kwargs: Any) -> subprocess.CompletedProcess[str]:  # noqa: ANN401
        calls.append(kwargs)
        if "collection install" in kwargs["command"]:
            collection.site_pkg_path.mkdir(parents=True, exist_ok=True)
        return subprocess.CompletedProcess(
            kwargs["command"],
            0,
            stdout="infra.demo:1.0.0 was installed successfully\n",
            stderr="",
        )

    monkeypatch.setattr(
        "ansible_dev_environment.subcommands.installer.subprocess_run",
        mock_subprocess_run,
    )
    monkeypatch.setattr(installer, "_copy_repo_files", MagicMock())

    installer._install_local_collection(collection)

    galaxy_installs = [
        c
        for c in calls
        if "collection install" in c["command"] and "ansible-galaxy" in c["command"]
    ]
    assert len(galaxy_installs) == 1
    assert "--no-deps" not in galaxy_installs[0]["command"]
    assert "ANSIBLE_CONFIG" not in galaxy_installs[0]["env"]


def test_auth_failure_emits_hint(
    tmp_path: Path,
    output: Output,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Access-token failures emit a hint about AH offline tokens and ANSIBLE_CONFIG.

    Args:
        tmp_path: Temporary directory.
        output: Output fixture.
        monkeypatch: Pytest monkeypatch fixture.
        capsys: Pytest capture fixture.
    """
    cfg = tmp_path / "ansible.cfg"
    cfg.write_text("[defaults]\ncollections_path = .\n", encoding="utf-8")
    config = _make_config(tmp_path, output, ansible_cfg=cfg)
    collection = _make_local_collection(
        config,
        tmp_path / "infra.demo",
        dependencies={"ansible.posix": ">=1.0.0"},
    )
    installer = Installer(config=config, output=output)

    def mock_subprocess_run(**kwargs: Any) -> subprocess.CompletedProcess[str]:  # noqa: ANN401
        command = kwargs["command"]
        if "collection build" in command:
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        raise subprocess.CalledProcessError(
            1,
            command,
            output="",
            stderr=f"ERROR! {ACCESS_TOKEN_ERROR} (HTTP Code: 400, Message: Bad Request)\n",
        )

    monkeypatch.setattr(
        "ansible_dev_environment.subcommands.installer.subprocess_run",
        mock_subprocess_run,
    )
    monkeypatch.setattr(installer, "_copy_repo_files", MagicMock())

    with pytest.raises(SystemExit):
        installer._install_local_collection(collection)

    captured = capsys.readouterr()
    assert "Automation Hub authentication failed" in captured.out + captured.err
    assert "ANSIBLE_GALAXY_SERVER_<SERVER>_TOKEN" in captured.out + captured.err
    assert f"ANSIBLE_CONFIG={cfg}" in captured.out + captured.err


def test_cli_assigns_trusted_ansible_cfg(
    tmp_path: Path,
    output: Output,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cli.run copies acfg_trusted onto Config.ansible_cfg.

    Args:
        tmp_path: Temporary directory.
        output: Output fixture.
        monkeypatch: Pytest monkeypatch fixture.
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "sys.argv",
        ["ade", "install", "--no-seed", "--venv", str(tmp_path / "venv")],
    )

    cli = Cli()
    cli.parse_args()
    cli.output = output
    cli.term_features = output.term_features
    cli.args_sanity()
    assert cli.isolation_check() is True
    assert cli.acfg_trusted is not None

    # Avoid running a full install; only exercise Config plumbing.
    monkeypatch.setattr(
        "ansible_dev_environment.subcommands.installer.Installer.run",
        MagicMock(),
    )
    # Config.init creates a venv; let it run then stop before Installer work via mock above.
    with pytest.raises(SystemExit) as exc:
        cli.run()
    assert exc.value.code == 0
    assert cli.config.ansible_cfg == cli.acfg_trusted
