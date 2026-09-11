"""Read-only developer-tool readiness probes."""

from __future__ import annotations

import pytest

from ..doctor import check_developer_toolchain, probe_toolchain

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_probe_reports_required_and_optional_commands_without_invoking_them() -> None:
    """The probe only asks PATH and keeps optional workstation gaps visible."""
    available = {"uv", "just", "ruff", "ty", "pyrefly", "lint-imports", "deptry", "vulture", "radon", "complexipy"}
    calls: list[str] = []

    def which(command: str) -> str | None:
        calls.append(command)
        return f"/bin/{command}" if command in available else None

    probes = probe_toolchain(which=which)

    assert calls == [probe.command for probe in probes]
    assert all(probe.available for probe in probes if not probe.optional)
    assert all(not probe.available for probe in probes if probe.optional)


def test_missing_required_tool_is_blocking_but_missing_optional_tools_are_not(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A minimal checkout stays usable without Node while required tools fail."""
    missing_required = {"ruff"}

    def which(command: str) -> str | None:
        return None if command in missing_required or command in {"node", "npx"} else f"/bin/{command}"

    assert check_developer_toolchain(which=which) == 1
    output = capsys.readouterr().out
    assert "missing" in output
    assert "ruff" in output
    assert "optional workstation tools absent: node, npx" in output


def test_optional_workstation_gaps_do_not_fail_the_probe() -> None:
    """The optional Node toolchain is not part of minimal setup readiness."""

    def which(command: str) -> str | None:
        return None if command in {"node", "npx"} else f"/bin/{command}"

    assert check_developer_toolchain(which=which) == 0
