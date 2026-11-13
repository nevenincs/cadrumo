"""Assertion helper for the notes a calculation over an empty ledger may carry."""

from __future__ import annotations

from ....application.aggregation.source_mesh import CalculationSourceDiagnostic
from ....application.modelo.calculation_note_gate import gate_refuses
from ....core.aggregation import BindingSourceKind
from ....domain.modelos.calculation_revision_sources import CalculationNoteSentence

_CREDIT_BOXES = frozenset({"0596", "0597", "0598", "0599", "0603"})


def assert_only_empty_source_notes(diagnostics: tuple[CalculationSourceDiagnostic, ...]) -> None:
    """Require every diagnostic to be a disclosure of an empty source, which the gate lets through.

    A credit box whose declared cross-check holds nothing, such as a borrador
    never imported, is noted as not cross-checked. A year with no pension
    contribution certificate recorded is noted once, naming no box, because the
    contribution boxes stay blank until the filer records one or types them.
    Neither note withholds anything.
    """
    for diagnostic in diagnostics:
        assert diagnostic.fact is not None, diagnostic
        if diagnostic.binding_source is BindingSourceKind.PREVISION_SOCIAL_CONTRIBUTION:
            assert diagnostic.reason == "source_issue", diagnostic
            assert diagnostic.fact.sentence is CalculationNoteSentence.PREVISION_SOCIAL_CONTRIBUTION_NOT_CERTIFIED
            assert diagnostic.casilla_id is None, diagnostic
        else:
            assert diagnostic.reason == "credit_cross_check_absent", diagnostic
            assert diagnostic.fact.sentence is CalculationNoteSentence.CREDIT_CROSS_CHECK_ABSENT
            assert diagnostic.casilla_id in _CREDIT_BOXES, diagnostic
        assert not gate_refuses(diagnostic.reason, diagnostic.binding_source, diagnostic.value_outcome)
