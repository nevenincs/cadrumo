"""Assertion helper for the capped boxes a calculation reports as proven zeros."""

from __future__ import annotations

from ....application.aggregation.source_mesh import CalculationSourceDiagnostic
from ....application.modelo.calculation_note_gate import gate_refuses
from ....core.aggregation import BindingValueOutcome
from ....domain.modelos.calculation_revision_sources import CalculationNoteSentence

_WITHHOLDING_BOX = "0599"
_WITHHOLDING_BINDING = "renta-ledger-actividad-retenciones-0599"
_CREDIT_BOXES = frozenset({"0596", "0597", "0598", "0599", "0603"})


def assert_only_proven_zero_capped_diagnostics(diagnostics: tuple[CalculationSourceDiagnostic, ...]) -> None:
    """Require every diagnostic to be a capped box's proven zero the gate lets through, box 0599 among them.

    An empty ledger proves each capped activity box zero: the withholding box
    0599 and the bank-dated income and expense boxes beside it. A credit box
    whose declared cross-check holds nothing, such as a borrador never imported,
    is noted as not cross-checked; that note withholds nothing and is no zero.
    """
    assert diagnostics, diagnostics
    for diagnostic in diagnostics:
        if diagnostic.reason == "credit_cross_check_absent":
            assert diagnostic.fact is not None
            assert diagnostic.fact.sentence is CalculationNoteSentence.CREDIT_CROSS_CHECK_ABSENT
            assert diagnostic.casilla_id in _CREDIT_BOXES, diagnostic
            assert not gate_refuses(diagnostic.reason, diagnostic.binding_source, diagnostic.value_outcome)
            continue
        assert diagnostic.reason == "advisory_binding_value", diagnostic
        assert diagnostic.value_outcome is BindingValueOutcome.PROVEN_ZERO, diagnostic
        assert diagnostic.fact is not None
        assert diagnostic.fact.sentence is CalculationNoteSentence.ADVISORY_VALUE_PROVEN_ZERO
        assert dict(diagnostic.fact.values)["amount"] == "0"
        assert not gate_refuses(diagnostic.reason, diagnostic.binding_source, diagnostic.value_outcome)
    assert (_WITHHOLDING_BOX, _WITHHOLDING_BINDING) in {
        (diagnostic.casilla_id, diagnostic.binding_id) for diagnostic in diagnostics
    }
