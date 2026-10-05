"""Exact-profile composition for registered diagnostic reports."""

from __future__ import annotations

from uuid import UUID

from ..application.diagnostics_operation_ports import DiagnosticsReadPorts
from ..domain.calculations.registry.authority import PinnedAuthorityOperation
from .auth_read_composition import compose_auth_read_ports
from .diagnostics_run_health_composition import (
    compose_diagnostics_auth_probe_port,
    compose_diagnostics_run_health_port,
)


def build_diagnostics_read_ports(*, profile_id: UUID, operation: PinnedAuthorityOperation) -> DiagnosticsReadPorts:
    """Reuse encrypted run records and the canonical local auth probe."""
    auth = compose_auth_read_ports(profile_id)
    return DiagnosticsReadPorts(
        profile_id=profile_id,
        operation=operation,
        run_telemetry_port=compose_diagnostics_run_health_port(),
        auth_probe_port=compose_diagnostics_auth_probe_port(
            certificate_secret_backend_factory=auth.certificate_secret_backend_factory,
            operator_probe_ports=auth.operator_probe_ports,
            operator_scope_ports=auth.operator_scope_ports,
            read_ports=auth.read_ports,
            operation=operation,
        ),
    )
