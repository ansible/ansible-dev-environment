"""Basic smoke tests."""

import json

from pathlib import Path

import pytest

from ansible_development_environment.cli import main
from ansible_development_environment.output import Output
from ansible_development_environment.utils import TermFeatures, subprocess_run


def test_venv(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Basic smoke test."""
    # disable color for json output
    term_features = TermFeatures(color=False, links=False)
    output = Output(
        log_file=f"/{tmp_path}/ansible-development-environment.log",
        log_level="INFO",
        log_append="false",
        term_features=term_features,
        verbosity=0,
    )
    command = (
        "git clone https://github.com/ansible-collections/cisco.nxos.git"
        f" {tmp_path/ 'cisco.nxos'}"
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
            "ansible-development-environment",
            "install",
            str(tmp_path / "cisco.nxos"),
            "--venv=venv",
            "--no-ansi",
        ],
    )
    with pytest.raises(SystemExit):
        main()
    string = "Installed collections include: ansible.netcommon, ansible.utils,"
    captured = capsys.readouterr()

    assert string in captured.out

    monkeypatch.setattr(
        "sys.argv",
        ["ansible-development-environment", "list", "--venv=venv"],
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
            "ansible-development-environment",
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
        ["ansible-development-environment", "inspect", "--venv=venv", "--no-ansi"],
    )
    with pytest.raises(SystemExit):
        main()
    captured = capsys.readouterr()
    captured_json = json.loads(captured.out)
    assert "cisco.nxos" in captured_json
    assert "ansible.netcommon" in captured_json
    assert "ansible.utils" not in captured_json

    command = f"{tmp_path / 'venv' / 'bin' / 'python'} -m pip uninstall xmltodict -y"
    subprocess_run(command=command, verbose=True, msg="", output=output)

    monkeypatch.setattr(
        "sys.argv",
        ["ansible-development-environment", "check", "--venv=venv"],
    )
    with pytest.raises(SystemExit):
        main()
    captured = capsys.readouterr()
    assert "Missing python dependencies: xmltodict" in captured.err


def test_non_local(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Install non-local collection."""
    monkeypatch.setattr(
        "sys.argv",
        [
            "ansible-development-environment",
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
        ["ansible-development-environment", "tree", f"--venv={tmp_path / 'venv'}"],
    )
    with pytest.raises(SystemExit):
        main()
    captured = capsys.readouterr()
    with pytest.raises(SystemExit):
        main()
    captured = capsys.readouterr()
    string = "ansible.scm\n└──ansible.utils\n\n"
    assert string == captured.out


def test_requirements(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Install non-local collection."""
    requirements = Path(__file__).parent.parent / "fixtures" / "requirements.yml"
    monkeypatch.setattr(
        "sys.argv",
        [
            "ansible-development-environment",
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
            "ansible-development-environment",
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
        ["ansible-development-environment", "list", f"--venv={tmp_path / 'venv'}"],
    )
    with pytest.raises(SystemExit):
        main()
    captured = capsys.readouterr()
    assert "ansible.netcommon" not in captured.out
    assert "ansible.scm" not in captured.out
    assert "ansible.utils" in captured.out
