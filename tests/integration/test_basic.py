"""Basic smoke tests."""

from pathlib import Path

import pytest

from pip4a.cli import main
from pip4a.utils import subprocess_run


def test_venv(
    caplog: pytest.LogCaptureFixture,
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
    main()
    string = "Installed collections: cisco.nxos, ansible.netcommon, and ansible.utils"
    assert string in caplog.text
