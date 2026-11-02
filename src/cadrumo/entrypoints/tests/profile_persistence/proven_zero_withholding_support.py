"""Assertion helper for the withholding box a calculation reports as a proven zero."""

from __future__ import annotations

from ....application.aggregation.source_mesh import CalculationSourceDiagnostic
from ....application.modelo.calculation_note_gate import gate_refuses
from ....core.aggregation import BindingValueOutcome
from ....domain.modelos.calculation_revision_sources import CalculationNoteSentence

_WITHHOLDING_BOX = "0599"
_WITHHOLDING_BINDING = "renta-ledger-actividad-retenciones-0599"


def assert_only_proven_zero_withholding_diagnostic(diagnostics: tuple[CalculationSourceDiagnostic, ...]) -> None:
    """Require the sole diagnostic to be the box 0599 proven zero, which the gate lets through."""
    assert len(diagnostics) == 1, diagnostics
    (diagnostic,) = diagnostics
    assert diagnostic.reason == "advisory_binding_value"
    assert diagnostic.casilla_id == _WITHHOLDING_BOX
    assert diagnostic.binding_id == _WITHHOLDING_BINDING
    assert diagnostic.value_outcome is BindingValueOutcome.PROVEN_ZERO
    assert diagnostic.fact is not None
    assert diagnostic.fact.sentence is CalculationNoteSentence.ADVISORY_VALUE_PROVEN_ZERO
    assert dict(diagnostic.fact.values)["amount"] == "0"
    assert not gate_refuses(diagnostic.reason, diagnostic.binding_source, diagnostic.value_outcome)
