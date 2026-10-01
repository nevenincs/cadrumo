"""The ``equals_sum`` printed-total predicate operator and the finding it raises.

A total box defined by an official record design as the sum of other printed
boxes must equal that sum exactly. These cases pin the operator's arithmetic
and the refusal it projects; the registry declarations that use it are tested
against the compiled Modelo 303 registry under ``dev/registry/tests``.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from cadrumo.application.modelo.tests.verification_substance_fixtures import workflow_profile

from ....core.casilla_id import CasillaId, validated_casilla_id
from ....domain.calculations.registry.schema_verification import VerificationPredicateDefinition
from ....domain.modelos.verification_report import (
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from ..verification_predicates import (
    evaluate_advisory_predicate_fires,
    evaluate_predicate_expression,
    evaluate_verification_predicates,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]

_TOTAL: CasillaId = validated_casilla_id("27")
_FIRST: CasillaId = validated_casilla_id("03")
_SECOND: CasillaId = validated_casilla_id("09")
_THIRD: CasillaId = validated_casilla_id("15")
_EXPRESSION = 'equals_sum(["27", "03", "09", "15"])'
_LEGAL_REFS = ("ley-37-1992:art-88",)


def _predicate(*, finding_kind: str = "BLOCKING_RULE") -> VerificationPredicateDefinition:
    return VerificationPredicateDefinition(
        id="equals-sum:printed-total",
        predicate_id="modelo-303-printed-total",
        legal_refs=_LEGAL_REFS,
        expression=_EXPRESSION,
        finding_kind=finding_kind,
    )


def _values(total: str, first: str, second: str, third: str) -> dict[CasillaId, Decimal]:
    return {_TOTAL: Decimal(total), _FIRST: Decimal(first), _SECOND: Decimal(second), _THIRD: Decimal(third)}


def test_holds_only_when_the_total_is_the_exact_sum_of_its_addends() -> None:
    profile = workflow_profile()

    assert evaluate_predicate_expression(_EXPRESSION, _values("31.00", "1.00", "20.00", "10.00"), profile) is True
    assert evaluate_predicate_expression(_EXPRESSION, _values("31.01", "1.00", "20.00", "10.00"), profile) is False
    assert evaluate_predicate_expression(_EXPRESSION, _values("30.99", "1.00", "20.00", "10.00"), profile) is False


def test_a_missing_addend_reads_as_zero_and_a_missing_total_does_too() -> None:
    profile = workflow_profile()

    assert evaluate_predicate_expression(_EXPRESSION, {_TOTAL: Decimal("20.00"), _SECOND: Decimal("20.00")}, profile)
    assert not evaluate_predicate_expression(_EXPRESSION, {_SECOND: Decimal("20.00")}, profile)
    assert not evaluate_predicate_expression(_EXPRESSION, {_TOTAL: Decimal("20.00")}, profile)
    assert evaluate_predicate_expression(_EXPRESSION, {}, profile)


def test_a_negative_addend_is_summed_with_its_sign() -> None:
    """Modification boxes such as [15] may be negative and still add into the total."""
    assert evaluate_predicate_expression(_EXPRESSION, _values("15.00", "0", "20.00", "-5.00"), workflow_profile())


def test_the_advisory_reading_fires_exactly_when_the_blocking_reading_fails() -> None:
    profile = workflow_profile()
    for values in (
        _values("31.00", "1.00", "20.00", "10.00"),
        _values("231.00", "1.00", "20.00", "10.00"),
        {_TOTAL: Decimal("5.00")},
    ):
        assert evaluate_advisory_predicate_fires(_EXPRESSION, values) is not evaluate_predicate_expression(
            _EXPRESSION, values, profile
        )


def test_fewer_than_two_addends_neither_blocks_nor_fires() -> None:
    """Registry validation refuses this arity; the runtime only defends against a bypass."""
    malformed = 'equals_sum(["27", "09"])'
    values = {_TOTAL: Decimal("5.00"), _SECOND: Decimal("1.00")}

    assert evaluate_predicate_expression(malformed, values, workflow_profile()) is True
    assert evaluate_advisory_predicate_fires(malformed, values) is False


def test_a_violation_raises_a_blocking_printed_total_finding_naming_the_box_and_the_printed_sum() -> None:
    findings = evaluate_verification_predicates(
        (_predicate(),),
        _values("231.00", "1.00", "20.00", "10.00"),
        workflow_profile(),
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.kind is ModeloVerificationFindingKind.BLOCKING_RULE
    assert finding.severity is ModeloVerificationFindingSeverity.BLOCKING
    assert finding.casilla_id == _TOTAL
    assert finding.message_locale_key == "application.modelo.findings.printed_total_mismatch"
    assert dict(finding.message_facts) == {
        "box": "27",
        "predicate_id": "modelo-303-printed-total",
        "printed_sum": Decimal("31.00"),
    }
    assert finding.legal_refs == _LEGAL_REFS


def test_a_consistent_total_raises_no_finding() -> None:
    consistent = _values("31.00", "1.00", "20.00", "10.00")

    assert evaluate_verification_predicates((_predicate(),), consistent, workflow_profile()) == []


def test_an_advisory_declaration_warns_through_the_generic_advisory_message() -> None:
    findings = evaluate_verification_predicates(
        (_predicate(finding_kind="ADVISORY"),),
        _values("231.00", "1.00", "20.00", "10.00"),
        workflow_profile(),
    )

    assert [(finding.kind, finding.severity, finding.message_locale_key) for finding in findings] == [
        (
            ModeloVerificationFindingKind.ADVISORY,
            ModeloVerificationFindingSeverity.WARNING,
            "application.modelo.findings.registry_advisory_predicate_fired",
        ),
    ]
