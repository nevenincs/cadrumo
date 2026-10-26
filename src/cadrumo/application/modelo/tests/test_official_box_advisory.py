"""The calculate-path official-box collector admits ADVISORY predicates as the verify gate does."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.casilla_id import CasillaId, validated_casilla_id
from ....domain.calculations.registry.schema import ModeloRevision
from ....domain.calculations.registry.schema_verification import (
    VerificationPredicateDefinition,
    VerificationPredicateOperator,
)
from ....domain.calculations.registry.tests.published_authority import published_authored_revision
from .._official_box_advisory import collect_official_box_unpopulated_diagnostics
from ..action_errors import ModeloVerificationPredicateMalformedError
from ..verification_predicates import VerificationPredicateRefusal, VerificationPredicateRoute

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]

_TOTAL: CasillaId = validated_casilla_id("iva.cuota-devengada-total")
_BOX_03: CasillaId = validated_casilla_id("03")
_BOX_09: CasillaId = validated_casilla_id("09")


def _revision_with(expression: str, *, finding_kind: str = "ADVISORY") -> ModeloRevision:
    predicate = VerificationPredicateDefinition(
        id="implies-any-nonzero:official-box-probe",
        predicate_id="modelo-303-official-box-probe",
        legal_refs=("ley-37-1992:art-88",),
        expression=expression,
        finding_kind=finding_kind,
    )
    return published_authored_revision("303", year=2025).model_copy(update={"verification_predicates": (predicate,)})


def test_a_well_formed_official_box_advisory_still_reports_the_unpopulated_boxes() -> None:
    revision = _revision_with('implies_any_nonzero(["iva.cuota-devengada-total", "03", "09"])')
    values = {_TOTAL: Decimal("210.00"), _BOX_03: Decimal("0"), _BOX_09: Decimal("0")}

    diagnostics = collect_official_box_unpopulated_diagnostics(revision, values)

    assert [(diagnostic.reason, diagnostic.casilla_id) for diagnostic in diagnostics] == [
        ("official_box_unpopulated", _TOTAL)
    ]
    assert collect_official_box_unpopulated_diagnostics(revision, {**values, _BOX_09: Decimal("210.00")}) == ()


@pytest.mark.parametrize(
    ("expression", "operator", "refusal"),
    (
        pytest.param(
            'implies_any_nonzero("iva.cuota-devengada-total")',
            VerificationPredicateOperator.IMPLIES_ANY_NONZERO,
            VerificationPredicateRefusal.UNPARSEABLE,
        ),
        pytest.param(
            'implies_any_nonzero(["iva.cuota-devengada-total"])',
            VerificationPredicateOperator.IMPLIES_ANY_NONZERO,
            VerificationPredicateRefusal.ARITY,
        ),
        pytest.param(
            'all_nonzero(["03", "09"])',
            VerificationPredicateOperator.ALL_NONZERO,
            VerificationPredicateRefusal.OPERATOR_FAMILY,
        ),
        pytest.param('mystery_operator(["03", "09"])', None, VerificationPredicateRefusal.UNPARSEABLE),
    ),
)
def test_a_malformed_advisory_predicate_is_refused_rather_than_skipped(
    expression: str,
    operator: VerificationPredicateOperator | None,
    refusal: VerificationPredicateRefusal,
) -> None:
    revision = _revision_with(expression)
    values = {_TOTAL: Decimal("210.00")}

    for _ in range(3):
        with pytest.raises(ModeloVerificationPredicateMalformedError) as raised:
            collect_official_box_unpopulated_diagnostics(revision, values)
        assert raised.value.context == {
            "predicate_expression_recognised": False,
            "predicate_operator": None if operator is None else operator.value,
            "predicate_refusal": refusal.value,
            "predicate_route": VerificationPredicateRoute.ADVISORY.value,
        }


def test_blocking_predicates_stay_on_the_verify_route() -> None:
    """The collector reads ADVISORY predicates only; a blocking one is the verify gate's to judge."""
    revision = _revision_with('advisory_when_positive(["03"])', finding_kind="BLOCKING_RULE")

    assert collect_official_box_unpopulated_diagnostics(revision, {_BOX_03: Decimal("1")}) == ()
