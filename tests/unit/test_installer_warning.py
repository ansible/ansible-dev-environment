"""Tests for installer dependency constraint warnings.

This module tests the warning functionality in the Installer class that alerts users
when their requested ansible-core version may be incompatible with ansible-dev-tools
requirements. It uses pytest with monkeypatch for clean, unittest-free testing.

Classes:
    FakeArgs: Mock args object for testing configuration
    FakeConfig: Mock config object for testing installer behavior
    FakeOutput: Mock output object for capturing warning messages

Fixtures:
    test_config: Provides a FakeConfig instance for tests
    test_output: Provides a FakeOutput instance for tests
    installer: Provides an Installer instance with test dependencies
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest


if TYPE_CHECKING:
    from pathlib import Path

from ansible_dev_environment.output import Output
from ansible_dev_environment.subcommands.installer import Installer
from ansible_dev_environment.utils import TermFeatures


class FakeArgs:
    """Fake args object for testing installer configuration.

    Mimics the argparse.Namespace object that contains CLI arguments
    passed to the installer.
    """

    def __init__(self) -> None:
        """Initialize with default test values."""
        self.seed: bool = True
        self.ansible_core_version: str | None = None


class FakeConfig:
    """Fake config object for testing installer behavior.

    Mimics the Config class that provides configuration data to the installer.
    Contains pip commands and argument configuration.
    """

    def __init__(self) -> None:
        """Initialize with default test configuration."""
        self.venv_pip_cmd: str = "pip"
        self.venv_pip_install_cmd: str = "pip install"
        self.args: FakeArgs = FakeArgs()


@pytest.fixture(name="test_config")
def _test_config() -> FakeConfig:
    """Create a test config object.

    Returns:
        FakeConfig instance with default test configuration
    """
    return FakeConfig()


@pytest.fixture(name="test_output")
def _test_output(tmp_path: Path) -> Output:
    """Create a real output object for testing.

    Args:
        tmp_path: Pytest temporary directory fixture

    Returns:
        Real Output instance for testing
    """
    term_features = TermFeatures(color=False, links=False)
    return Output(
        log_file=str(tmp_path / "test.log"),
        log_level="WARNING",
        log_append="false",
        term_features=term_features,
        verbosity=0,
    )


@pytest.fixture(name="installer")
def _installer(test_config: FakeConfig, test_output: Output) -> Installer:
    """Create an installer instance with test dependencies.

    Args:
        test_config: Test configuration object
        test_output: Real output object for logging

    Returns:
        Installer instance configured for testing
    """
    return Installer(config=test_config, output=test_output)


def test_no_warning_when_seed_false(
    installer: Installer,
    test_config: FakeConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that no warning is issued when --seed is False.

    When the --seed flag is False, ansible-dev-tools won't be installed,
    so there's no need to check for version compatibility warnings.

    Args:
        installer: Installer instance under test
        test_config: Test configuration object
        monkeypatch: Pytest monkeypatch fixture for mocking
    """
    test_config.args.seed = False

    call_count = 0

    def _get_dependency_constraint(*_args: str, **_kwargs: str) -> None:
        nonlocal call_count
        call_count += 1

    monkeypatch.setattr(
        "ansible_dev_environment.subcommands.installer.get_dependency_constraint",
        _get_dependency_constraint,
    )

    installer._warn_if_core_version_incompatible("2.15.0")

    # Should not call get_dependency_constraint if seed is False
    assert call_count == 0


def test_no_warning_when_constraint_not_found(
    installer: Installer,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that no warning is issued when constraint cannot be determined.

    When the dependency constraint lookup returns None (e.g., package not found,
    network issues), the warning should be skipped gracefully.

    Args:
        installer: Installer instance under test
        monkeypatch: Pytest monkeypatch fixture for mocking
        caplog: Pytest log capture fixture
    """

    def _get_dependency_constraint(*_args: str, **_kwargs: str) -> None:
        return None

    monkeypatch.setattr(
        "ansible_dev_environment.subcommands.installer.get_dependency_constraint",
        _get_dependency_constraint,
    )

    installer._warn_if_core_version_incompatible("2.15.0")

    # Should not have any warning messages
    assert not any("ansible-dev-tools requires" in record.message for record in caplog.records)


def test_warning_issued_for_incompatible_version(
    installer: Installer,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that warning is issued when version is incompatible.

    When the user requests an ansible-core version that falls outside
    the requirements of ansible-dev-tools, a warning should be displayed.

    Args:
        installer: Installer instance under test
        monkeypatch: Pytest monkeypatch fixture for mocking
        caplog: Pytest log capture fixture
    """

    def _get_dependency_constraint(*_args: str, **_kwargs: str) -> str:
        return ">=2.16.0"

    monkeypatch.setattr(
        "ansible_dev_environment.subcommands.installer.get_dependency_constraint",
        _get_dependency_constraint,
    )

    installer._warn_if_core_version_incompatible("2.15.0")

    # Check that warning was logged
    warning_records = [record for record in caplog.records if record.levelname == "WARNING"]
    assert len(warning_records) == 1
    warning_msg = warning_records[0].message
    assert "ansible-dev-tools requires ansible-core>=2.16.0" in warning_msg
    assert "the requested version 2.15.0 falls outside this range" in warning_msg
    assert "There may be compatibility issues" in warning_msg


def test_no_warning_for_compatible_version(
    installer: Installer,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that no warning is issued when version is compatible.

    Args:
        installer: Installer instance under test
        monkeypatch: Pytest monkeypatch fixture for mocking
        caplog: Pytest log capture fixture
    """

    def _get_dependency_constraint(*_args: str, **_kwargs: str) -> str:
        return ">=2.16.0"

    monkeypatch.setattr(
        "ansible_dev_environment.subcommands.installer.get_dependency_constraint",
        _get_dependency_constraint,
    )

    installer._warn_if_core_version_incompatible("2.16.0")

    # Should not have any warning messages
    warning_records = [record for record in caplog.records if record.levelname == "WARNING"]
    assert len(warning_records) == 0


def test_no_warning_for_higher_compatible_version(
    installer: Installer,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that no warning is issued when version is higher than required.

    Args:
        installer: Installer instance under test
        monkeypatch: Pytest monkeypatch fixture for mocking
        caplog: Pytest log capture fixture
    """

    def _get_dependency_constraint(*_args: str, **_kwargs: str) -> str:
        return ">=2.16.0"

    monkeypatch.setattr(
        "ansible_dev_environment.subcommands.installer.get_dependency_constraint",
        _get_dependency_constraint,
    )

    installer._warn_if_core_version_incompatible("2.19.0")

    # Should not have any warning messages for higher compatible version
    warning_records = [record for record in caplog.records if record.levelname == "WARNING"]
    assert len(warning_records) == 0


def test_handles_packaging_import_error(
    installer: Installer,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that function handles packaging module being unavailable gracefully.

    Args:
        installer: Installer instance under test
        monkeypatch: Pytest monkeypatch fixture for mocking
        caplog: Pytest log capture fixture
    """

    def _get_dependency_constraint(*_args: str, **_kwargs: str) -> str:
        return ">=2.16.0"

    monkeypatch.setattr(
        "ansible_dev_environment.subcommands.installer.get_dependency_constraint",
        _get_dependency_constraint,
    )
    # Mock the module-level variables to simulate packaging not being available
    monkeypatch.setattr("ansible_dev_environment.subcommands.installer.specifiers", None)
    monkeypatch.setattr("ansible_dev_environment.subcommands.installer.version", None)

    installer._warn_if_core_version_incompatible("2.15.0")

    # Should not have any warning messages when packaging is unavailable
    warning_records = [record for record in caplog.records if record.levelname == "WARNING"]
    assert len(warning_records) == 0


def test_handles_version_parsing_error(
    installer: Installer,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that function handles version parsing errors gracefully.

    Args:
        installer: Installer instance under test
        monkeypatch: Pytest monkeypatch fixture for mocking
        caplog: Pytest log capture fixture
    """

    def _get_dependency_constraint(*_args: str, **_kwargs: str) -> str:
        return ">=2.16.0"

    monkeypatch.setattr(
        "ansible_dev_environment.subcommands.installer.get_dependency_constraint",
        _get_dependency_constraint,
    )

    # Use a truly malformed version that will cause packaging.version.parse to fail
    installer._warn_if_core_version_incompatible("invalid.version.string!")

    # Should not have any warning messages when version parsing fails
    warning_records = [record for record in caplog.records if record.levelname == "WARNING"]
    assert len(warning_records) == 0


@pytest.mark.parametrize(
    "pip_command",
    (
        "pip",
        "uv pip",
        "/path/to/pip",
        "python -m pip",
    ),
)
def test_uses_pip_command_correctly(
    installer: Installer,
    test_config: FakeConfig,
    monkeypatch: pytest.MonkeyPatch,
    pip_command: str,
) -> None:
    """Test that pip command is used correctly from config.

    Verifies that the installer passes the correct pip command from the
    configuration to the dependency constraint lookup function.

    Args:
        installer: Installer instance under test
        test_config: Test configuration object
        monkeypatch: Pytest monkeypatch fixture for mocking
        pip_command: The pip command to test (parametrized)
    """
    test_config.venv_pip_cmd = pip_command

    received_calls = []

    def _get_dependency_constraint(
        package_name: str,
        dependency_name: str,
        pip_command: str = "pip",
        _timeout: int = 30,
    ) -> str | None:
        received_calls.append(
            {
                "package_name": package_name,
                "dependency_name": dependency_name,
                "pip_command": pip_command,
            },
        )
        return None

    monkeypatch.setattr(
        "ansible_dev_environment.subcommands.installer.get_dependency_constraint",
        _get_dependency_constraint,
    )

    installer._warn_if_core_version_incompatible("2.15.0")

    assert len(received_calls) == 1
    call = received_calls[0]
    assert call["package_name"] == "ansible-dev-tools"
    assert call["dependency_name"] == "ansible-core"
    assert call["pip_command"] == pip_command


def test_warning_called_from_install_ade_deps(
    installer: Installer,
    test_config: FakeConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that warning is called from _install_ade_deps when appropriate.

    Verifies that the warning method is called with the correct version
    when both a core version is specified and seed is True.

    Args:
        installer: Installer instance under test
        test_config: Test configuration object
        monkeypatch: Pytest monkeypatch fixture for mocking
    """
    test_config.args.ansible_core_version = "2.15.0"
    test_config.args.seed = True

    warning_calls: list[str] = []

    def _warn_if_core_version_incompatible(version: str) -> None:
        warning_calls.append(version)

    def _install_dev_tools() -> None:
        pass

    def _install_core() -> None:
        pass

    monkeypatch.setattr(
        installer,
        "_warn_if_core_version_incompatible",
        _warn_if_core_version_incompatible,
    )
    monkeypatch.setattr(installer, "_install_dev_tools", _install_dev_tools)
    monkeypatch.setattr(installer, "_install_core", _install_core)

    installer._install_ade_deps()

    assert len(warning_calls) == 1
    assert warning_calls[0] == "2.15.0"


def test_warning_not_called_when_no_core_version(
    installer: Installer,
    test_config: FakeConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that warning is not called when no core version is specified.

    When ansible_core_version is None, no version compatibility check
    should be performed, even if seed is True.

    Args:
        installer: Installer instance under test
        test_config: Test configuration object
        monkeypatch: Pytest monkeypatch fixture for mocking
    """
    test_config.args.ansible_core_version = None
    test_config.args.seed = True

    warning_calls: list[str] = []

    def _warn_if_core_version_incompatible(version: str) -> None:
        warning_calls.append(version)

    def _install_dev_tools() -> None:
        pass

    def _install_core() -> None:
        pass

    monkeypatch.setattr(
        installer,
        "_warn_if_core_version_incompatible",
        _warn_if_core_version_incompatible,
    )
    monkeypatch.setattr(installer, "_install_dev_tools", _install_dev_tools)
    monkeypatch.setattr(installer, "_install_core", _install_core)

    installer._install_ade_deps()

    assert len(warning_calls) == 0


def test_warning_not_called_when_seed_false(
    installer: Installer,
    test_config: FakeConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that warning is not called when seed is False.

    When seed is False, ansible-dev-tools won't be installed, so there's
    no need to check for version compatibility warnings.

    Args:
        installer: Installer instance under test
        test_config: Test configuration object
        monkeypatch: Pytest monkeypatch fixture for mocking
    """
    test_config.args.ansible_core_version = "2.15.0"
    test_config.args.seed = False

    warning_calls: list[str] = []

    def _warn_if_core_version_incompatible(version: str) -> None:
        warning_calls.append(version)

    def _install_dev_tools() -> None:
        pass

    def _install_core() -> None:
        pass

    monkeypatch.setattr(
        installer,
        "_warn_if_core_version_incompatible",
        _warn_if_core_version_incompatible,
    )
    monkeypatch.setattr(installer, "_install_dev_tools", _install_dev_tools)
    monkeypatch.setattr(installer, "_install_core", _install_core)

    installer._install_ade_deps()

    assert len(warning_calls) == 0


@pytest.mark.parametrize(
    ("constraint", "version", "should_warn"),
    (
        (">=2.16.0", "2.15.0", True),  # Should warn
        (">=2.16.0", "2.16.0", False),  # Should not warn
        (">=2.16.0", "2.17.0", False),  # Should not warn
        (">2.16.0", "2.16.0", True),  # Should warn (strictly greater)
        ("==2.16.0", "2.15.0", True),  # Should warn
        ("==2.16.0", "2.16.0", False),  # Should not warn
        ("~=2.16.0", "2.15.0", True),  # Should warn
        ("~=2.16.0", "2.16.5", False),  # Should not warn
    ),
)
def test_handles_different_constraint_formats(
    installer: Installer,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    constraint: str,
    version: str,
    *,
    should_warn: bool,
) -> None:
    """Test that different constraint formats are handled correctly.

    Args:
        installer: Installer instance under test
        monkeypatch: Pytest monkeypatch fixture for mocking
        caplog: Pytest log capture fixture
        constraint: The version constraint to test (parametrized)
        version: The version to test against constraint (parametrized)
        should_warn: Whether a warning should be issued (parametrized)
    """

    def _get_dependency_constraint(*_args: str, **_kwargs: str) -> str:
        return constraint

    monkeypatch.setattr(
        "ansible_dev_environment.subcommands.installer.get_dependency_constraint",
        _get_dependency_constraint,
    )

    installer._warn_if_core_version_incompatible(version)

    warning_records = [record for record in caplog.records if record.levelname == "WARNING"]
    if should_warn:
        assert len(warning_records) == 1
    else:
        assert len(warning_records) == 0


def test_integration_with_real_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test integration with a real config object.

    This integration test verifies that the warning system works correctly
    when using real Output objects instead of test fakes.

    Args:
        tmp_path: Pytest temporary directory fixture
        monkeypatch: Pytest monkeypatch fixture for mocking
    """
    # This test uses real objects to ensure integration works

    # Create real objects
    term_features = TermFeatures(color=False, links=False)
    output = Output(
        log_file=str(tmp_path / "test.log"),
        log_level="INFO",
        log_append="false",
        term_features=term_features,
        verbosity=0,
    )

    # Test config with required attributes
    config = FakeConfig()
    config.venv_pip_cmd = "pip"
    config.venv_pip_install_cmd = "pip install"
    config.args.seed = True
    config.args.ansible_core_version = "2.15.0"

    installer = Installer(config=config, output=output)

    # Verify the dependency constraint function is called
    constraint_calls = []

    def _get_dependency_constraint(
        package_name: str,
        dependency_name: str,
        pip_command: str = "pip",
        _timeout: int = 30,
    ) -> str:
        constraint_calls.append(
            {
                "package_name": package_name,
                "dependency_name": dependency_name,
                "pip_command": pip_command,
            },
        )
        return ">=2.16.0"

    monkeypatch.setattr(
        "ansible_dev_environment.subcommands.installer.get_dependency_constraint",
        _get_dependency_constraint,
    )

    # This should not raise any exceptions
    installer._warn_if_core_version_incompatible("2.15.0")

    # Verify the constraint check was called
    assert len(constraint_calls) == 1
    call = constraint_calls[0]
    assert call["package_name"] == "ansible-dev-tools"
    assert call["dependency_name"] == "ansible-core"
    assert call["pip_command"] == "pip"
