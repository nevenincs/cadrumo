"""Composition-owned exact-profile capabilities for registered diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from ..domain.calculations.registry.authority import PinnedAuthorityOperation
from .diagnostics_run_health_ports import DiagnosticAuthProbePort, DiagnosticRunRecordPort


@dataclass(frozen=True, slots=True)
class DiagnosticsReadPorts:
    """One immutable worker identity and its local diagnostic readers."""

    profile_id: UUID
    operation: PinnedAuthorityOperation
    run_record_port: DiagnosticRunRecordPort
    auth_probe_port: DiagnosticAuthProbePort


class DiagnosticsReadPortsFactory(Protocol):
    """Compose readers only within the already admitted exact profile worker."""

    def __call__(self, *, profile_id: UUID, operation: PinnedAuthorityOperation) -> DiagnosticsReadPorts:
        """Return exact-profile encrypted run storage and canonical local auth probe."""
        ...
