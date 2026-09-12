"""Outer composition for diagnostic run-health telemetry."""

from __future__ import annotations

from ..application.diagnostics_run_health_ports import DiagnosticRunTelemetryPort


def compose_diagnostics_run_health_port() -> DiagnosticRunTelemetryPort:
    """Bind the diagnostic read port to encrypted local run telemetry."""
    from ..adapters.outbound.llm.run_telemetry import (
        LLMRunTelemetryDiagnosticsAdapter,
        LLMRunTelemetryRecorder,
    )

    return LLMRunTelemetryDiagnosticsAdapter(LLMRunTelemetryRecorder())


__all__ = ["compose_diagnostics_run_health_port"]
