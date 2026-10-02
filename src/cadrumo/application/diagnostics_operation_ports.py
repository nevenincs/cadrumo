"""Composition-owned exact-profile capabilities for registered diagnostics."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from ..core.config import Settings
from ..core.telemetry.emit import TelemetrySink
from ..domain.calculations.registry.authority import PinnedAuthorityOperation
from .diagnostics_run_health_ports import DiagnosticAuthProbePort, DiagnosticRunTelemetryPort


@dataclass(frozen=True, slots=True)
class DiagnosticsReadPorts:
    """One immutable worker identity and its local diagnostic readers."""

    profile_id: UUID
    operation: PinnedAuthorityOperation
    run_telemetry_port: DiagnosticRunTelemetryPort
    auth_probe_port: DiagnosticAuthProbePort


class DiagnosticsReadPortsFactory(Protocol):
    """Compose readers only within the already admitted exact profile worker."""

    def __call__(self, *, profile_id: UUID, operation: PinnedAuthorityOperation) -> DiagnosticsReadPorts:
        """Return exact-profile encrypted run storage and canonical local auth probe."""
        ...


@dataclass(frozen=True, slots=True)
class DiagnosticsTelemetryFlushPorts:
    """Local readers plus fresh settings and the canonical telemetry sink factory."""

    profile_id: UUID
    operation: PinnedAuthorityOperation
    run_telemetry_port: DiagnosticRunTelemetryPort
    auth_probe_port: DiagnosticAuthProbePort
    settings_factory: Callable[[], Settings]
    sink_factory: Callable[[Settings], TelemetrySink]


class DiagnosticsTelemetryFlushPortsFactory(Protocol):
    """Compose telemetry capabilities without starting a remote request."""

    def __call__(self, *, profile_id: UUID, operation: PinnedAuthorityOperation) -> DiagnosticsTelemetryFlushPorts:
        """Return capabilities for the immutable profile and authority pin."""
        ...
