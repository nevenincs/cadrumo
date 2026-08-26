"""M123 silent-under-declaration verification advisory tests."""

from __future__ import annotations

from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.schema_verification import VerificationPredicateDefinition

from ....core import CasillaId
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.modelos import (
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from .._verification_actions import evaluate_verification_predicates
from ._verification_substance_support import _CASILLA_06, _CASILLA_09, _workflow_profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_M123_ADVISORY_PREDICATE_ID = "modelo-123-2024-base-total-implica-retenciones-total"


def _m123_advisory_predicate() -> VerificationPredicateDefinition:
    """Load the shipped M123 silent-under-declaration advisory from the authority."""
    revision = bundled_authority().validate_modelo("123").revisions["2024-y-siguientes"]
    predicate = next(p for p in revision.verification_predicates if p.predicate_id == _M123_ADVISORY_PREDICATE_ID)
    assert predicate.finding_kind == "ADVISORY"
    assert predicate.expression == 'implies_nonzero(["06", "09"])'
    return predicate


def test_m123_advisory_ships_with_legal_grounding() -> None:
    """The M123 2024-y-siguientes revision carries the C06->C09 silent-under-declaration advisory."""
    predicate = _m123_advisory_predicate()
    legal_refs = tuple(str(r) for r in predicate.legal_refs)
    assert "rd-439-2007:art-90" in legal_refs
    assert "rd-439-2007:art-75" in legal_refs
    assert "ley-35-2006:art-101" in legal_refs


def test_m123_advisory_fires_when_base_total_positive_but_retenciones_total_zero() -> None:
    """Positive C06 with zero C09 surfaces a warning advisory."""
    predicate = _m123_advisory_predicate()
    casilla_values: dict[CasillaId, Decimal] = {
        _CASILLA_06: Decimal("42000.00"),
        _CASILLA_09: Decimal("0"),
    }

    findings = evaluate_verification_predicates((predicate,), casilla_values, _workflow_profile())

    assert len(findings) == 1
    assert findings[0].kind is ModeloVerificationFindingKind.ADVISORY
    assert findings[0].severity is ModeloVerificationFindingSeverity.WARNING
    assert "rd-439-2007:art-90" in findings[0].legal_refs
    assert "rd-439-2007:art-75" in findings[0].legal_refs


def test_m123_advisory_silent_when_retenciones_total_present() -> None:
    """Positive C06 and positive C09 satisfy the implication."""
    predicate = _m123_advisory_predicate()
    casilla_values: dict[CasillaId, Decimal] = {
        _CASILLA_06: Decimal("42000.00"),
        _CASILLA_09: Decimal("7980.00"),
    }

    findings = evaluate_verification_predicates((predicate,), casilla_values, _workflow_profile())
    assert findings == []


def test_m123_advisory_silent_when_no_retenible_activity() -> None:
    """No base-total activity (zero or absent) holds trivially."""
    predicate = _m123_advisory_predicate()

    explicit_zero: dict[CasillaId, Decimal] = {_CASILLA_06: Decimal("0"), _CASILLA_09: Decimal("0")}
    absent: dict[CasillaId, Decimal] = {}

    assert evaluate_verification_predicates((predicate,), explicit_zero, _workflow_profile()) == []
    assert evaluate_verification_predicates((predicate,), absent, _workflow_profile()) == []
