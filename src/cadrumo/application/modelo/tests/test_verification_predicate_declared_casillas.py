"""A blocking predicate may only name casillas the selected revision declares.

Missing values read as zero, so a mistyped antecedent or ceiling would make a
cross-casilla rule hold on every filing. The dispatcher receives the revision's
hydrated casilla set and refuses such a predicate before evaluating anything.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from cadrumo.application.modelo.tests.verification_substance_fixtures import workflow_profile

from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.errors.error_codes import ErrorCategory, get_registered_error_code
from ....domain.calculations.registry.schema_verification import (
    VerificationPredicateDefinition,
    VerificationPredicateOperator,
)
from ....domain.calculations.registry.tests.published_authority import published_revision
from ..action_errors import ModeloVerificationPredicateMalformedError
from ..verification_predicates import VerificationPredicateRefusal, evaluate_verification_predicates

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]

_DECLARED: frozenset[CasillaId] = frozenset(validated_casilla_id(raw) for raw in ("01", "02"))
_INGRESOS = validated_casilla_id("01")
_CUOTA = validated_casilla_id("02")


def _blocking(expression: str) -> VerificationPredicateDefinition:
    return VerificationPredicateDefinition(
        id="declared-casillas:probe",
        predicate_id="declared-casillas-probe",
        legal_refs=("ley-37-1992:art-88",),
        expression=expression,
        finding_kind="BLOCKING_RULE",
    )


@pytest.mark.parametrize(
    ("expression", "operator"),
    [
        ('implies_nonzero(["03", "02"])', VerificationPredicateOperator.IMPLIES_NONZERO),
        ('implies_nonzero(["01", "03"])', VerificationPredicateOperator.IMPLIES_NONZERO),
        ('cap_le_when_positive(["01", "03"])', VerificationPredicateOperator.CAP_LE_WHEN_POSITIVE),
        ('cap_le_when_positive(["03", "02"])', VerificationPredicateOperator.CAP_LE_WHEN_POSITIVE),
    ],
)
def test_a_blocking_predicate_naming_an_undeclared_casilla_is_refused(
    expression: str, operator: VerificationPredicateOperator
) -> None:
    values = {_INGRESOS: Decimal("100")}
    with pytest.raises(ModeloVerificationPredicateMalformedError) as raised:
        evaluate_verification_predicates(
            (_blocking(expression),), values, workflow_profile(), declared_casilla_ids=_DECLARED
        )
    assert get_registered_error_code(raised.value).category is ErrorCategory.REFUSED
    assert raised.value.context == {
        "predicate_expression_recognised": False,
        "predicate_operator": operator.value,
        "predicate_refusal": VerificationPredicateRefusal.UNDECLARED_CASILLA.value,
        "predicate_route": "blocking",
    }


def test_the_same_typo_is_read_as_holding_when_no_declared_set_is_supplied() -> None:
    # Documents why the dispatcher check matters: the evaluator alone has no casilla set.
    findings = evaluate_verification_predicates(
        (_blocking('implies_nonzero(["03", "02"])'),), {_INGRESOS: Decimal("100")}, workflow_profile()
    )
    assert findings == []


def test_a_declared_casilla_without_a_value_still_evaluates_as_zero() -> None:
    values = {_INGRESOS: Decimal("100")}
    findings = evaluate_verification_predicates(
        (_blocking('implies_nonzero(["01", "02"])'),), values, workflow_profile(), declared_casilla_ids=_DECLARED
    )
    assert len(findings) == 1
    assert findings[0].casilla_id is None
    capped = evaluate_verification_predicates(
        (_blocking('cap_le_when_positive(["02", "01"])'),), values, workflow_profile(), declared_casilla_ids=_DECLARED
    )
    assert capped == []
    uncapped = evaluate_verification_predicates(
        (_blocking('cap_le_when_positive(["01", "02"])'),), values, workflow_profile(), declared_casilla_ids=_DECLARED
    )
    assert len(uncapped) == 1


def test_an_advisory_predicate_is_not_checked_against_the_declared_set() -> None:
    advisory = VerificationPredicateDefinition(
        id="declared-casillas:advisory",
        predicate_id="declared-casillas-advisory",
        legal_refs=("ley-37-1992:art-88",),
        expression='implies_nonzero(["01", "03"])',
        finding_kind="ADVISORY",
    )
    evaluate_verification_predicates((advisory,), {}, workflow_profile(), declared_casilla_ids=_DECLARED)


@pytest.mark.parametrize(("modelo", "revision_id"), [("100", "2025"), ("200", "2024"), ("303", "2026-hasta-01-y-1t")])
def test_every_shipped_blocking_predicate_of_a_baseline_revision_names_a_hydrated_casilla(
    modelo: str, revision_id: str
) -> None:
    revision = published_revision(modelo, revision_id)
    assert revision.casilla_storage_baseline is not None
    declared = frozenset(casilla.id for casilla in revision.casillas)
    blocking = tuple(p for p in revision.verification_predicates if p.finding_kind != "ADVISORY")
    assert blocking
    evaluate_verification_predicates(blocking, {}, workflow_profile(), declared_casilla_ids=declared)
    with pytest.raises(ModeloVerificationPredicateMalformedError):
        evaluate_verification_predicates(blocking, {}, workflow_profile(), declared_casilla_ids=frozenset())
