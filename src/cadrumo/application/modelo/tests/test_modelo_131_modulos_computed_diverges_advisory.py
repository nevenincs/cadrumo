"""Modelo 131 módulos-engine-vs-declared-C01 ADVISORY predicate.

The first slice of the estimación-objetiva módulos engine keeps casilla 01
("Suma de rendimientos netos") a manual operator input while wiring a
computed reference figure (``modulos-rendimiento-neto-actividad``) for a
bounded first-slice of tabled IAE activities. The
``advisory_when_computed_diverges(["01", "modulos-rendimiento-neto-actividad"])``
predicate surfaces a discrepancy between the two without ever blocking the
filing — the computed reference intentionally omits fases 2ª/3ª correcting
factors the taxpayer may legitimately claim.

Semantics are derived from the ``advisory_when_computed_diverges``
DSL contract directly, never from any registry formula output — no
hand-computed Decimal, no tautology.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.casilla_id import CasillaId, validated_casilla_id
from ....domain.calculations.registry.schema_verification import VerificationPredicateDefinition
from ....domain.deadlines.models import IVARegime, TaxpayerProfile
from ....domain.modelos.verification_report import ModeloVerificationFindingKind
from .._verification_predicates import evaluate_advisory_predicate_fires
from ..verification_actions import _evaluate_verification_predicates

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_EXPRESSION = 'advisory_when_computed_diverges(["01", "modulos-rendimiento-neto-actividad"])'
_CASILLA_01: CasillaId = validated_casilla_id("01", surface="m131 modulos advisory test")
_COMPUTED: CasillaId = validated_casilla_id(
    "modulos-rendimiento-neto-actividad",
    surface="m131 modulos advisory test",
)


def _profile() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="X1234567L",
        iva_regime=IVARegime.GENERAL,
        has_employees=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
    )


def _predicate() -> VerificationPredicateDefinition:
    return VerificationPredicateDefinition(
        predicate_id="modelo-131-2025-modulos-computed-diverges-de-c01",
        legal_refs=("ley-35-2006:art-31", "orden-hac-1347-2024:art-4", "orden-hac-1347-2024:da-1"),
        expression=_EXPRESSION,
        finding_kind="ADVISORY",
    )


def test_advisory_fires_when_declared_differs_from_computed_by_more_than_a_cent() -> None:
    values: dict[CasillaId, Decimal] = {
        _CASILLA_01: Decimal("15000.00"),
        _COMPUTED: Decimal("21995.99"),
    }
    assert evaluate_advisory_predicate_fires(_EXPRESSION, values) is True


def test_advisory_fires_when_declared_absent_but_computed_positive() -> None:
    """Absent casilla 01 (reads as Decimal(0)) with a positive computed reference fires."""
    values: dict[CasillaId, Decimal] = {_COMPUTED: Decimal("21995.99")}
    assert evaluate_advisory_predicate_fires(_EXPRESSION, values) is True


def test_advisory_does_not_fire_when_declared_matches_computed() -> None:
    values: dict[CasillaId, Decimal] = {
        _CASILLA_01: Decimal("21995.99"),
        _COMPUTED: Decimal("21995.99"),
    }
    assert evaluate_advisory_predicate_fires(_EXPRESSION, values) is False


def test_advisory_does_not_fire_within_one_cent_tolerance() -> None:
    values: dict[CasillaId, Decimal] = {
        _CASILLA_01: Decimal("21995.98"),
        _COMPUTED: Decimal("21995.99"),
    }
    assert evaluate_advisory_predicate_fires(_EXPRESSION, values) is False


def test_advisory_does_not_fire_when_computed_is_zero_untabled_activity() -> None:
    """Zero computed reference (untabled epígrafe) → nothing to reconcile against, no fire.

    A filer whose activity is not yet in the bounded first-slice coefficient
    table has no engine coverage; casilla 01 stays the sole authoritative
    manual input and no discrepancy prompt is meaningful.
    """
    values: dict[CasillaId, Decimal] = {
        _CASILLA_01: Decimal("8500.00"),
        _COMPUTED: Decimal("0"),
    }
    assert evaluate_advisory_predicate_fires(_EXPRESSION, values) is False


def test_advisory_does_not_fire_when_computed_absent() -> None:
    values: dict[CasillaId, Decimal] = {_CASILLA_01: Decimal("8500.00")}
    assert evaluate_advisory_predicate_fires(_EXPRESSION, values) is False


def test_emits_single_advisory_warning_finding_when_violated() -> None:
    values: dict[CasillaId, Decimal] = {
        _CASILLA_01: Decimal("15000.00"),
        _COMPUTED: Decimal("21995.99"),
    }
    findings = _evaluate_verification_predicates((_predicate(),), values, _profile())
    assert len(findings) == 1
    assert findings[0].kind is ModeloVerificationFindingKind.ADVISORY
