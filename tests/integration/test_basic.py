"""Basic smoke tests."""

from __future__ import annotations

import json
import re
import sys

from pathlib import Path

import pytest

from ansible_dev_environment.cli import main
from ansible_dev_environment.output import Output
from ansible_dev_environment.utils import TermFeatures, subprocess_run


@pytest.mark.skipif(
    sys.version_info > (3, 12),
    reason="pylibssh issues 3.13, https://github.com/ansible/pylibssh/issues/699",
)
def test_venv(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Basic smoke test.

    Test for a local collection install with optional dependencies

    Args:
        capsys: Capture stdout and stderr
        tmp_path: Temporary directory
        monkeypatch: Pytest monkeypatch
    """
    # disable color for json output
    term_features = TermFeatures(color=False, links=False)
    output = Output(
        log_file=f"/{tmp_path}/ansible-dev-environment.log",
        log_level="INFO",
        log_append="false",
        term_features=term_features,
        verbosity=0,
    )
    command = (
        f"git clone https://github.com/ansible-collections/cisco.nxos.git {tmp_path / 'cisco.nxos'}"
    )
    subprocess_run(
        command=command,
        verbose=True,
        msg="",
        output=output,
    )
    monkeypatch.chdir(tmp_path)

    monkeypatch.setattr(
        "sys.argv",
        [
            "ade",
            "install",
            str(tmp_path / "cisco.nxos[test]"),
            "--venv=venv",
            "--no-ansi",
            "-vvv",
        ],
    )
    with pytest.raises(SystemExit):
        main()

    captured = capsys.readouterr()
    assert "Installed collections include: ansible.netcommon, ansible.utils," in captured.out
    assert "Optional dependencies found" in captured.out
    assert "'pytest-xdist  # from collection user'" in captured.out

    monkeypatch.setattr(
        "sys.argv",
        ["ade", "list", "--venv=venv"],
    )
    with pytest.raises(SystemExit):
        main()
    captured = capsys.readouterr()
    assert "cisco.nxos" in captured.out
    assert "ansible.netcommon" in captured.out
    assert "ansible.utils" in captured.out
    assert "unknown" not in captured.out

    monkeypatch.setattr(
        "sys.argv",
        [
            "ade",
            "uninstall",
            "ansible.utils",
            "--venv=venv",
        ],
    )
    with pytest.raises(SystemExit):
        main()
    captured = capsys.readouterr()
    assert "Removed ansible.utils" in captured.out

    monkeypatch.setattr(
        "sys.argv",
        ["ade", "inspect", "--venv=venv", "--no-ansi"],
    )
    with pytest.raises(SystemExit):
        main()
    captured = capsys.readouterr()
    captured_json = json.loads(captured.out)
    assert "cisco.nxos" in captured_json
    assert "ansible.netcommon" in captured_json
    assert "ansible.utils" not in captured_json

    monkeypatch.setattr(
        "sys.argv",
        ["ade", "check", "--venv=venv"],
    )
    with pytest.raises(SystemExit):
        main()
    captured = capsys.readouterr()
    assert "Collection ansible.netcommon requires ansible.util" in captured.err


def test_non_local(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Install non-local collection.

    Args:
        capsys: Capture stdout and stderr
        tmp_path: Temporary directory
        monkeypatch: Pytest monkeypatch
    """
    monkeypatch.setattr(
        "sys.argv",
        [
            "ade",
            "install",
            "ansible.scm",
            f"--venv={tmp_path / 'venv'}",
        ],
    )
    with pytest.raises(SystemExit):
        main()
    string = "Installed collections include: ansible.scm and ansible.utils"
    captured = capsys.readouterr()
    assert string in captured.out
    monkeypatch.setattr(
        "sys.argv",
        ["ade", "tree", f"--venv={tmp_path / 'venv'}", "-v"],
    )
    with pytest.raises(SystemExit):
        main()
    captured = capsys.readouterr()
    assert "ansible.scm\n├──ansible.utils" in captured.out
    assert "├──jsonschema" in captured.out


@pytest.mark.skipif(
    sys.version_info > (3, 12),
    reason="pylibssh issues 3.13, https://github.com/ansible/pylibssh/issues/699",
)
def test_requirements(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Install non-local collection.

    Args:
        capsys: Capture stdout and stderr
        tmp_path: Temporary directory
        monkeypatch: Pytest monkeypatch

    """
    requirements = Path(__file__).parent.parent / "fixtures" / "requirements.yml"
    monkeypatch.setattr(
        "sys.argv",
        [
            "ade",
            "install",
            f"--venv={tmp_path / 'venv'}",
            "-r",
            str(requirements),
        ],
    )
    with pytest.raises(SystemExit):
        main()
    string = "Installed collections include: ansible.netcommon, ansible.scm,"
    captured = capsys.readouterr()
    assert string in captured.out
    monkeypatch.setattr(
        "sys.argv",
        [
            "ade",
            "uninstall",
            f"--venv={tmp_path / 'venv'}",
            "-r",
            str(requirements),
        ],
    )
    with pytest.raises(SystemExit):
        main()
    captured = capsys.readouterr()
    string = "Removed ansible.netcommon"
    assert string in captured.out
    string = "Removed ansible.scm"
    assert string in captured.out

    monkeypatch.setattr(
        "sys.argv",
        ["ade", "list", f"--venv={tmp_path / 'venv'}"],
    )
    with pytest.raises(SystemExit):
        main()
    captured = capsys.readouterr()
    assert "ansible.netcommon" not in captured.out
    assert "ansible.scm" not in captured.out
    assert "ansible.utils" in captured.out


def test_system_site_packages(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Install non-local collection.

    Args:
        capsys: Capture stdout and stderr
        tmp_path: Temporary directory
        monkeypatch: Pytest monkeypatch
    """
    monkeypatch.setattr(
        "sys.argv",
        [
            "ade",
            "install",
            "ansible.utils",
            f"--venv={tmp_path / 'venv'}",
            "--system-site-packages",
            "--no-ansi",
            "-vvv",
        ],
    )
    with pytest.raises(SystemExit):
        main()
    captured = capsys.readouterr()
    assert "with system site packages" in captured.out
    assert "Installed collections include: ansible.utils" in captured.out


def test_specified_core_version_pass(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Install a user-specified core version.

    Args:
        tmp_path: Temporary directory
        monkeypatch: Pytest monkeypatch
    """
    term_features = TermFeatures(color=False, links=False)
    output = Output(
        log_file=f"/{tmp_path}/ansible-dev-environment.log",
        log_level="INFO",
        log_append="false",
        term_features=term_features,
        verbosity=0,
    )
    command = "pip index versions ansible-core"
    result = subprocess_run(command=command, verbose=True, msg="", output=output)

    version_pattern = re.compile(r"\d+\.\d+\.\d+")
    versions = version_pattern.findall(result.stdout)
    second_latest = versions[2]

    venv_path = tmp_path / ".venv"

    monkeypatch.setattr(
        "sys.argv",
        [
            "ade",
            "install",
            f"--venv={venv_path}",
            f"--ansible-core-version={second_latest}",
        ],
    )
    with pytest.raises(SystemExit):
        main()
    command = f"{venv_path}/bin/ansible --version"
    result = subprocess_run(command=command, verbose=True, msg="", output=output)
    assert second_latest in result.stdout


def test_specified_dev_tools_version_pass(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Install a user-specified ansible-dev-tools version.

    Args:
        tmp_path: Temporary directory
        monkeypatch: Pytest monkeypatch
    """
    term_features = TermFeatures(color=False, links=False)
    output = Output(
        log_file=f"/{tmp_path}/ansible-dev-environment.log",
        log_level="INFO",
        log_append="false",
        term_features=term_features,
        verbosity=0,
    )
    command = "pip index versions ansible-dev-tools"
    result = subprocess_run(command=command, verbose=True, msg="", output=output)

    version_pattern = re.compile(r"\d+\.\d+\.\d+")
    versions = version_pattern.findall(result.stdout)
    second_latest = versions[2]

    venv_path = tmp_path / ".venv"

    monkeypatch.setattr(
        "sys.argv",
        [
            "ade",
            "install",
            f"--venv={venv_path}",
            "--seed",
            f"--ansible-dev-tools-version={second_latest}",
        ],
    )
    with pytest.raises(SystemExit):
        main()
    command = f"{venv_path}/bin/pip list | grep ansible-dev-tools"
    result = subprocess_run(command=command, verbose=True, msg="", output=output)
    assert second_latest in result.stdout
