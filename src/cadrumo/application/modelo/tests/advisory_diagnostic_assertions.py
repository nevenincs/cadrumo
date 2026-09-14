"""Application-level assertions for operator-facing advisory diagnostics."""

from __future__ import annotations

from cadrumo.application.aggregation.source_mesh import CalculationSourceDiagnostic


def operator_text(diagnostic: CalculationSourceDiagnostic) -> str:
    """Return the complete operator-facing diagnostic line."""
    remedy = getattr(diagnostic, "remedy", None)
    message = diagnostic.message
    return message if remedy is None else f"{message} {remedy}"
