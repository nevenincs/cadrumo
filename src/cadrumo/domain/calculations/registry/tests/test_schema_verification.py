"""Registry verification-expression parser tests."""

from __future__ import annotations

import dataclasses

import pytest

from .. import schema_verification
from ..schema_verification import (
    KNOWN_VERIFICATION_PREDICATE_OPERATORS,
    ParsedVerificationPredicate,
    VerificationPredicateOperator,
    _parse_verification_predicate_expression_memo,
    parse_verification_predicate_expression,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_domain_predicate_parser_recognises_every_known_predicate_operator() -> None:
    """Parse every operator declared by the canonical registry set.

    The explicit probes guard the registry schema grammar. Runtime evaluation
    has its own application-level contract tests.
    """
    probe_expressions: dict[str, str] = {
        "all_nonzero": 'all_nonzero(["01", "02"])',
        "any_nonzero": 'any_nonzero(["01", "02"])',
        "at_most_one_positive": 'at_most_one_positive(["01", "02"])',
        "cap_le_when_positive": 'cap_le_when_positive(["11", "10"])',
        "positive_application_le_present_stock": ('positive_application_le_present_stock(["DP200014:00547", "00670"])'),
        "advisory_when_positive": 'advisory_when_positive(["0527"])',
        "advisory_when_ratio_ge": 'advisory_when_ratio_ge(["01", "02", "0.5"])',
        "equals": 'equals(["27", "iva.cuota-devengada-total"])',
        "equals_sum": 'equals_sum(["27", "03", "06", "09"])',
        "implies_nonzero": 'implies_nonzero(["01", "07"])',
        "implies_any_nonzero": 'implies_any_nonzero(["iva.cuota-devengada-total", "03", "06", "09"])',
        "profile_field_required": ('profile_field_required("representante_fiscal_nif", "non_resident_irnr_non_eea")'),
        "profile_flag_enabled": 'profile_flag_enabled("art109_activity_income_withholding_ge_70pct")',
        "roll_forward_balances": 'roll_forward_balances(["00671", "00670", "DP200014:00547", "DP200014:00552"])',
        "casilla_equals_implies_zero": 'casilla_equals_implies_zero(["01", "  ", "07"])',
        "casilla_equals_implies_nonzero": (
            'casilla_equals_implies_nonzero(["tipo_renta", "inmobiliaria", "base_imponible"])'
        ),
        "casilla_equals_implies_profile_flag": (
            'casilla_equals_implies_profile_flag(["tipo_renta", "ue_residente", "ue_eee_status"])'
        ),
        "casilla_equals_implies_diverges": (
            'casilla_equals_implies_diverges(["modulos-epigrafe", "721.2", '
            '"modulos-rendimiento-neto-minorado", "modulos-rendimiento-neto-modulos"])'
        ),
        "deduccion_requires_adquisicion_before": (
            'deduccion_requires_adquisicion_before(["0547", "0708", "0690", "2013-01-01"])'
        ),
        "advisory_when_computed_diverges": (
            'advisory_when_computed_diverges(["01", "modulos-rendimiento-neto-actividad"])'
        ),
    }
    missing_probes = KNOWN_VERIFICATION_PREDICATE_OPERATORS.difference(probe_expressions)
    assert not missing_probes, (
        f"Probe map is missing entries for known operators {sorted(missing_probes)!r}; "
        "add a syntax probe when adding a new operator to the canonical set"
    )

    for operator_name in sorted(KNOWN_VERIFICATION_PREDICATE_OPERATORS):
        probe = probe_expressions[operator_name]
        parsed = parse_verification_predicate_expression(probe)
        assert parsed is not None, f"schema parser did not recognise {operator_name!r}: {probe!r}"
        assert parsed.operator.value == operator_name


def test_repeated_parse_reuses_the_memoised_value_without_reparsing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A second parse of the same text is served without running the grammar again."""
    expression = 'equals_sum(["27", "03", "06", "09"])'
    _parse_verification_predicate_expression_memo.cache_clear()
    grammar_calls: list[str] = []
    real_operator_name = schema_verification.verification_predicate_operator_name

    def counting_operator_name(text: str) -> str | None:
        grammar_calls.append(text)
        return real_operator_name(text)

    monkeypatch.setattr(schema_verification, "verification_predicate_operator_name", counting_operator_name)

    first = parse_verification_predicate_expression(expression)
    second = parse_verification_predicate_expression(expression)

    assert grammar_calls == [expression]
    assert first is second
    assert first == ParsedVerificationPredicate(
        operator=VerificationPredicateOperator.EQUALS_SUM,
        arguments=("27", "03", "06", "09"),
        casilla_ids=("27", "03", "06", "09"),
    )


def test_memoised_parse_value_cannot_be_mutated() -> None:
    """The shared memo value is frozen, so no caller can alter another caller's parse."""
    parsed = parse_verification_predicate_expression('implies_nonzero(["01", "07"])')
    assert parsed is not None
    assert isinstance(parsed.arguments, tuple)
    assert isinstance(parsed.casilla_ids, tuple)
    for field in dataclasses.fields(parsed):
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(parsed, field.name, "x")


@pytest.mark.parametrize(
    "malformed",
    [
        "",
        "not_a_predicate",
        'unknown_operator(["01", "02"])',
        'all_nonzero("01", "02")',
        'advisory_when_ratio_ge(["01", "02"])',
        'profile_field_required("only_field")',
    ],
)
def test_malformed_expression_refuses_on_every_parse(malformed: str) -> None:
    """Memoisation keeps the unknown-or-malformed refusal on every call."""
    _parse_verification_predicate_expression_memo.cache_clear()
    assert parse_verification_predicate_expression(malformed) is None
    assert parse_verification_predicate_expression(malformed) is None
    assert parse_verification_predicate_expression(malformed) is None


def test_distinct_expression_text_is_parsed_independently() -> None:
    """Whitespace-distinct and near-identical texts never borrow another text's parse."""
    _parse_verification_predicate_expression_memo.cache_clear()
    valid = parse_verification_predicate_expression('all_nonzero(["01", "02"])')
    padded = parse_verification_predicate_expression('  all_nonzero(["01", "02"])  ')
    broken = parse_verification_predicate_expression('all_nonzero(["01", "02"]')

    assert valid is not None
    assert padded == valid
    assert broken is None
