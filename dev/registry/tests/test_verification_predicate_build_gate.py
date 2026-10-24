"""The registry build refuses verification predicates the runtime would silently ignore.

An expression the runtime cannot parse holds trivially, and an operator authored
under a finding kind its evaluator does not serve never reports. The build-time
gate is the only place either is visible, so each refusal must name the modelo,
revision, predicate and expression it rejects.
"""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.schema_verification import (
    KNOWN_VERIFICATION_PREDICATE_OPERATORS,
    VERIFICATION_PREDICATE_SPECIFICATIONS,
    VerificationFindingKind,
    VerificationPredicateDefinition,
    VerificationPredicateOperator,
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


def _kind_for(operator: VerificationPredicateOperator) -> str:
    return (
        VerificationFindingKind.ADVISORY.value
        if operator in _ADVISORY_ONLY_OPERATORS
        else VerificationFindingKind.BLOCKING_RULE.value
    )


def _gate_message(expression: str, finding_kind: str) -> str:
    modelo, catalogues = _committed_modelo("130")
    revision = next(iter(modelo.revisions.values()))
    predicate = VerificationPredicateDefinition(
        id="build-gate:probe",
        predicate_id=_PREDICATE_ID,
        legal_refs=("rd-439-2007:art-110",),
        expression=expression,
        finding_kind=finding_kind,
    )
    mutated = revision.model_copy(
        update={"verification_predicates": (*revision.verification_predicates, predicate)},
    )
    try:
        committed_registry_validator(catalogues).validate_modelo(_with_revision(modelo, mutated))
    except RegistryValidationError as error:
        return str(error)
    return ""


def _gate_failures(expression: str, finding_kind: str) -> list[str]:
    return [line for line in _gate_message(expression, finding_kind).splitlines() if _PREDICATE_ID in line]


def _assert_locator(failures: list[str], expression: str) -> None:
    modelo, _ = _committed_modelo("130")
    revision = next(iter(modelo.revisions.values()))
    assert failures, f"expected the build gate to refuse {expression!r}"
    for failure in failures:
        assert f"modelo 130 revision {revision.id}" in failure
        assert f"verification predicate {_PREDICATE_ID}" in failure
        assert repr(expression) in failure


def test_every_known_operator_is_classified_and_has_an_authoring_route() -> None:
    operators = set(VerificationPredicateOperator)
    assert {operator.value for operator in operators} == KNOWN_VERIFICATION_PREDICATE_OPERATORS
    assert set(VERIFICATION_PREDICATE_SPECIFICATIONS) == operators
    assert not _ADVISORY_ONLY_OPERATORS & _BLOCKING_ONLY_OPERATORS
    assert operators >= _ADVISORY_ONLY_OPERATORS | _BLOCKING_ONLY_OPERATORS
    routed = set(_MIXED_TOKEN_PREDICATE_VALIDATORS) | set(_PROFILE_PREDICATE_VALIDATORS) | _CASILLA_LIST_OPERATORS
    assert routed == KNOWN_VERIFICATION_PREDICATE_OPERATORS


@pytest.mark.parametrize("operator", sorted(VerificationPredicateOperator, key=lambda member: member.value))
def test_unparseable_syntax_under_each_known_operator_is_refused_with_locator(
    operator: VerificationPredicateOperator,
) -> None:
    expression = f"{operator.value}(not a valid argument list)"

    _assert_locator(_gate_failures(expression, _kind_for(operator)), expression)


def test_unknown_operator_is_refused_with_locator() -> None:
    expression = 'cap_lt_when_positive(["15", "14"])'

    failures = _gate_failures(expression, "BLOCKING_RULE")

    _assert_locator(failures, expression)
    assert any("unknown operator 'cap_lt_when_positive'" in failure for failure in failures)


def test_expression_without_call_shape_is_refused_with_locator() -> None:
    expression = "just a string with no call shape"

    _assert_locator(_gate_failures(expression, "BLOCKING_RULE"), expression)


@pytest.mark.parametrize(
    ("expression", "kind"),
    (
        ('all_nonzero(["01", "missing-casilla"])', "BLOCKING_RULE"),
        ('equals_sum(["01", "02", "missing-casilla"])', "BLOCKING_RULE"),
        ('advisory_when_ratio_ge(["01", "missing-casilla", "0.5"])', "ADVISORY"),
        ('advisory_when_ratio_ge(["missing-casilla", "01", "0.5"])', "ADVISORY"),
        ('casilla_equals_implies_nonzero(["missing-casilla", "general", "07"])', "BLOCKING_RULE"),
        ('casilla_equals_implies_zero(["01", "general", "missing-casilla"])', "BLOCKING_RULE"),
        ('casilla_equals_implies_profile_flag(["missing-casilla", "general", "ue_eee_status"])', "ADVISORY"),
        ('casilla_equals_implies_diverges(["missing-casilla", "general", "01", "02"])', "ADVISORY"),
        ('casilla_equals_implies_diverges(["01", "general", "missing-casilla", "02"])', "ADVISORY"),
        ('casilla_equals_implies_diverges(["01", "general", "02", "missing-casilla"])', "ADVISORY"),
        ('deduccion_requires_adquisicion_before(["missing-casilla", "01", "07", "2013-01-01"])', "ADVISORY"),
        ('deduccion_requires_adquisicion_before(["01", "missing-casilla", "07", "2013-01-01"])', "ADVISORY"),
        ('deduccion_requires_adquisicion_before(["01", "07", "missing-casilla", "2013-01-01"])', "ADVISORY"),
    ),
)
def test_unknown_casilla_token_is_refused_with_locator(expression: str, kind: str) -> None:
    failures = _gate_failures(expression, kind)

    _assert_locator(failures, expression)
    assert any("unknown" in failure and "'missing-casilla'" in failure for failure in failures)


@pytest.mark.parametrize(
    "operator",
    sorted(_ADVISORY_ONLY_OPERATORS, key=lambda member: member.value),
)
def test_advisory_only_operator_authored_as_blocking_is_refused(operator: VerificationPredicateOperator) -> None:
    expression = {
        VerificationPredicateOperator.ADVISORY_WHEN_COMPUTED_DIVERGES: 'advisory_when_computed_diverges(["01", "02"])',
        VerificationPredicateOperator.ADVISORY_WHEN_POSITIVE: 'advisory_when_positive(["01"])',
        VerificationPredicateOperator.ADVISORY_WHEN_RATIO_GE: 'advisory_when_ratio_ge(["01", "02", "0.5"])',
        VerificationPredicateOperator.CASILLA_EQUALS_IMPLIES_DIVERGES: (
            'casilla_equals_implies_diverges(["01", "general", "02", "06"])'
        ),
        VerificationPredicateOperator.CASILLA_EQUALS_IMPLIES_PROFILE_FLAG: (
            'casilla_equals_implies_profile_flag(["01", "general", "ue_eee_status"])'
        ),
        VerificationPredicateOperator.DEDUCCION_REQUIRES_ADQUISICION_BEFORE: (
            'deduccion_requires_adquisicion_before(["01", "02", "06", "2013-01-01"])'
        ),
        VerificationPredicateOperator.PROFILE_FLAG_ENABLED: 'profile_flag_enabled("ue_eee_status")',
    }[operator]

    failures = _gate_failures(expression, "BLOCKING_RULE")

    _assert_locator(failures, expression)
    assert any(f"{operator.value} is advisory-only" in failure for failure in failures)


@pytest.mark.parametrize(
    ("expression", "operator"),
    (
        ('all_nonzero(["01", "02"])', VerificationPredicateOperator.ALL_NONZERO),
        ('any_nonzero(["01", "02"])', VerificationPredicateOperator.ANY_NONZERO),
        ('cap_le_when_positive(["15", "14"])', VerificationPredicateOperator.CAP_LE_WHEN_POSITIVE),
        (
            'positive_application_le_present_stock(["01", "02"])',
            VerificationPredicateOperator.POSITIVE_APPLICATION_LE_PRESENT_STOCK,
        ),
        ('profile_field_required("ue_eee_status", "applies")', VerificationPredicateOperator.PROFILE_FIELD_REQUIRED),
    ),
)
def test_blocking_only_operator_authored_as_advisory_is_refused(
    expression: str,
    operator: VerificationPredicateOperator,
) -> None:
    failures = _gate_failures(expression, "ADVISORY")

    _assert_locator(failures, expression)
    assert any(f"{operator.value} is blocking-only" in failure for failure in failures)


@pytest.mark.parametrize(
    ("expression", "kind"),
    (
        ('all_nonzero(["01", "02"])', "BLOCKING_RULE"),
        ('equals(["01", "02"])', "ADVISORY"),
        ('equals(["01", "02"])', "BLOCKING_RULE"),
        ('advisory_when_ratio_ge(["01", "02", "0.5"])', "ADVISORY"),
        ('profile_flag_enabled("ue_eee_status")', "ADVISORY"),
    ),
)
def test_well_formed_predicate_for_its_kind_passes(expression: str, kind: str) -> None:
    assert _gate_message(expression, kind) == ""
