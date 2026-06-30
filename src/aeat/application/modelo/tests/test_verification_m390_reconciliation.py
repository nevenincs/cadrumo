"""M390 annual deducible-total reconciliation verification tests."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.resources import resources
from ....domain.calculations.registry import CasillaId, VerificationPredicateDefinition, validated_casilla_id
from ....domain.modelos._verification_report import (
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from .._verification_actions import evaluate_verification_predicates
from ._verification_substance_support import _workflow_profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PREDICATE_ID = "modelo-390-cuota-deducible-total-equals-reconciliacion-303"
_PREDICATE_EXPRESSION = 'equals(["iva.anual.cuota-deducible-total", "iva.anual.reconciliacion.deducible-303"])'
_PREDICATE_LEGAL_REFS = {
    "ley-37-1992:art-17",
    "ley-37-1992:art-84",
    "ley-37-1992:art-92",
    "rd-1624-1992:art-71",
    "orden-eha-3111-2009:art-1",
}


def _casilla_id(value: object) -> CasillaId:
    try:
        return validated_casilla_id(value, surface="test_verification_m390_reconciliation")
    except ValueError as exc:
        raise AssertionError(f"M390 verification fixture casilla key {value!r} is not a CasillaId") from exc


_CUOTA_DEDUCIBLE_TOTAL = _casilla_id("iva.anual.cuota-deducible-total")
_RECONCILIACION_DEDUCIBLE_303 = _casilla_id("iva.anual.reconciliacion.deducible-303")


def _predicate() -> VerificationPredicateDefinition:
    revision = resources().modelos.authority.validate_modelo("390").revisions["2010-y-siguientes"]
    predicate = next(item for item in revision.verification_predicates if item.predicate_id == _PREDICATE_ID)
    assert predicate.finding_kind == "BLOCKING_RULE"
    assert predicate.expression == _PREDICATE_EXPRESSION
    return predicate


def test_m390_deducible_reconciliation_predicate_ships_with_grounding() -> None:
    predicate = _predicate()

    assert set(str(ref) for ref in predicate.legal_refs) == _PREDICATE_LEGAL_REFS


def test_m390_deducible_reconciliation_blocks_when_annual_total_diverges_from_303_fold() -> None:
    predicate = _predicate()
    casilla_values: dict[CasillaId, Decimal] = {
        _CUOTA_DEDUCIBLE_TOTAL: Decimal("1200.00"),
        _RECONCILIACION_DEDUCIBLE_303: Decimal("900.00"),
    }

    findings = evaluate_verification_predicates((predicate,), casilla_values, _workflow_profile())

    assert len(findings) == 1
    assert findings[0].kind is ModeloVerificationFindingKind.BLOCKING_RULE
    assert findings[0].severity is ModeloVerificationFindingSeverity.BLOCKING
    assert set(findings[0].legal_refs) == _PREDICATE_LEGAL_REFS


def test_m390_deducible_reconciliation_passes_when_annual_total_matches_303_fold() -> None:
    predicate = _predicate()
    casilla_values: dict[CasillaId, Decimal] = {
        _CUOTA_DEDUCIBLE_TOTAL: Decimal("1200.00"),
        _RECONCILIACION_DEDUCIBLE_303: Decimal("1200.00"),
    }

    assert evaluate_verification_predicates((predicate,), casilla_values, _workflow_profile()) == []
