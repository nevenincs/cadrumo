"""Modelo 202 B1/B2 resultado-previo lane verification tests."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.resources._boundary import bundled_path
from ....domain.calculations.registry.loader import load_modelo_path
from ....domain.calculations.registry.schema_verification import VerificationPredicateDefinition
from ....domain.modelos.verification_report import ModeloVerificationFindingKind
from .._verification_actions import evaluate_verification_predicates
from ._verification_substance_support import _workflow_profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_M202_B1_B2_RESULTADO_PREVIO_XOR_PREDICATE_ID = "modelo-202-b1-b2-resultado-previo-at-most-one-positive"
_CASILLA_18: CasillaId = validated_casilla_id("18", surface="test M202 B1 resultado previo")
_CASILLA_26: CasillaId = validated_casilla_id("26", surface="test M202 B2 resultado previo")
_M202_XOR_REVISION_IDS = ("2019-2022", "2023-2024", "2025-y-siguientes")
_M202_SINGLE_LANE_CASES: tuple[tuple[str, dict[CasillaId, Decimal]], ...] = (
    ("b1-only", {_CASILLA_18: Decimal("1200"), _CASILLA_26: Decimal("0")}),
    ("b2-only", {_CASILLA_18: Decimal("0"), _CASILLA_26: Decimal("800")}),
    ("neither-lane-positive", {_CASILLA_18: Decimal("0"), _CASILLA_26: Decimal("0")}),
)


def _m202_xor_predicate(revision_id: str) -> VerificationPredicateDefinition:
    modelo = load_modelo_path(bundled_path("registry", "aeat", "modelos", "202"))
    revision = modelo.revisions[revision_id]
    predicate = next(
        p for p in revision.verification_predicates if p.predicate_id == _M202_B1_B2_RESULTADO_PREVIO_XOR_PREDICATE_ID
    )
    assert predicate.expression == 'at_most_one_positive(["18", "26"])'
    assert predicate.finding_kind == "BLOCKING_RULE"
    return predicate


def test_modelo_202_b1_b2_resultado_previo_both_positive_is_blocking() -> None:
    """The committed M202 predicate refuses the overstatement state: claves 18 and 26 both positive."""

    for revision_id in _M202_XOR_REVISION_IDS:
        predicate = _m202_xor_predicate(revision_id)
        findings = evaluate_verification_predicates(
            (predicate,),
            {_CASILLA_18: Decimal("1200"), _CASILLA_26: Decimal("800")},
            _workflow_profile(),
        )

        assert len(findings) == 1, revision_id
        assert findings[0].kind is ModeloVerificationFindingKind.BLOCKING_RULE, revision_id
        assert findings[0].message_locale_key == "application.modelo.findings.cross_casilla_invariant_violated", (
            revision_id
        )
        assert dict(findings[0].message_facts) == {"predicate_id": _M202_B1_B2_RESULTADO_PREVIO_XOR_PREDICATE_ID}, (
            revision_id
        )
        assert "ley-27-2014:art-40-3" in findings[0].legal_refs, revision_id


def test_modelo_202_b1_b2_resultado_previo_single_lane_passes() -> None:
    """B1-only and B2-only filings remain valid; the gate only targets both-positive overstatement."""

    predicate = _m202_xor_predicate("2025-y-siguientes")

    for case_label, casilla_values in _M202_SINGLE_LANE_CASES:
        assert evaluate_verification_predicates((predicate,), casilla_values, _workflow_profile()) == [], case_label
