"""Modelo 202 B1/B2 resultado-previo lane verification tests."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core import (
    CasillaId,
    validated_casilla_id,
)
from ....core.resources import bundled_path
from ....domain.calculations.registry import VerificationPredicateDefinition, load_modelo_path
from ....domain.modelos import ModeloVerificationFindingKind
from .._verification_actions import evaluate_verification_predicates
from ._verification_substance_support import _workflow_profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_M202_B1_B2_RESULTADO_PREVIO_XOR_PREDICATE_ID = "modelo-202-b1-b2-resultado-previo-at-most-one-positive"
_CASILLA_18: CasillaId = validated_casilla_id("18", surface="test M202 B1 resultado previo")
_CASILLA_26: CasillaId = validated_casilla_id("26", surface="test M202 B2 resultado previo")


def _m202_xor_predicate(revision_id: str) -> VerificationPredicateDefinition:
    modelo = load_modelo_path(bundled_path("registry", "aeat", "modelos", "202"))
    revision = modelo.revisions[revision_id]
    predicate = next(
        p for p in revision.verification_predicates if p.predicate_id == _M202_B1_B2_RESULTADO_PREVIO_XOR_PREDICATE_ID
    )
    assert predicate.expression == 'at_most_one_positive(["18", "26"])'
    assert predicate.finding_kind == "BLOCKING_RULE"
    return predicate


@pytest.mark.parametrize("revision_id", ["2019-2022", "2023-2024", "2025-y-siguientes"])
def test_modelo_202_b1_b2_resultado_previo_both_positive_is_blocking(revision_id: str) -> None:
    """The committed M202 predicate refuses the overstatement state: claves 18 and 26 both positive."""

    predicate = _m202_xor_predicate(revision_id)
    findings = evaluate_verification_predicates(
        (predicate,),
        {_CASILLA_18: Decimal("1200"), _CASILLA_26: Decimal("800")},
        _workflow_profile(),
    )

    assert len(findings) == 1
    assert findings[0].kind is ModeloVerificationFindingKind.BLOCKING_RULE
    assert _M202_B1_B2_RESULTADO_PREVIO_XOR_PREDICATE_ID in findings[0].message
    assert "ley-27-2014:art-40-3" in findings[0].legal_refs


@pytest.mark.parametrize(
    "casilla_values",
    (
        {_CASILLA_18: Decimal("1200"), _CASILLA_26: Decimal("0")},
        {_CASILLA_18: Decimal("0"), _CASILLA_26: Decimal("800")},
        {_CASILLA_18: Decimal("0"), _CASILLA_26: Decimal("0")},
    ),
    ids=("b1-only", "b2-only", "neither-lane-positive"),
)
def test_modelo_202_b1_b2_resultado_previo_single_lane_passes(
    casilla_values: dict[CasillaId, Decimal],
) -> None:
    """B1-only and B2-only filings remain valid; the gate only targets both-positive overstatement."""

    predicate = _m202_xor_predicate("2025-y-siguientes")

    assert evaluate_verification_predicates((predicate,), casilla_values, _workflow_profile()) == []
