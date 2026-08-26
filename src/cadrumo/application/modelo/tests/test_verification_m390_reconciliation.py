"""M390 annual total reconciliation verification tests."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache

import pytest

from cadrumo.domain.calculations.registry.schema_verification import VerificationPredicateDefinition

from ....core import CasillaId, validated_casilla_id
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.modelos import (
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from .._verification_actions import evaluate_verification_predicates
from ._verification_substance_support import _workflow_profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@dataclass(frozen=True)
class _PredicateCase:
    label: str
    predicate_id: str
    total_id: CasillaId
    reconciliation_id: CasillaId
    expression: str
    legal_refs: frozenset[str]


_PREDICATE_CASES = (
    _PredicateCase(
        label="devengada",
        predicate_id="modelo-390-cuota-devengada-total-equals-reconciliacion-303",
        total_id=validated_casilla_id(
            "iva.anual.cuota-devengada-total", surface="test_verification_m390_reconciliation"
        ),
        reconciliation_id=validated_casilla_id(
            "iva.anual.reconciliacion.devengada-303", surface="test_verification_m390_reconciliation"
        ),
        expression='equals(["iva.anual.cuota-devengada-total", "iva.anual.reconciliacion.devengada-303"])',
        legal_refs=frozenset(
            {
                "ley-37-1992:art-88",
                "ley-37-1992:art-90",
                "ley-37-1992:art-91",
                "rd-1624-1992:art-71",
                "orden-eha-3111-2009:art-1",
            },
        ),
    ),
    _PredicateCase(
        label="deducible",
        predicate_id="modelo-390-cuota-deducible-total-equals-reconciliacion-303",
        total_id=validated_casilla_id(
            "iva.anual.cuota-deducible-total", surface="test_verification_m390_reconciliation"
        ),
        reconciliation_id=validated_casilla_id(
            "iva.anual.reconciliacion.deducible-303", surface="test_verification_m390_reconciliation"
        ),
        expression='equals(["iva.anual.cuota-deducible-total", "iva.anual.reconciliacion.deducible-303"])',
        legal_refs=frozenset(
            {
                "ley-37-1992:art-17",
                "ley-37-1992:art-84",
                "ley-37-1992:art-92",
                "rd-1624-1992:art-71",
                "orden-eha-3111-2009:art-1",
            },
        ),
    ),
    _PredicateCase(
        label="resultado",
        predicate_id="modelo-390-resultado-regimen-general-equals-reconciliacion-303",
        total_id=validated_casilla_id(
            "iva.anual.resultado-regimen-general", surface="test_verification_m390_reconciliation"
        ),
        reconciliation_id=validated_casilla_id(
            "iva.anual.reconciliacion.resultado-303", surface="test_verification_m390_reconciliation"
        ),
        expression='equals(["iva.anual.resultado-regimen-general", "iva.anual.reconciliacion.resultado-303"])',
        legal_refs=frozenset(
            {
                "ley-37-1992:art-88",
                "ley-37-1992:art-92",
                "rd-1624-1992:art-71",
                "orden-eha-3111-2009:art-1",
            },
        ),
    ),
)


@lru_cache
def _predicate(predicate_id: str, expression: str) -> VerificationPredicateDefinition:
    revision = bundled_authority().validate_modelo("390").revisions["2010-y-siguientes"]
    predicate = next(item for item in revision.verification_predicates if item.predicate_id == predicate_id)
    assert predicate.finding_kind == "BLOCKING_RULE"
    assert predicate.expression == expression
    return predicate


def test_m390_reconciliation_predicates_ship_with_grounding() -> None:
    for case in _PREDICATE_CASES:
        predicate = _predicate(case.predicate_id, case.expression)

        assert frozenset(str(ref) for ref in predicate.legal_refs) == case.legal_refs, case.label


def test_m390_reconciliation_blocks_when_annual_total_diverges_from_303_fold() -> None:
    for case in _PREDICATE_CASES:
        predicate = _predicate(case.predicate_id, case.expression)
        casilla_values: dict[CasillaId, Decimal] = {
            case.total_id: Decimal("1200.00"),
            case.reconciliation_id: Decimal("900.00"),
        }

        findings = evaluate_verification_predicates((predicate,), casilla_values, _workflow_profile())

        assert len(findings) == 1, case.label
        assert findings[0].kind is ModeloVerificationFindingKind.BLOCKING_RULE, case.label
        assert findings[0].severity is ModeloVerificationFindingSeverity.BLOCKING, case.label
        assert frozenset(findings[0].legal_refs) == case.legal_refs, case.label


def test_m390_reconciliation_passes_when_annual_total_matches_303_fold() -> None:
    for case in _PREDICATE_CASES:
        predicate = _predicate(case.predicate_id, case.expression)
        casilla_values: dict[CasillaId, Decimal] = {
            case.total_id: Decimal("1200.00"),
            case.reconciliation_id: Decimal("1200.00"),
        }

        assert evaluate_verification_predicates((predicate,), casilla_values, _workflow_profile()) == [], case.label
