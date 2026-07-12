"""M303 prorrata settlement silent-under-declaration verification advisory tests.

See Also:
    :class:`~domain.calculations.registry.VerificationPredicateDefinition`
        Registry-authored predicate type loaded from the M303 fragmented
        revision.
    :func:`~application.modelo._verification_actions.evaluate_verification_predicates`
        Verification predicate evaluator exercised directly by these tests.
    :class:`~domain.modelos.ModeloVerificationFindingKind`
        Finding-kind enum proving the guard remains advisory, not blocking.
    :func:`~application.modelo.tests._verification_substance_support._workflow_profile`
        Real workflow-profile fixture used by the predicate evaluator.
    :mod:`~application.modelo.tests.test_prorrata_regularizacion_advisory`
        Calculate-path prorrata advisory regression that complements this
        settlement verify gate.
"""

from __future__ import annotations

from decimal import Decimal
from functools import lru_cache

import pytest

from ....core.resources import resources
from ....domain.calculations.registry import (
    CasillaId,
    VerificationPredicateDefinition,
    validated_casilla_id,
)
from ....domain.modelos import ModeloVerificationFindingKind, ModeloVerificationFindingSeverity
from .._verification_actions import evaluate_verification_predicates
from ._verification_substance_support import _workflow_profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_REVISION_ID = "2023-y-siguientes"
_PREDICATE_ID = "modelo-303-prorrata-regularizacion-determinada-cuando-volumen-anual-declarado"
_EXPRESSION = 'implies_nonzero(["iva.prorrata-volumen-total", "44"])'

_VOLUMEN_TOTAL: CasillaId = validated_casilla_id("iva.prorrata-volumen-total", surface="test casilla id")
_CASILLA_44: CasillaId = validated_casilla_id("44", surface="test casilla id")


@lru_cache
def _m303_prorrata_predicate() -> VerificationPredicateDefinition:
    revision = resources().modelos.authority.validate_modelo("303").revisions[_REVISION_ID]
    predicate = next(p for p in revision.verification_predicates if p.predicate_id == _PREDICATE_ID)
    assert predicate.finding_kind == "ADVISORY"
    assert predicate.expression == _EXPRESSION
    return predicate


def test_m303_prorrata_settlement_advisory_ships_on_fragmented_revision() -> None:
    """The live M303 2023 revision carries the casilla-44 settlement advisory."""
    predicate = _m303_prorrata_predicate()
    legal_refs = tuple(str(ref) for ref in predicate.legal_refs)

    assert "ley-37-1992:art-104" in legal_refs
    assert "ley-37-1992:art-105" in legal_refs


def test_m303_prorrata_settlement_advisory_fires_when_volume_declared_but_c44_zero() -> None:
    """Declared annual prorrata volume with zero C44 surfaces a non-blocking warning."""
    predicate = _m303_prorrata_predicate()
    casilla_values: dict[CasillaId, Decimal] = {
        _VOLUMEN_TOTAL: Decimal("100000.00"),
        _CASILLA_44: Decimal("0"),
    }

    findings = evaluate_verification_predicates((predicate,), casilla_values, _workflow_profile())

    assert len(findings) == 1
    assert findings[0].kind is ModeloVerificationFindingKind.ADVISORY
    assert findings[0].severity is ModeloVerificationFindingSeverity.WARNING
    assert "ley-37-1992:art-104" in findings[0].legal_refs
    assert "ley-37-1992:art-105" in findings[0].legal_refs


def test_m303_prorrata_settlement_advisory_silent_when_c44_present() -> None:
    """A non-zero settlement regularizacion satisfies the implication."""
    predicate = _m303_prorrata_predicate()
    casilla_values: dict[CasillaId, Decimal] = {
        _VOLUMEN_TOTAL: Decimal("100000.00"),
        _CASILLA_44: Decimal("-217.60"),
    }

    assert evaluate_verification_predicates((predicate,), casilla_values, _workflow_profile()) == []


def test_m303_prorrata_settlement_advisory_silent_for_art94_full_deduction_default() -> None:
    """No annual prorrata volume data keeps the full-deduction default untouched."""
    predicate = _m303_prorrata_predicate()
    explicit_zero: dict[CasillaId, Decimal] = {
        _VOLUMEN_TOTAL: Decimal("0"),
        _CASILLA_44: Decimal("0"),
    }

    assert evaluate_verification_predicates((predicate,), explicit_zero, _workflow_profile()) == []
    assert evaluate_verification_predicates((predicate,), {}, _workflow_profile()) == []
