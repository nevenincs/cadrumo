"""A malformed registry verification predicate ends verification as a registered refusal.

Each refusal kind is driven through the real evaluators on every route that
can reach it, and must surface as the one registered ``REFUSED`` error with
the same machine context on every call, so the operation supervisor settles it
as a refusal rather than a failure. Operator-family and arity cases are
derived from the routes' operator sets and the operators' specifications; only
the unparseable and unreadable-literal inputs are authored per route.
"""

from __future__ import annotations

import itertools
import json
from collections.abc import Iterator
from dataclasses import dataclass
from decimal import Decimal

import pytest

from cadrumo.application.modelo.tests.verification_substance_fixtures import workflow_profile

from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.errors.error_codes import ErrorCategory, get_registered_error_code, resolve_error_message
from ....core.external_constants import OutputLanguage
from ....domain.calculations.registry.schema_verification import (
    VERIFICATION_PREDICATE_SPECIFICATIONS,
    VerificationPredicateOperator,
    VerificationPredicateSyntax,
)
from ....domain.modelos.errors import ModeloError
from ..action_errors import ModeloVerificationPredicateMalformedError
from ..verification_predicates import (
    ADVISORY_PREDICATE_OPERATORS,
    BLOCKING_PREDICATE_OPERATORS,
    VerificationPredicateRefusal,
    VerificationPredicateRoute,
    evaluate_advisory_predicate_fires,
    evaluate_predicate_expression,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]

_CODE = "REFUSED_MODELO_VERIFICATION_PREDICATE_MALFORMED"
_MESSAGE_KEY = "errors.refused.refused_modelo_verification_predicate_malformed"
_CASILLA_01: CasillaId = validated_casilla_id("01")
_CASILLA_02: CasillaId = validated_casilla_id("02")
_VALUES: dict[CasillaId, Decimal] = {_CASILLA_01: Decimal("1000"), _CASILLA_02: Decimal("10")}

#: The remedy each catalogue sentence names, in the operator-addressed form of its language.
_LOCALE_REMEDY_WORD: dict[OutputLanguage, str] = {
    OutputLanguage.EN: "correct",
    OutputLanguage.ES: "corrige",
    OutputLanguage.CA: "corregeix",
    OutputLanguage.HU: "javítsd",
}

_ROUTE_OPERATORS: dict[VerificationPredicateRoute, frozenset[VerificationPredicateOperator]] = {
    VerificationPredicateRoute.BLOCKING: BLOCKING_PREDICATE_OPERATORS,
    VerificationPredicateRoute.ADVISORY: ADVISORY_PREDICATE_OPERATORS,
}

#: The authored malformed inputs that no operator specification can derive.
_AUTHORED_INPUTS: dict[
    tuple[VerificationPredicateRefusal, VerificationPredicateRoute], tuple[str, VerificationPredicateOperator | None]
] = {
    (VerificationPredicateRefusal.UNPARSEABLE, VerificationPredicateRoute.BLOCKING): ('mystery_operator(["01"])', None),
    (VerificationPredicateRefusal.UNPARSEABLE, VerificationPredicateRoute.ADVISORY): ('mystery_operator(["01"])', None),
    (VerificationPredicateRefusal.LITERAL, VerificationPredicateRoute.BLOCKING): (
        'casilla_equals_implies_zero(["01", "", "07"])',
        VerificationPredicateOperator.CASILLA_EQUALS_IMPLIES_ZERO,
    ),
    (VerificationPredicateRefusal.LITERAL, VerificationPredicateRoute.ADVISORY): (
        'advisory_when_ratio_ge(["01", "02", "notadecimal"])',
        VerificationPredicateOperator.ADVISORY_WHEN_RATIO_GE,
    ),
}


@dataclass(frozen=True, slots=True)
class _RefusalCase:
    expression: str
    route: VerificationPredicateRoute
    operator: VerificationPredicateOperator | None
    refusal: VerificationPredicateRefusal

    @property
    def id(self) -> str:
        return f"{self.route.value}-{self.refusal.value}-{self.expression}"


def _casilla_list_expression(operator: VerificationPredicateOperator, count: int) -> str:
    return f"{operator.value}({json.dumps([f'{index:02d}' for index in range(1, count + 1)])})"


def _casilla_list_operators() -> Iterator[VerificationPredicateOperator]:
    for operator in VerificationPredicateOperator:
        if VERIFICATION_PREDICATE_SPECIFICATIONS[operator].syntax is VerificationPredicateSyntax.CASILLA_LIST:
            yield operator


def _derived_cases() -> Iterator[_RefusalCase]:
    for route, route_operators in _ROUTE_OPERATORS.items():
        for operator in _casilla_list_operators():
            specification = VERIFICATION_PREDICATE_SPECIFICATIONS[operator]
            if operator not in route_operators:
                yield _RefusalCase(
                    _casilla_list_expression(operator, max(1, specification.minimum_casilla_ids)),
                    route,
                    operator,
                    VerificationPredicateRefusal.OPERATOR_FAMILY,
                )
                continue
            if specification.minimum_casilla_ids >= 2:
                yield _RefusalCase(
                    _casilla_list_expression(operator, specification.minimum_casilla_ids - 1),
                    route,
                    operator,
                    VerificationPredicateRefusal.ARITY,
                )
            if specification.maximum_casilla_ids is not None:
                yield _RefusalCase(
                    _casilla_list_expression(operator, specification.maximum_casilla_ids + 1),
                    route,
                    operator,
                    VerificationPredicateRefusal.ARITY,
                )
    for (refusal, route), (expression, operator) in _AUTHORED_INPUTS.items():
        yield _RefusalCase(expression, route, operator, refusal)


_CASES: tuple[_RefusalCase, ...] = tuple(_derived_cases())


def _evaluate(case: _RefusalCase) -> object:
    if case.route is VerificationPredicateRoute.BLOCKING:
        return evaluate_predicate_expression(case.expression, _VALUES, workflow_profile())
    return evaluate_advisory_predicate_fires(case.expression, _VALUES, {}, workflow_profile())


def test_every_refusal_kind_has_a_case_on_every_route() -> None:
    covered = {(case.refusal, case.route) for case in _CASES}
    assert covered == set(itertools.product(VerificationPredicateRefusal, VerificationPredicateRoute))


@pytest.mark.parametrize("case", _CASES, ids=lambda case: case.id)
def test_each_refusal_raises_the_registered_refusal_on_every_call(case: _RefusalCase) -> None:
    for _ in range(3):
        with pytest.raises(ModeloVerificationPredicateMalformedError) as raised:
            _evaluate(case)
        registered = get_registered_error_code(raised.value)
        assert registered.code == _CODE
        assert registered.category is ErrorCategory.REFUSED
        assert registered.retryable is False
        assert raised.value.translated_message == _MESSAGE_KEY
        assert raised.value.context == {
            "predicate_expression_recognised": False,
            "predicate_operator": None if case.operator is None else case.operator.value,
            "predicate_refusal": case.refusal.value,
            "predicate_route": case.route.value,
        }


def test_a_non_canonical_casilla_token_keeps_its_unregistered_modelo_error() -> None:
    with pytest.raises(ModeloError) as raised:
        evaluate_predicate_expression('all_nonzero(["01", "bad key"])', _VALUES, workflow_profile())
    assert not isinstance(raised.value, ModeloVerificationPredicateMalformedError)
    assert raised.value.context == {"casilla_id_token": "bad key", "casilla_id_canonical": False}


def test_well_formed_predicates_still_evaluate_on_both_routes() -> None:
    profile = workflow_profile()
    assert evaluate_predicate_expression('all_nonzero(["01", "02"])', _VALUES, profile) is True
    assert evaluate_predicate_expression('equals_sum(["01", "02", "02"])', _VALUES, profile) is False
    assert evaluate_advisory_predicate_fires('advisory_when_ratio_ge(["02", "01", "0.50"])', _VALUES) is False
    assert evaluate_advisory_predicate_fires('advisory_when_ratio_ge(["01", "02", "0.50"])', _VALUES) is True


def test_the_refusal_renders_its_own_catalogue_sentence_in_every_supported_locale() -> None:
    with pytest.raises(ModeloVerificationPredicateMalformedError) as raised:
        evaluate_advisory_predicate_fires('mystery_operator(["01"])', _VALUES)
    assert set(_LOCALE_REMEDY_WORD) == set(OutputLanguage)
    rendered = {locale: resolve_error_message(raised.value, locale=locale.value) for locale in OutputLanguage}
    assert all(sentence and sentence != _MESSAGE_KEY for sentence in rendered.values())
    assert len(set(rendered.values())) == len(rendered)
    for locale, remedy_word in _LOCALE_REMEDY_WORD.items():
        assert remedy_word in rendered[locale], locale
