"""M202 silent-under-declaration verification advisory tests."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core import CasillaId, validated_casilla_id
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.schema_verification import VerificationPredicateDefinition
from ....domain.modelos import (
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
    revision = bundled_authority().validate_modelo("202").revisions[revision_id]
    predicate = next(p for p in revision.verification_predicates if p.predicate_id == _M202_PREDICATE_ID)
    assert predicate.finding_kind == "ADVISORY"
    assert predicate.expression == 'implies_nonzero(["04", "13"])'
    return predicate


def test_m202_advisory_ships_in_every_revision() -> None:
    """Every M202 revision carries the clave 04 -> clave 13 silent-under-declaration advisory."""
    for revision_id in _M202_REVISION_IDS:
        predicate = _m202_advisory_predicate(revision_id)
        legal_refs = tuple(str(r) for r in predicate.legal_refs)
        assert "ley-27-2014:art-40-3" in legal_refs, revision_id
        assert "ley-27-2014:art-40" in legal_refs, revision_id


def test_m202_advisory_fires_when_resultado_positive_but_base_zero() -> None:
    """Positive clave 04 with zero clave 13 surfaces a warning advisory."""
    for revision_id in _M202_REVISION_IDS:
        predicate = _m202_advisory_predicate(revision_id)
        casilla_values: dict[CasillaId, Decimal] = {
            _CASILLA_04: Decimal("140000.00"),
            _CASILLA_13: Decimal("0"),
        }

        findings = evaluate_verification_predicates((predicate,), casilla_values, _workflow_profile())

        assert len(findings) == 1, revision_id
        assert findings[0].kind is ModeloVerificationFindingKind.ADVISORY, revision_id
        assert findings[0].severity is ModeloVerificationFindingSeverity.WARNING, revision_id
        assert "ley-27-2014:art-40-3" in findings[0].legal_refs, revision_id


def test_m202_advisory_silent_when_base_imponible_previa_present() -> None:
    """Positive clave 04 and positive clave 13 satisfy the implication."""
    for revision_id in _M202_REVISION_IDS:
        predicate = _m202_advisory_predicate(revision_id)
        casilla_values: dict[CasillaId, Decimal] = {
            _CASILLA_04: Decimal("140000.00"),
            _CASILLA_13: Decimal("140000.00"),
        }

        findings = evaluate_verification_predicates((predicate,), casilla_values, _workflow_profile())
        assert findings == [], revision_id


def test_m202_advisory_silent_when_no_resultado_contable() -> None:
    """No positive resultado contable holds trivially (losses, zero activity)."""
    for revision_id in _M202_REVISION_IDS:
        predicate = _m202_advisory_predicate(revision_id)

        explicit_zero: dict[CasillaId, Decimal] = {_CASILLA_04: Decimal("0"), _CASILLA_13: Decimal("0")}
        negative: dict[CasillaId, Decimal] = {_CASILLA_04: Decimal("-5000.00"), _CASILLA_13: Decimal("0")}
        absent: dict[CasillaId, Decimal] = {}

        assert evaluate_verification_predicates((predicate,), explicit_zero, _workflow_profile()) == [], revision_id
        assert evaluate_verification_predicates((predicate,), negative, _workflow_profile()) == [], revision_id
        assert evaluate_verification_predicates((predicate,), absent, _workflow_profile()) == [], revision_id


# 2025-only B2 casos especificos tipo-3/tipo-4 tramo guards (deferred-items
# audit, m202-deferred-items, 2026-06-30): clave 61/62 -> clave 63 and clave
# 64/65 -> clave 66 are both formula-derived via the ``percent`` operator.

_M202_B2_TIPO_3_PREDICATE_ID = "modelo-202-2025-b2-base-tipo-3-implica-importe-pago-fraccionado-tipo-3"
_M202_B2_TIPO_4_PREDICATE_ID = "modelo-202-2025-b2-base-tipo-4-implica-importe-pago-fraccionado-tipo-4"

_CASILLA_61: CasillaId = validated_casilla_id("61", surface="test_verification_m202_advisory.casilla")
_CASILLA_63: CasillaId = validated_casilla_id("63", surface="test_verification_m202_advisory.casilla")
_CASILLA_64: CasillaId = validated_casilla_id("64", surface="test_verification_m202_advisory.casilla")
_CASILLA_66: CasillaId = validated_casilla_id("66", surface="test_verification_m202_advisory.casilla")
_M202_B2_TRAMO_CASES = (
    (_M202_B2_TIPO_3_PREDICATE_ID, _CASILLA_61, _CASILLA_63),
    (_M202_B2_TIPO_4_PREDICATE_ID, _CASILLA_64, _CASILLA_66),
)


def _m202_2025_predicate(predicate_id: str) -> VerificationPredicateDefinition:
    """Load a shipped 2025-y-siguientes-only M202 silent-under-declaration advisory."""
    revision = bundled_authority().validate_modelo("202").revisions["2025-y-siguientes"]
    return next(p for p in revision.verification_predicates if p.predicate_id == predicate_id)


def test_m202_2025_b2_tramo_advisory_ships_and_is_grounded() -> None:
    for predicate_id, antecedent, consequent in _M202_B2_TRAMO_CASES:
        predicate = _m202_2025_predicate(predicate_id)
        assert predicate.finding_kind == "ADVISORY", predicate_id
        assert predicate.expression == f'implies_nonzero(["{antecedent}", "{consequent}"])', predicate_id
        legal_refs = tuple(str(r) for r in predicate.legal_refs)
        assert "ley-27-2014:art-40-3" in legal_refs, predicate_id
        assert "ley-27-2014:art-29" in legal_refs, predicate_id


def test_m202_2025_b2_tramo_advisory_fires_when_base_positive_but_importe_zero() -> None:
    """Positive tramo base with a zero computed importe surfaces a warning advisory."""
    for predicate_id, antecedent, consequent in _M202_B2_TRAMO_CASES:
        predicate = _m202_2025_predicate(predicate_id)
        casilla_values: dict[CasillaId, Decimal] = {antecedent: Decimal("50000.00"), consequent: Decimal("0")}

        findings = evaluate_verification_predicates((predicate,), casilla_values, _workflow_profile())

        assert len(findings) == 1, predicate_id
        assert findings[0].kind is ModeloVerificationFindingKind.ADVISORY, predicate_id
        assert findings[0].severity is ModeloVerificationFindingSeverity.WARNING, predicate_id
        assert "ley-27-2014:art-40-3" in findings[0].legal_refs, predicate_id


def test_m202_2025_b2_tramo_advisory_holds_when_importe_present() -> None:
    """Positive tramo base and positive computed importe satisfy the implication."""
    for predicate_id, antecedent, consequent in _M202_B2_TRAMO_CASES:
        predicate = _m202_2025_predicate(predicate_id)
        casilla_values: dict[CasillaId, Decimal] = {antecedent: Decimal("50000.00"), consequent: Decimal("15000.00")}

        findings = evaluate_verification_predicates((predicate,), casilla_values, _workflow_profile())
        assert findings == [], predicate_id


def test_m202_2025_b2_tramo_advisory_holds_trivially_when_base_not_used() -> None:
    """No declared tramo base holds trivially (the filer does not use this B2 tramo)."""
    for predicate_id, antecedent, consequent in _M202_B2_TRAMO_CASES:
        predicate = _m202_2025_predicate(predicate_id)

        explicit_zero: dict[CasillaId, Decimal] = {antecedent: Decimal("0"), consequent: Decimal("0")}
        absent: dict[CasillaId, Decimal] = {}

        assert evaluate_verification_predicates((predicate,), explicit_zero, _workflow_profile()) == [], predicate_id
        assert evaluate_verification_predicates((predicate,), absent, _workflow_profile()) == [], predicate_id
