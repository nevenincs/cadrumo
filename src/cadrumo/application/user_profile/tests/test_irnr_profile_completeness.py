"""IRNR profile completeness gates shared by validation, health, and preflight."""

from __future__ import annotations

import pytest

from ....core import Period
from ....core.resources import resources
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ...wizard import compiler as _wizard  # noqa: F401 - registers compiled profile keys
from ..completeness import conditional_profile_missing_required
from ..keys_validation import validate_profile_values
from ..preflight import ProfilePreflightService
from ..validation import ProfileValidationService

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


_BASE_VALUES: dict[str, str] = {
    "identity.tax_id": "X1234567L",
    "tax_residence.jurisdiction_scope": "common_regime",
    "iva.regime": "GENERAL",
    "iva.m303_regime_composition": "general",
    "iva.redeme_enrolled": "false",
    "iva.cash_accounting_regime_enrolled": "false",
    "iva.voluntary_sii_enrolled": "false",
    "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
}


def test_clave_movil_route_is_conditionally_required_without_affecting_other_providers() -> None:
    missing_route = conditional_profile_missing_required({"auth.provider": "clave_movil"})
    configured_qr = conditional_profile_missing_required(
        {"auth.provider": "clave_movil", "auth.clave_movil_route": "qr"},
    )
    certificate = conditional_profile_missing_required({"auth.provider": "certificate"})

    assert missing_route == ("auth.clave_movil_route",)
    assert configured_qr == ()
    assert certificate == ()


def test_profile_key_validation_applies_irnr_conditional_requirements() -> None:
    cases = (
        (
            "missing-country",
            {"taxpayer_type.fiscal_residency": "non_resident_irnr"},
            False,
            ("taxpayer_type.country_of_fiscal_residence",),
        ),
        (
            "gb-missing-representante",
            {
                "taxpayer_type.fiscal_residency": "non_resident_irnr",
                "taxpayer_type.country_of_fiscal_residence": "GB",
            },
            False,
            ("taxpayer_type.representante_fiscal_nif", "taxpayer_type.representante_fiscal_nombre"),
        ),
        (
            "eu-country",
            {
                "taxpayer_type.fiscal_residency": "non_resident_irnr",
                "taxpayer_type.country_of_fiscal_residence": "FR",
            },
            True,
            (),
        ),
    )

    for case_id, overrides, expected_valid, expected_missing in cases:
        result = validate_profile_values({**_BASE_VALUES, **overrides})

        assert result.valid is expected_valid, case_id
        for missing_path in expected_missing:
            assert missing_path in result.missing_required, case_id


def test_lifecycle_validation_reports_conditional_irnr_profile_errors() -> None:
    schema = resources().user_profile_schema.singleton
    facts = (
        UserProfileFact(path="identity.tax_id", value="B66012345"),
        UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
        UserProfileFact(path="iva.regime", value="GENERAL"),
        UserProfileFact(path="iva.m303_regime_composition", value="general"),
        UserProfileFact(path="iva.redeme_enrolled", value=False),
        UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
        UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
        UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
        UserProfileFact(path="taxpayer_type.entity_type", value="legal_entity"),
        UserProfileFact(path="taxpayer_type.fiscal_residency", value="non_resident_irnr"),
        UserProfileFact(path="taxpayer_type.country_of_fiscal_residence", value="GB"),
    )

    report = ProfileValidationService(schema=schema).validate_facts("77777777-7777-4777-8777-777777777777", facts)

    error_paths = {issue.path for issue in report.issues if issue.severity.value == "error"}
    assert "taxpayer_type.representante_fiscal_nif" in error_paths
    assert "taxpayer_type.representante_fiscal_nombre" in error_paths


def test_profile_key_validation_does_not_require_iva_regime_for_natural_person_without_activity() -> None:
    result = validate_profile_values(
        {
            "identity.tax_id": "12345678Z",
            "tax_residence.jurisdiction_scope": "common_regime",
            "taxpayer_type.entity_type": "natural_person",
            "taxpayer_type.irpf_income_categories": "capital_inmobiliario",
        }
    )

    assert result.valid is True
    assert "iva.regime" not in result.missing_required


def test_lifecycle_validation_allows_natural_person_without_activity_to_omit_iva_regime() -> None:
    schema = resources().user_profile_schema.singleton
    facts = (
        UserProfileFact(path="identity.tax_id", value="12345678Z"),
        UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
        UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
        UserProfileFact(path="taxpayer_type.irpf_income_categories", value="capital_inmobiliario"),
    )

    report = ProfileValidationService(schema=schema).validate_facts("77777777-7777-4777-8777-777777777777", facts)

    error_paths = {issue.path for issue in report.issues if issue.severity.value == "error"}
    assert "iva.regime" not in error_paths


def test_lifecycle_validation_requires_natural_person_with_activity_to_declare_iva_regime() -> None:
    schema = resources().user_profile_schema.singleton
    facts = (
        UserProfileFact(path="identity.tax_id", value="12345678Z"),
        UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
        UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
        UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
    )

    report = ProfileValidationService(schema=schema).validate_facts("77777777-7777-4777-8777-777777777777", facts)

    error_paths = {issue.path for issue in report.issues if issue.severity.value == "error"}
    assert "iva.regime" in error_paths


def test_profile_preflight_reports_irnr_country_as_missing_before_modelo_work() -> None:
    schema = resources().user_profile_schema.singleton
    record = UserProfileRecord(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id="88888888-8888-4888-8888-888888888888",
        facts=(
            UserProfileFact(path="identity.tax_id", value="X1234567L"),
            UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
            UserProfileFact(path="iva.regime", value="GENERAL"),
            UserProfileFact(path="iva.m303_regime_composition", value="general"),
            UserProfileFact(path="iva.redeme_enrolled", value=False),
            UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
            UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
            UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
            UserProfileFact(path="taxpayer_type.fiscal_residency", value="non_resident_irnr"),
        ),
    )

    report = ProfilePreflightService(schema=schema).report(
        record=record,
        modelo="210",
        revision_id="2025",
        period=Period.from_year_and_code(2026, "1T"),
    )

    missing_paths = {f"{item.section_key}.{item.field_key}" for item in report.missing}
    assert report.ready is False
    assert "taxpayer_type.country_of_fiscal_residence" in missing_paths
