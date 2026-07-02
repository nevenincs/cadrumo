"""M714 (Patrimonio) silent-under-declaration verification advisory tests."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.resources import resources
from ....domain.calculations.registry import (
    CasillaId,
    VerificationPredicateDefinition,
    validated_casilla_id,
)
from ....domain.modelos import (
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from .._verification_actions import evaluate_verification_predicates
from ._verification_substance_support import _workflow_profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_M714_PREDICATE_ID = "modelo-714-cuota-integra-implica-total-cuota-integra"
_CASILLA_CUOTA_INTEGRA: CasillaId = validated_casilla_id(
    "patrimonio.cuota-integra",
    surface="test casilla id",
)
_CASILLA_TOTAL_CUOTA_INTEGRA: CasillaId = validated_casilla_id(
    "patrimonio.total-cuota-integra",
    surface="test casilla id",
)


def _m714_advisory_predicate() -> VerificationPredicateDefinition:
    """Load the shipped M714 silent-under-declaration advisory from the authority."""
    revision = resources().modelos.authority.validate_modelo("714").revisions["2021-y-siguientes"]
    predicate = next(p for p in revision.verification_predicates if p.predicate_id == _M714_PREDICATE_ID)
    assert predicate.finding_kind == "ADVISORY"
    assert predicate.expression == ('implies_nonzero(["patrimonio.cuota-integra", "patrimonio.total-cuota-integra"])')
    return predicate


def test_m714_advisory_ships_on_2021_y_siguientes_revision() -> None:
    """The 2021-y-siguientes revision carries the C29->C40 silent-under-declaration advisory."""
    predicate = _m714_advisory_predicate()
    assert "ley-19-1991:art-30" in tuple(str(r) for r in predicate.legal_refs)


def test_m714_advisory_fires_when_cuota_integra_positive_but_total_zero() -> None:
    """Positive cuota integra (C29) with zero total cuota integra (C40) surfaces a warning advisory."""
    predicate = _m714_advisory_predicate()
    casilla_values: dict[CasillaId, Decimal] = {
        _CASILLA_CUOTA_INTEGRA: Decimal("2506.86"),
        _CASILLA_TOTAL_CUOTA_INTEGRA: Decimal("0"),
    }

    findings = evaluate_verification_predicates((predicate,), casilla_values, _workflow_profile())

    assert len(findings) == 1
    assert findings[0].kind is ModeloVerificationFindingKind.ADVISORY
    assert findings[0].severity is ModeloVerificationFindingSeverity.WARNING
    assert "ley-19-1991:art-30" in findings[0].legal_refs


def test_m714_advisory_silent_when_total_cuota_integra_present() -> None:
    """Positive cuota integra and a positive total cuota integra satisfy the implication."""
    predicate = _m714_advisory_predicate()
    casilla_values: dict[CasillaId, Decimal] = {
        _CASILLA_CUOTA_INTEGRA: Decimal("2506.86"),
        _CASILLA_TOTAL_CUOTA_INTEGRA: Decimal("2506.86"),
    }

    findings = evaluate_verification_predicates((predicate,), casilla_values, _workflow_profile())
    assert findings == []


def test_m714_advisory_silent_when_cuota_integra_zero_or_negative() -> None:
    """No (or negative) cuota integra holds the implication trivially."""
    predicate = _m714_advisory_predicate()

    explicit_zero: dict[CasillaId, Decimal] = {
        _CASILLA_CUOTA_INTEGRA: Decimal("0"),
        _CASILLA_TOTAL_CUOTA_INTEGRA: Decimal("0"),
    }
    absent: dict[CasillaId, Decimal] = {}

    assert evaluate_verification_predicates((predicate,), explicit_zero, _workflow_profile()) == []
    assert evaluate_verification_predicates((predicate,), absent, _workflow_profile()) == []
