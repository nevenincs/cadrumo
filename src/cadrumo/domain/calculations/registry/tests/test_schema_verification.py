"""Registry verification-expression parser tests."""

from __future__ import annotations

import pytest

from ..schema_verification import (
    KNOWN_VERIFICATION_PREDICATE_OPERATORS,
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
