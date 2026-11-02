"""Assertion helper for the capped boxes a calculation reports as proven zeros."""

from __future__ import annotations

from ....application.aggregation.source_mesh import CalculationSourceDiagnostic
from ....application.modelo.calculation_note_gate import gate_refuses
from ....core.aggregation import BindingValueOutcome
from ....domain.modelos.calculation_revision_sources import CalculationNoteSentence

_WITHHOLDING_BOX = "0599"
_WITHHOLDING_BINDING = "renta-ledger-actividad-retenciones-0599"


def assert_only_proven_zero_capped_diagnostics(diagnostics: tuple[CalculationSourceDiagnostic, ...]) -> None:
    """Require every diagnostic to be a capped box's proven zero the gate lets through, box 0599 among them.

    An empty ledger proves each capped activity box zero: the withholding box
    0599 and the bank-dated income and expense boxes beside it.
    """
    assert diagnostics, diagnostics
    for diagnostic in diagnostics:
        assert diagnostic.reason == "advisory_binding_value", diagnostic
        assert diagnostic.value_outcome is BindingValueOutcome.PROVEN_ZERO, diagnostic
        assert diagnostic.fact is not None
        assert diagnostic.fact.sentence is CalculationNoteSentence.ADVISORY_VALUE_PROVEN_ZERO
        assert dict(diagnostic.fact.values)["amount"] == "0"
        assert not gate_refuses(diagnostic.reason, diagnostic.binding_source, diagnostic.value_outcome)
    assert (_WITHHOLDING_BOX, _WITHHOLDING_BINDING) in {
        (diagnostic.casilla_id, diagnostic.binding_id) for diagnostic in diagnostics
    }
