"""The registry build refuses verification predicates the runtime would silently ignore.

An expression the runtime cannot parse holds trivially, and an operator authored
under a finding kind its evaluator does not serve never reports. The build-time
gate is the only place either is visible, so each refusal must name the modelo,
revision, predicate and expression it rejects.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

import pytest

from cadrumo.application.modelo.verification_predicates import (
    ADVISORY_PREDICATE_OPERATORS,
    BLOCKING_PREDICATE_OPERATORS,
)
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.schema_base import CasillaDataType
from cadrumo.domain.calculations.registry.schema_verification import (
    KNOWN_VERIFICATION_PREDICATE_OPERATORS,
    VERIFICATION_PREDICATE_SPECIFICATIONS,
    VerificationFindingKind,
    VerificationPredicateDefinition,
    VerificationPredicateOperator,
    parse_verification_predicate_expression,
)

from ..compiler._validate_verification_predicates import (
    _ADVISORY_ONLY_OPERATORS,
    _BLOCKING_ONLY_OPERATORS,
    _CASILLA_LIST_OPERATORS,
)
from ..compiler.validate_registry_surfaces import (
    _MIXED_TOKEN_PREDICATE_VALIDATORS,
    _PROFILE_PREDICATE_VALIDATORS,
)
from ..conformance.registry_schema_support import committed_modelo as _committed_modelo
from ..conformance.registry_schema_support import with_revision as _with_revision
from .profile_schema_support import committed_registry_validator

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("governed_fact_scope")]

_PREDICATE_ID = "modelo-130-build-gate-probe"
_MISSING_CASILLA = "missing-casilla"
_TEXT_CASILLA = "08"
_ACQUISITION_DATE_CASILLA = "10"
_CONSTRUCTION_DATE_CASILLA = "16"
_PROBE_CASILLA_TYPES: Mapping[str, CasillaDataType] = MappingProxyType(
    {
        _TEXT_CASILLA: CasillaDataType.TEXT,
        _ACQUISITION_DATE_CASILLA: CasillaDataType.DATE,
        _CONSTRUCTION_DATE_CASILLA: CasillaDataType.DATE,
    },
)

_PROBE_EXPRESSIONS: Mapping[VerificationPredicateOperator, str] = MappingProxyType(
    {
        VerificationPredicateOperator.ADVISORY_WHEN_COMPUTED_DIVERGES: 'advisory_when_computed_diverges(["01", "02"])',
        VerificationPredicateOperator.ADVISORY_WHEN_POSITIVE: 'advisory_when_positive(["01"])',
        VerificationPredicateOperator.ADVISORY_WHEN_RATIO_GE: 'advisory_when_ratio_ge(["01", "02", "0.5"])',
        VerificationPredicateOperator.ALL_NONZERO: 'all_nonzero(["01", "02"])',
        VerificationPredicateOperator.ANY_NONZERO: 'any_nonzero(["01", "02"])',
        VerificationPredicateOperator.AT_MOST_ONE_POSITIVE: 'at_most_one_positive(["01", "02"])',
        VerificationPredicateOperator.CAP_LE_WHEN_POSITIVE: 'cap_le_when_positive(["15", "14"])',
        VerificationPredicateOperator.CASILLA_EQUALS_IMPLIES_DIVERGES: (
            f'casilla_equals_implies_diverges(["{_TEXT_CASILLA}", "general", "02", "06"])'
        ),
        VerificationPredicateOperator.CASILLA_EQUALS_IMPLIES_NONZERO: (
            f'casilla_equals_implies_nonzero(["{_TEXT_CASILLA}", "general", "07"])'
        ),
        VerificationPredicateOperator.CASILLA_EQUALS_IMPLIES_PROFILE_FLAG: (
            f'casilla_equals_implies_profile_flag(["{_TEXT_CASILLA}", "general", "ue_eee_status"])'
        ),
        VerificationPredicateOperator.CASILLA_EQUALS_IMPLIES_ZERO: (
            f'casilla_equals_implies_zero(["{_TEXT_CASILLA}", "general", "07"])'
        ),
        VerificationPredicateOperator.DEDUCCION_REQUIRES_ADQUISICION_BEFORE: (
            f'deduccion_requires_adquisicion_before(["01", "{_ACQUISITION_DATE_CASILLA}", '
            f'"{_CONSTRUCTION_DATE_CASILLA}", "2013-01-01"])'
        ),
        VerificationPredicateOperator.EQUALS: 'equals(["01", "02"])',
        VerificationPredicateOperator.EQUALS_SUM: 'equals_sum(["01", "02", "06"])',
        VerificationPredicateOperator.IMPLIES_ANY_NONZERO: 'implies_any_nonzero(["01", "02"])',
        VerificationPredicateOperator.IMPLIES_NONZERO: 'implies_nonzero(["01", "02"])',
        VerificationPredicateOperator.POSITIVE_APPLICATION_LE_PRESENT_STOCK: (
            'positive_application_le_present_stock(["01", "02"])'
        ),
        VerificationPredicateOperator.PROFILE_FIELD_REQUIRED: 'profile_field_required("ue_eee_status", "applies")',
        VerificationPredicateOperator.PROFILE_FLAG_ENABLED: 'profile_flag_enabled("ue_eee_status")',
        VerificationPredicateOperator.ROLL_FORWARD_BALANCES: 'roll_forward_balances(["01", "02", "06", "07"])',
    },
)


def _served_kinds(operator: VerificationPredicateOperator) -> tuple[VerificationFindingKind, ...]:
    return tuple(
        kind
        for kind, family in (
            (VerificationFindingKind.BLOCKING_RULE, BLOCKING_PREDICATE_OPERATORS),
            (VerificationFindingKind.ADVISORY, ADVISORY_PREDICATE_OPERATORS),
        )
        if operator in family
    )


def _unknown_casilla_cases() -> list[object]:
    cases: list[object] = []
    for operator, expression in _PROBE_EXPRESSIONS.items():
        parsed = parse_verification_predicate_expression(expression)
        assert parsed is not None
        for position, casilla_id in enumerate(parsed.casilla_ids):
            quoted = f'"{casilla_id}"'
            assert expression.count(quoted) == 1
            cases.append(
                pytest.param(
                    operator,
                    expression.replace(quoted, f'"{_MISSING_CASILLA}"'),
                    id=f"{operator.value}-{position}",
                ),
            )
    return cases


def _gate_message(expression: str, finding_kind: VerificationFindingKind) -> str:
    modelo, catalogues = _committed_modelo("130")
    revision = next(iter(modelo.revisions.values()))
    predicate = VerificationPredicateDefinition(
        id="build-gate:probe",
        predicate_id=_PREDICATE_ID,
        legal_refs=("rd-439-2007:art-110",),
        expression=expression,
        finding_kind=finding_kind,
    )
    casillas = tuple(
        casilla.model_copy(update={"data_type": _PROBE_CASILLA_TYPES[casilla.id]})
        if casilla.id in _PROBE_CASILLA_TYPES
        else casilla
        for casilla in revision.casillas
    )
    mutated = revision.model_copy(
        update={
            "casillas": casillas,
            "verification_predicates": (*revision.verification_predicates, predicate),
        },
    )
    try:
        committed_registry_validator(catalogues).validate_modelo(_with_revision(modelo, mutated))
    except RegistryValidationError as error:
        return str(error)
    return ""


def _gate_failures(expression: str, finding_kind: VerificationFindingKind) -> list[str]:
    return [line for line in _gate_message(expression, finding_kind).splitlines() if _PREDICATE_ID in line]


def _assert_locator(failures: list[str], expression: str) -> None:
    modelo, _ = _committed_modelo("130")
    revision = next(iter(modelo.revisions.values()))
    assert failures, f"expected the build gate to refuse {expression!r}"
    for failure in failures:
        assert f"modelo 130 revision {revision.id}" in failure
        assert f"verification predicate {_PREDICATE_ID}" in failure
        assert repr(expression) in failure


def test_probe_table_covers_every_known_operator() -> None:
    assert set(_PROBE_EXPRESSIONS) == set(VerificationPredicateOperator)
    for operator, expression in _PROBE_EXPRESSIONS.items():
        parsed = parse_verification_predicate_expression(expression)
        assert parsed is not None
        assert parsed.operator is operator


def test_every_known_operator_is_classified_and_has_an_authoring_route() -> None:
    operators = set(VerificationPredicateOperator)
    assert {operator.value for operator in operators} == KNOWN_VERIFICATION_PREDICATE_OPERATORS
    assert set(VERIFICATION_PREDICATE_SPECIFICATIONS) == operators
    assert not _ADVISORY_ONLY_OPERATORS & _BLOCKING_ONLY_OPERATORS
    assert _ADVISORY_ONLY_OPERATORS == ADVISORY_PREDICATE_OPERATORS - BLOCKING_PREDICATE_OPERATORS
    assert _BLOCKING_ONLY_OPERATORS == BLOCKING_PREDICATE_OPERATORS - ADVISORY_PREDICATE_OPERATORS
    assert operators == ADVISORY_PREDICATE_OPERATORS | BLOCKING_PREDICATE_OPERATORS
    routed = set(_MIXED_TOKEN_PREDICATE_VALIDATORS) | set(_PROFILE_PREDICATE_VALIDATORS) | _CASILLA_LIST_OPERATORS
    assert routed == KNOWN_VERIFICATION_PREDICATE_OPERATORS


@pytest.mark.parametrize("operator", sorted(VerificationPredicateOperator, key=lambda member: member.value))
def test_unparseable_syntax_under_each_known_operator_is_refused_with_locator(
    operator: VerificationPredicateOperator,
) -> None:
    expression = f"{operator.value}(not a valid argument list)"

    _assert_locator(_gate_failures(expression, _served_kinds(operator)[0]), expression)


def test_unknown_operator_is_refused_with_locator() -> None:
    expression = 'cap_lt_when_positive(["15", "14"])'

    failures = _gate_failures(expression, VerificationFindingKind.BLOCKING_RULE)

    _assert_locator(failures, expression)
    assert any("unknown operator 'cap_lt_when_positive'" in failure for failure in failures)


def test_expression_without_call_shape_is_refused_with_locator() -> None:
    expression = "just a string with no call shape"

    _assert_locator(_gate_failures(expression, VerificationFindingKind.BLOCKING_RULE), expression)


@pytest.mark.parametrize(("operator", "expression"), _unknown_casilla_cases())
def test_unknown_casilla_token_is_refused_with_locator(
    operator: VerificationPredicateOperator,
    expression: str,
) -> None:
    failures = _gate_failures(expression, _served_kinds(operator)[0])

    _assert_locator(failures, expression)
    assert any("unknown" in failure and f"'{_MISSING_CASILLA}'" in failure for failure in failures)


@pytest.mark.parametrize(
    "operator",
    sorted(_ADVISORY_ONLY_OPERATORS, key=lambda member: member.value),
)
def test_advisory_only_operator_authored_as_blocking_is_refused(operator: VerificationPredicateOperator) -> None:
    expression = _PROBE_EXPRESSIONS[operator]

    failures = _gate_failures(expression, VerificationFindingKind.BLOCKING_RULE)

    _assert_locator(failures, expression)
    assert any(f"{operator.value} is advisory-only" in failure for failure in failures)


@pytest.mark.parametrize(
    "operator",
    sorted(_BLOCKING_ONLY_OPERATORS, key=lambda member: member.value),
)
def test_blocking_only_operator_authored_as_advisory_is_refused(operator: VerificationPredicateOperator) -> None:
    expression = _PROBE_EXPRESSIONS[operator]

    failures = _gate_failures(expression, VerificationFindingKind.ADVISORY)

    _assert_locator(failures, expression)
    assert any(f"{operator.value} is blocking-only" in failure for failure in failures)


@pytest.mark.parametrize(
    ("operator", "kind"),
    [
        pytest.param(operator, kind, id=f"{operator.value}-{kind.value}")
        for operator in sorted(VerificationPredicateOperator, key=lambda member: member.value)
        for kind in _served_kinds(operator)
    ],
)
def test_well_formed_predicate_for_its_kind_passes(
    operator: VerificationPredicateOperator,
    kind: VerificationFindingKind,
) -> None:
    message = _gate_message(_PROBE_EXPRESSIONS[operator], kind)
    assert message == "", message
