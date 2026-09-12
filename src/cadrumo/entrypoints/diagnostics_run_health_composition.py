"""Outer composition for diagnostic run-health telemetry."""

from __future__ import annotations

from ..application.diagnostics_run_health_ports import (
    DiagnosticAuthProbePort,
    DiagnosticAuthProbeResult,
    DiagnosticRunTelemetryPort,
)
from ..application.state_projection_ports import StateProjectionReadPorts


class _DiagnosticsAuthProbeAdapter(DiagnosticAuthProbePort):
    """Adapt the canonical auth application result to diagnostics-safe facts."""

    def __init__(self, read_ports: StateProjectionReadPorts) -> None:
        self._read_ports = read_ports

    def probe(self) -> DiagnosticAuthProbeResult:
        """Read auth readiness through the root-composed state projection ports."""
        from ..application.auth.operator import test_operator_auth

        result = test_operator_auth(read_ports=self._read_ports)
        return DiagnosticAuthProbeResult(
            provider=result.provider,
            configured=result.configured,
            persisted_session_present=result.persisted_session_present,
            persisted_session_expired=result.persisted_session_expired,
            persisted_session_state=result.persisted_session_state,
            probe_summary=result.probe_summary,
        )


def compose_diagnostics_run_health_port() -> DiagnosticRunTelemetryPort:
    """Bind the diagnostic read port to encrypted local run telemetry."""
    from ..adapters.outbound.llm.run_telemetry import (
        LLMRunTelemetryDiagnosticsAdapter,
        LLMRunTelemetryRecorder,
    )

    return LLMRunTelemetryDiagnosticsAdapter(LLMRunTelemetryRecorder())


def compose_diagnostics_auth_probe_port(*, read_ports: StateProjectionReadPorts) -> DiagnosticAuthProbePort:
    """Bind the diagnostics auth probe to the root-composed state projection."""
    return _DiagnosticsAuthProbeAdapter(read_ports)


__all__ = ["compose_diagnostics_auth_probe_port", "compose_diagnostics_run_health_port"]
