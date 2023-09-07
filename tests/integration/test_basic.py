"""Basic smoke tests."""

from pathlib import Path

import pytest

from pip4a.cli import main
from pip4a.utils import subprocess_run


def test_venv(
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Basic smoke test."""
    command = (
        "git clone https://github.com/ansible-collections/cisco.nxos.git"
        f" {tmp_path/ 'cisco.nxos'}"
    )
    subprocess_run(command=command, verbose=True)
    monkeypatch.chdir(tmp_path)

    monkeypatch.setattr(
        "sys.argv",
        ["pip4a", "install", str(tmp_path / "cisco.nxos"), "--venv=venv"],
    )
    with pytest.raises(SystemExit):
        main()
    string = "Installed collections: cisco.nxos, ansible.netcommon, and ansible.utils"
    assert string in caplog.text
    _captured = capsys.readouterr()
    monkeypatch.setattr(
        "sys.argv",
        ["pip4a", "list", "--venv=venv"],
    )
    with pytest.raises(SystemExit):
        main()
    captured = capsys.readouterr()
    assert "cisco.nxos" in captured.out
    assert "ansible.netcommon" in captured.out
    assert "ansible.utils" in captured.out
    assert "unknown" not in captured.out

    monkeypatch.setattr("sys.argv", ["pip4a", "uninstall", "cisco.nxos", "--venv=venv"])
    with pytest.raises(SystemExit):
        main()
    captured = capsys.readouterr()
    assert "Removed cisco.nxos" in caplog.text

    monkeypatch.setattr("sys.argv", ["pip4a", "inspect", "--venv=venv"])
    with pytest.raises(SystemExit):
        main()
    captured = capsys.readouterr()
    assert "cisco.nxos" not in captured.out
    assert "ansible.netcommon" in captured.out
    assert "ansible.utils" in captured.out


def test_non_local(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Install non-local collection."""
    monkeypatch.setattr(
        "sys.argv",
        ["pip4a", "install", "ansible.scm", f"--venv={tmp_path / 'venv'}"],
    )
    with pytest.raises(SystemExit):
        main()
    string = "Installed collections: ansible.scm and ansible.utils"
    assert string in caplog.text
