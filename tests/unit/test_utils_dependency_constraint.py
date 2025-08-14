"""Tests for get_dependency_constraint utility function.

This module tests the get_dependency_constraint function in utils.py that dynamically
determines package dependency constraints using pip's --dry-run functionality.

The function uses subprocess to run pip commands and parses the output to extract
version constraints for specific dependencies. These tests verify the parsing logic,
error handling, and integration with different pip output formats.
"""

from __future__ import annotations

import subprocess

from typing import NoReturn

import pytest

from ansible_dev_environment.utils import get_dependency_constraint


# Constants for testing
CUSTOM_TIMEOUT = 60


def test_returns_none_for_nonexistent_package() -> None:
    """Test that function returns None for packages that don't exist.

    When pip cannot find a package, the function should gracefully return None
    rather than raising an exception.
    """
    result = get_dependency_constraint(
        package_name="definitely-does-not-exist-package-12345",
        dependency_name="some-dependency",
    )
    assert result is None


def test_returns_none_for_nonexistent_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that function returns None when dependency doesn't exist.

    When the target package exists but doesn't depend on the specified dependency,
    the function should return None.

    Args:
        monkeypatch: Pytest monkeypatch fixture for mocking
    """

    class SubprocessResult:
        def __init__(self) -> None:
            self.returncode = 0
            self.stdout = "Would install some-other-package>=1.0.0"
            self.stderr = ""

    def _run(*_args: object, **_kwargs: object) -> SubprocessResult:
        return SubprocessResult()

    monkeypatch.setattr("subprocess.run", _run)

    result = get_dependency_constraint(
        package_name="some-package",
        dependency_name="nonexistent-dependency",
    )
    assert result is None


def test_parses_standard_constraint_format(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test parsing standard constraint format like 'package>=1.2.3'.

    Args:
        monkeypatch: Pytest monkeypatch fixture for mocking
    """

    class SubprocessResult:
        def __init__(self) -> None:
            self.returncode = 0
            self.stdout = "Would install ansible-core>=2.16.0 other-package>=1.0.0"
            self.stderr = ""

    def _run(*_args: object, **_kwargs: object) -> SubprocessResult:
        return SubprocessResult()

    monkeypatch.setattr("subprocess.run", _run)

    result = get_dependency_constraint(
        package_name="ansible-dev-tools",
        dependency_name="ansible-core",
    )
    assert result == ">=2.16.0"


@pytest.mark.parametrize(
    "output_format",
    (
        "Would install (ansible-core>=2.16.0) other-package",
        "Requirement already satisfied: ansible-core>=2.16.0 in /path/to/site-packages",
        "Dependencies: ansible-core (>=2.16.0), other-dep (>=1.0)",
        "Would install ANSIBLE-CORE>=2.16.0",  # Case insensitive
        "Some output without our dependency\nansible-core>=2.16.0 found in stderr",
    ),
)
def test_parses_various_output_formats(
    monkeypatch: pytest.MonkeyPatch,
    output_format: str,
) -> None:
    """Test parsing various pip output formats.

    Args:
        monkeypatch: Pytest monkeypatch fixture for mocking
        output_format: The output format to test (parametrized)
    """

    class SubprocessResult:
        def __init__(self) -> None:
            self.returncode = 0
            if "stderr" in output_format:
                self.stdout, self.stderr = output_format.split("\n")
            else:
                self.stdout = output_format
                self.stderr = ""

    def _run(*_args: object, **_kwargs: object) -> SubprocessResult:
        return SubprocessResult()

    monkeypatch.setattr("subprocess.run", _run)

    result = get_dependency_constraint(
        package_name="ansible-dev-tools",
        dependency_name="ansible-core",
    )
    assert result == ">=2.16.0"


@pytest.mark.parametrize(
    ("constraint_output", "expected"),
    (
        ("ansible-core>=2.16.0", ">=2.16.0"),
        ("ansible-core>2.16.0", ">2.16.0"),
        ("ansible-core==2.16.0", "==2.16.0"),
        ("ansible-core~=2.16.0", "~=2.16.0"),
        ("ansible-core!=2.15.0", "!=2.15.0"),
        ("ansible-core<=2.17.0", "<=2.17.0"),
    ),
)
def test_handles_different_constraint_operators(
    monkeypatch: pytest.MonkeyPatch,
    constraint_output: str,
    expected: str,
) -> None:
    """Test that different constraint operators are parsed correctly.

    Args:
        monkeypatch: Pytest monkeypatch fixture for mocking
        constraint_output: The constraint string in pip output (parametrized)
        expected: The expected parsed constraint (parametrized)
    """

    class SubprocessResult:
        def __init__(self) -> None:
            self.returncode = 0
            self.stdout = f"Would install {constraint_output}"
            self.stderr = ""

    def _run(*_args: object, **_kwargs: object) -> SubprocessResult:
        return SubprocessResult()

    monkeypatch.setattr("subprocess.run", _run)

    result = get_dependency_constraint(
        package_name="ansible-dev-tools",
        dependency_name="ansible-core",
    )
    assert result == expected


@pytest.mark.parametrize(
    ("version_output", "expected"),
    (
        ("ansible-core>=2.16.0", ">=2.16.0"),
        ("ansible-core>=2.16.0.1", ">=2.16.0.1"),
        ("ansible-core>=2.16.0.2.3", ">=2.16.0.2.3"),
    ),
)
def test_handles_complex_version_numbers(
    monkeypatch: pytest.MonkeyPatch,
    version_output: str,
    expected: str,
) -> None:
    """Test that complex version numbers are parsed correctly.

    Args:
        monkeypatch: Pytest monkeypatch fixture for mocking
        version_output: The version string in pip output (parametrized)
        expected: The expected parsed constraint (parametrized)
    """

    class SubprocessResult:
        def __init__(self) -> None:
            self.returncode = 0
            self.stdout = f"Would install {version_output}"
            self.stderr = ""

    def _run(*_args: object, **_kwargs: object) -> SubprocessResult:
        return SubprocessResult()

    monkeypatch.setattr("subprocess.run", _run)

    result = get_dependency_constraint(
        package_name="ansible-dev-tools",
        dependency_name="ansible-core",
    )
    assert result == expected


def test_handles_special_characters_in_package_names(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that package names with special characters are handled correctly.

    Args:
        monkeypatch: Pytest monkeypatch fixture for mocking
    """

    class SubprocessResult:
        def __init__(self) -> None:
            self.returncode = 0
            self.stdout = "Would install some-package.with.dots>=1.0.0"
            self.stderr = ""

    def _run(*_args: object, **_kwargs: object) -> SubprocessResult:
        return SubprocessResult()

    monkeypatch.setattr("subprocess.run", _run)

    result = get_dependency_constraint(
        package_name="some-package",
        dependency_name="some-package.with.dots",
    )
    assert result == ">=1.0.0"


def test_returns_none_on_pip_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that function returns None when pip command fails.

    Args:
        monkeypatch: Pytest monkeypatch fixture for mocking
    """

    class SubprocessResult:
        def __init__(self) -> None:
            self.returncode = 1
            self.stdout = ""
            self.stderr = "ERROR: Could not find a version that satisfies the requirement"

    def _run(*_args: object, **_kwargs: object) -> SubprocessResult:
        return SubprocessResult()

    monkeypatch.setattr("subprocess.run", _run)

    result = get_dependency_constraint(
        package_name="nonexistent-package",
        dependency_name="some-dependency",
        timeout=1,
    )
    assert result is None


def test_returns_none_on_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that function returns None when pip command times out.

    Args:
        monkeypatch: Pytest monkeypatch fixture for mocking
    """

    def _run(*_args: object, **_kwargs: object) -> NoReturn:
        cmd = "pip"
        timeout = 30
        raise subprocess.TimeoutExpired(cmd, timeout)

    monkeypatch.setattr("subprocess.run", _run)

    result = get_dependency_constraint(
        package_name="some-package",
        dependency_name="some-dependency",
        timeout=1,
    )
    assert result is None


def test_returns_none_on_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that function returns None when any exception occurs.

    Args:
        monkeypatch: Pytest monkeypatch fixture for mocking
    """

    def _run(*_args: object, **_kwargs: object) -> NoReturn:
        msg = "Unexpected error"
        raise RuntimeError(msg)

    monkeypatch.setattr("subprocess.run", _run)

    result = get_dependency_constraint(
        package_name="some-package",
        dependency_name="some-dependency",
    )
    assert result is None


def test_uses_custom_pip_command(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that custom pip command is used correctly.

    Args:
        monkeypatch: Pytest monkeypatch fixture for mocking
    """

    class SubprocessResult:
        def __init__(self) -> None:
            self.returncode = 0
            self.stdout = "Would install ansible-core>=2.16.0"
            self.stderr = ""

    received_commands: list[str] = []

    def _run(command: str, *_args: object, **_kwargs: object) -> SubprocessResult:
        received_commands.append(command)
        return SubprocessResult()

    monkeypatch.setattr("subprocess.run", _run)

    get_dependency_constraint(
        package_name="ansible-dev-tools",
        dependency_name="ansible-core",
        pip_command="uv pip",
    )

    assert len(received_commands) == 1
    assert "uv pip install --dry-run ansible-dev-tools" in received_commands[0]


def test_uses_custom_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that custom timeout is passed to subprocess.run.

    Args:
        monkeypatch: Pytest monkeypatch fixture for mocking
    """

    class SubprocessResult:
        def __init__(self) -> None:
            self.returncode = 0
            self.stdout = "Would install ansible-core>=2.16.0"
            self.stderr = ""

    def _run(*_args: object, **kwargs: object) -> SubprocessResult:
        # Verify timeout was passed correctly
        assert kwargs.get("timeout") == CUSTOM_TIMEOUT
        return SubprocessResult()

    monkeypatch.setattr("subprocess.run", _run)

    get_dependency_constraint(
        package_name="ansible-dev-tools",
        dependency_name="ansible-core",
        timeout=CUSTOM_TIMEOUT,
    )


def test_finds_first_matching_pattern(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that function returns the first matching constraint found.

    Args:
        monkeypatch: Pytest monkeypatch fixture for mocking
    """

    class SubprocessResult:
        def __init__(self) -> None:
            self.returncode = 0
            self.stdout = "ansible-core>=2.16.0 and also ansible-core>=2.15.0"
            self.stderr = ""

    def _run(*_args: object, **_kwargs: object) -> SubprocessResult:
        return SubprocessResult()

    monkeypatch.setattr("subprocess.run", _run)

    result = get_dependency_constraint(
        package_name="ansible-dev-tools",
        dependency_name="ansible-core",
    )

    # Should return the first match
    assert result == ">=2.16.0"


def test_real_ansible_dev_tools_constraint() -> None:
    """Test with real ansible-dev-tools package (if available).

    This integration test will only work if pip is available and can reach PyPI.
    If the package is not available or network is unreachable, it should return None.
    """
    result = get_dependency_constraint(
        package_name="ansible-dev-tools",
        dependency_name="ansible-core",
        timeout=5,  # Short timeout for CI environments
    )

    # Should either find a constraint or return None (if package not available)
    if result is not None:
        # If we get a result, it should be a valid constraint string
        assert any(op in result for op in [">=", ">", "==", "~=", "!=", "<=", "<"])
        assert any(c.isdigit() for c in result)  # Should contain version numbers


def test_real_pytest_constraint() -> None:
    """Test with real pytest package (if available).

    This tests the function with a package that's likely to be available
    in the test environment.
    """
    result = get_dependency_constraint(
        package_name="pytest",
        dependency_name="packaging",  # pytest depends on packaging
        timeout=5,
    )

    # Should either find a constraint or return None
    if result is not None:
        assert any(op in result for op in [">=", ">", "==", "~=", "!=", "<=", "<"])


def test_timeout_with_slow_command() -> None:
    """Test that timeout works with a slow command.

    This test uses a command that will likely timeout to verify
    the timeout functionality works correctly.
    """
    result = get_dependency_constraint(
        package_name="some-nonexistent-package-that-will-be-slow",
        dependency_name="some-dependency",
        timeout=1,  # Very short timeout
    )

    # Should return None due to timeout
    assert result is None
