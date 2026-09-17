"""Outer composition for diagnostic run-health telemetry."""

from __future__ import annotations

from typing import override

from ..application.auth.certificate_secret_backend import CertificateSecretBackendFactory
from ..application.auth.operator_probe_ports import OperatorProbePorts
from ..application.auth.operator_scope_ports import OperatorScopePorts
from ..application.diagnostics_run_health_ports import (
    DiagnosticAuthProbePort,
    DiagnosticAuthProbeResult,
    DiagnosticRunTelemetryPort,
)
from ..application.state_projection_ports import StateProjectionReadPorts
from ..domain.calculations.registry.authority import PinnedAuthorityOperation


class _DiagnosticsAuthProbeAdapter(DiagnosticAuthProbePort):
    """Adapt the canonical auth application result to diagnostics-safe facts."""

    def __init__(
        self,
        read_ports: StateProjectionReadPorts,
        certificate_secret_backend_factory: CertificateSecretBackendFactory,
        operator_probe_ports: OperatorProbePorts,
        operator_scope_ports: OperatorScopePorts,
        operation: PinnedAuthorityOperation,
    ) -> None:
        self._read_ports = read_ports
        self._certificate_secret_backend_factory = certificate_secret_backend_factory
        self._operator_probe_ports = operator_probe_ports
        self._operator_scope_ports = operator_scope_ports
        self._operation = operation

    @override
    def probe(self) -> DiagnosticAuthProbeResult:
        """Read auth readiness through the root-composed state projection ports."""
        from ..application.auth.operator import test_operator_auth

        result = test_operator_auth(
            certificate_secret_backend_factory=self._certificate_secret_backend_factory,
            operator_probe_ports=self._operator_probe_ports,
            operator_scope_ports=self._operator_scope_ports,
            read_ports=self._read_ports,
            operation=self._operation,
        )
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
    from ..adapters.persistence.llm.run_telemetry import (
        LLMRunTelemetryDiagnosticsAdapter,
        LLMRunTelemetryRecorder,
    )

    return LLMRunTelemetryDiagnosticsAdapter(LLMRunTelemetryRecorder())


def compose_diagnostics_auth_probe_port(
    *,
    certificate_secret_backend_factory: CertificateSecretBackendFactory,
    operator_probe_ports: OperatorProbePorts,
    operator_scope_ports: OperatorScopePorts,
    read_ports: StateProjectionReadPorts,
    operation: PinnedAuthorityOperation,
) -> DiagnosticAuthProbePort:
    """Bind the diagnostics auth probe to the root-composed state projection."""
    return _DiagnosticsAuthProbeAdapter(
        read_ports,
        certificate_secret_backend_factory,
        operator_probe_ports,
        operator_scope_ports,
        operation,
    )


__all__ = ["compose_diagnostics_auth_probe_port", "compose_diagnostics_run_health_port"]
