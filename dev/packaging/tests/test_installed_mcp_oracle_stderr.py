"""Focused contracts for the installed MCP oracle's process stderr channel."""

from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest

from ..installed_mcp_oracle import (
    InstalledMcpOracleError,
    _assert_no_diagnostic_notices,
    _process_stderr,
    _protocol_environment_overrides,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_process_stderr_ignores_a_capture_stream_without_fileno(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pytest-style capture cannot replace the native child-process handle."""
    captured = io.StringIO()
    monkeypatch.setattr(sys, "stderr", captured)

    process_stderr = _process_stderr()

    assert process_stderr is sys.__stderr__
    assert process_stderr is not captured
    assert process_stderr.fileno() >= 0


def test_process_stderr_refuses_when_the_interpreter_has_no_native_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    """A host without an original stderr handle fails before MCP process launch."""
    monkeypatch.setattr(sys, "__stderr__", None)

    with pytest.raises(InstalledMcpOracleError, match="OS-backed process stderr"):
        _process_stderr()


def test_protocol_environment_binds_the_attested_sibling_cli() -> None:
    """A caller cannot redirect the harness command port away from its cohort."""
    sibling_cli = Path("installed") / "Scripts" / "aeat.exe"

    environment = _protocol_environment_overrides(
        sibling_cli,
        {"CADRUMO_CLI_EXECUTABLE": "foreign-aeat", "SENTINEL": "retained"},
    )

    assert environment == {
        "CADRUMO_CLI_EXECUTABLE": str(sibling_cli),
        "SENTINEL": "retained",
    }


def test_authenticated_notice_gate_excuses_only_the_isolation_notice() -> None:
    isolated = {
        "status": "warning",
        "notices": [
            {
                "severity": "warning",
                "code": "config.login.session_not_persisted",
            },
        ],
    }

    _assert_no_diagnostic_notices(
        isolated,
        command_key="config.profile.complete_setup",
        authenticated=True,
    )
    with pytest.raises(InstalledMcpOracleError, match="unexpected diagnostic notices"):
        _assert_no_diagnostic_notices(
            isolated,
            command_key="config.profile.complete_setup",
        )

    unexpected = {
        "status": "warning",
        "notices": [{"severity": "warning", "code": "config.profile.unexpected"}],
    }
    with pytest.raises(InstalledMcpOracleError, match="unexpected diagnostic notices"):
        _assert_no_diagnostic_notices(
            unexpected,
            command_key="config.profile.complete_setup",
            authenticated=True,
        )
