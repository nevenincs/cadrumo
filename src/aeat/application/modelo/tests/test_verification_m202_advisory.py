"""M202 silent-under-declaration verification advisory tests."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.resources import resources
from ....domain.calculations.registry._ids import CasillaId, validated_casilla_id
from ....domain.calculations.registry._schema import VerificationPredicateDefinition
from ....domain.modelos._verification_report import (
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from .._verification_actions import evaluate_verification_predicates
from ._verification_substance_support import _workflow_profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_M202_PREDICATE_ID = "modelo-202-base-imponible-previa-determinada-cuando-resultado-positivo"

_CASILLA_04: CasillaId = validated_casilla_id("04", surface="test_verification_m202_advisory.casilla")
_CASILLA_13: CasillaId = validated_casilla_id("13", surface="test_verification_m202_advisory.casilla")

_M202_REVISION_IDS = ("2019-2022", "2023-2024", "2025-y-siguientes")


def _m202_advisory_predicate(revision_id: str) -> VerificationPredicateDefinition:
    """Load the shipped M202 silent-under-declaration advisory from the authority."""
    revision = resources().modelos.authority.validate_modelo("202").revisions[revision_id]
    predicate = next(p for p in revision.verification_predicates if p.predicate_id == _M202_PREDICATE_ID)
    assert predicate.finding_kind == "ADVISORY"
    assert predicate.expression == 'implies_nonzero(["04", "13"])'
    return predicate


@pytest.mark.parametrize("revision_id", _M202_REVISION_IDS)
def test_m202_advisory_ships_in_every_revision(revision_id: str) -> None:
    """Every M202 revision carries the clave 04 -> clave 13 silent-under-declaration advisory."""
    predicate = _m202_advisory_predicate(revision_id)
    legal_refs = tuple(str(r) for r in predicate.legal_refs)
    assert "ley-27-2014:art-40-3" in legal_refs
    assert "ley-27-2014:art-40" in legal_refs


@pytest.mark.parametrize("revision_id", _M202_REVISION_IDS)
def test_m202_advisory_fires_when_resultado_positive_but_base_zero(revision_id: str) -> None:
    """Positive clave 04 with zero clave 13 surfaces a warning advisory."""
    predicate = _m202_advisory_predicate(revision_id)
    casilla_values: dict[CasillaId, Decimal] = {
        _CASILLA_04: Decimal("140000.00"),
        _CASILLA_13: Decimal("0"),
    }

    findings = evaluate_verification_predicates((predicate,), casilla_values, _workflow_profile())

    assert len(findings) == 1
    assert findings[0].kind is ModeloVerificationFindingKind.ADVISORY
    assert findings[0].severity is ModeloVerificationFindingSeverity.WARNING
    assert "ley-27-2014:art-40-3" in findings[0].legal_refs


@pytest.mark.parametrize("revision_id", _M202_REVISION_IDS)
def test_m202_advisory_silent_when_base_imponible_previa_present(revision_id: str) -> None:
    """Positive clave 04 and positive clave 13 satisfy the implication."""
    predicate = _m202_advisory_predicate(revision_id)
    casilla_values: dict[CasillaId, Decimal] = {
        _CASILLA_04: Decimal("140000.00"),
        _CASILLA_13: Decimal("140000.00"),
    }

    findings = evaluate_verification_predicates((predicate,), casilla_values, _workflow_profile())
    assert findings == []


@pytest.mark.parametrize("revision_id", _M202_REVISION_IDS)
def test_m202_advisory_silent_when_no_resultado_contable(revision_id: str) -> None:
    """No positive resultado contable holds trivially (losses, zero activity)."""
    predicate = _m202_advisory_predicate(revision_id)

    explicit_zero: dict[CasillaId, Decimal] = {_CASILLA_04: Decimal("0"), _CASILLA_13: Decimal("0")}
    negative: dict[CasillaId, Decimal] = {_CASILLA_04: Decimal("-5000.00"), _CASILLA_13: Decimal("0")}
    absent: dict[CasillaId, Decimal] = {}

    assert evaluate_verification_predicates((predicate,), explicit_zero, _workflow_profile()) == []
    assert evaluate_verification_predicates((predicate,), negative, _workflow_profile()) == []
    assert evaluate_verification_predicates((predicate,), absent, _workflow_profile()) == []


# 2025-only B2 casos especificos tipo-3/tipo-4 tramo guards (deferred-items
# audit, m202-deferred-items, 2026-06-30): clave 61/62 -> clave 63 and clave
# 64/65 -> clave 66 are both formula-derived via the ``percent`` operator.

_M202_B2_TIPO_3_PREDICATE_ID = "modelo-202-2025-b2-base-tipo-3-implica-importe-pago-fraccionado-tipo-3"
_M202_B2_TIPO_4_PREDICATE_ID = "modelo-202-2025-b2-base-tipo-4-implica-importe-pago-fraccionado-tipo-4"

_CASILLA_61: CasillaId = validated_casilla_id("61", surface="test_verification_m202_advisory.casilla")
_CASILLA_63: CasillaId = validated_casilla_id("63", surface="test_verification_m202_advisory.casilla")
_CASILLA_64: CasillaId = validated_casilla_id("64", surface="test_verification_m202_advisory.casilla")
_CASILLA_66: CasillaId = validated_casilla_id("66", surface="test_verification_m202_advisory.casilla")


def _m202_2025_predicate(predicate_id: str) -> VerificationPredicateDefinition:
    """Load a shipped 2025-y-siguientes-only M202 silent-under-declaration advisory."""
    revision = resources().modelos.authority.validate_modelo("202").revisions["2025-y-siguientes"]
    return next(p for p in revision.verification_predicates if p.predicate_id == predicate_id)


@pytest.mark.parametrize(
    ("predicate_id", "antecedent", "consequent"),
    [
        (_M202_B2_TIPO_3_PREDICATE_ID, _CASILLA_61, _CASILLA_63),
        (_M202_B2_TIPO_4_PREDICATE_ID, _CASILLA_64, _CASILLA_66),
    ],
)
def test_m202_2025_b2_tramo_advisory_ships_and_is_grounded(
    predicate_id: str, antecedent: CasillaId, consequent: CasillaId
) -> None:
    predicate = _m202_2025_predicate(predicate_id)
    assert predicate.finding_kind == "ADVISORY"
    assert predicate.expression == f'implies_nonzero(["{antecedent}", "{consequent}"])'
    legal_refs = tuple(str(r) for r in predicate.legal_refs)
    assert "ley-27-2014:art-40-3" in legal_refs
    assert "ley-27-2014:art-29" in legal_refs


@pytest.mark.parametrize(
    ("predicate_id", "antecedent", "consequent"),
    [
        (_M202_B2_TIPO_3_PREDICATE_ID, _CASILLA_61, _CASILLA_63),
        (_M202_B2_TIPO_4_PREDICATE_ID, _CASILLA_64, _CASILLA_66),
    ],
)
def test_m202_2025_b2_tramo_advisory_fires_when_base_positive_but_importe_zero(
    predicate_id: str, antecedent: CasillaId, consequent: CasillaId
) -> None:
    """Positive tramo base with a zero computed importe surfaces a warning advisory."""
    predicate = _m202_2025_predicate(predicate_id)
    casilla_values: dict[CasillaId, Decimal] = {antecedent: Decimal("50000.00"), consequent: Decimal("0")}

    findings = evaluate_verification_predicates((predicate,), casilla_values, _workflow_profile())

    assert len(findings) == 1
    assert findings[0].kind is ModeloVerificationFindingKind.ADVISORY
    assert findings[0].severity is ModeloVerificationFindingSeverity.WARNING
    assert "ley-27-2014:art-40-3" in findings[0].legal_refs


@pytest.mark.parametrize(
    ("predicate_id", "antecedent", "consequent"),
    [
        (_M202_B2_TIPO_3_PREDICATE_ID, _CASILLA_61, _CASILLA_63),
        (_M202_B2_TIPO_4_PREDICATE_ID, _CASILLA_64, _CASILLA_66),
    ],
)
def test_m202_2025_b2_tramo_advisory_holds_when_importe_present(
    predicate_id: str, antecedent: CasillaId, consequent: CasillaId
) -> None:
    """Positive tramo base and positive computed importe satisfy the implication."""
    predicate = _m202_2025_predicate(predicate_id)
    casilla_values: dict[CasillaId, Decimal] = {antecedent: Decimal("50000.00"), consequent: Decimal("15000.00")}

    findings = evaluate_verification_predicates((predicate,), casilla_values, _workflow_profile())
    assert findings == []


@pytest.mark.parametrize(
    ("predicate_id", "antecedent", "consequent"),
    [
        (_M202_B2_TIPO_3_PREDICATE_ID, _CASILLA_61, _CASILLA_63),
        (_M202_B2_TIPO_4_PREDICATE_ID, _CASILLA_64, _CASILLA_66),
    ],
)
def test_m202_2025_b2_tramo_advisory_holds_trivially_when_base_not_used(
    predicate_id: str, antecedent: CasillaId, consequent: CasillaId
) -> None:
    """No declared tramo base holds trivially (the filer does not use this B2 tramo)."""
    predicate = _m202_2025_predicate(predicate_id)

    explicit_zero: dict[CasillaId, Decimal] = {antecedent: Decimal("0"), consequent: Decimal("0")}
    absent: dict[CasillaId, Decimal] = {}

    assert evaluate_verification_predicates((predicate,), explicit_zero, _workflow_profile()) == []
    assert evaluate_verification_predicates((predicate,), absent, _workflow_profile()) == []
