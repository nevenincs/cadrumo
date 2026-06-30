"""IRNR profile completeness gates shared by validation, health, and preflight."""

from __future__ import annotations

import pytest

from ....core import Period
from ....core.resources import resources
from ....domain.user_profile import UserProfileFact, UserProfileRecord
from ... import wizard as _wizard  # noqa: F401 - registers compiled profile keys
from .. import ProfilePreflightService, ProfileValidationService
from .._keys_validation import validate_profile_values

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


_BASE_VALUES: dict[str, str] = {
    "identity.tax_id": "X1234567L",
    "iva.regime": "GENERAL",
}


def test_profile_key_validation_blocks_irnr_without_country() -> None:
    result = validate_profile_values(
        {
            **_BASE_VALUES,
            "taxpayer_type.fiscal_residency": "non_resident_irnr",
        },
    )

    assert result.valid is False
    assert "taxpayer_type.country_of_fiscal_residence" in result.missing_required


def test_profile_key_validation_blocks_gb_irnr_without_representante() -> None:
    result = validate_profile_values(
        {
            **_BASE_VALUES,
            "taxpayer_type.fiscal_residency": "non_resident_irnr",
            "taxpayer_type.country_of_fiscal_residence": "GB",
        },
    )

    assert result.valid is False
    assert "taxpayer_type.representante_fiscal_nif" in result.missing_required
    assert "taxpayer_type.representante_fiscal_nombre" in result.missing_required


def test_profile_key_validation_accepts_eu_irnr_without_representante() -> None:
    result = validate_profile_values(
        {
            **_BASE_VALUES,
            "taxpayer_type.fiscal_residency": "non_resident_irnr",
            "taxpayer_type.country_of_fiscal_residence": "FR",
        },
    )

    assert result.valid is True


def test_lifecycle_validation_reports_conditional_irnr_profile_errors() -> None:
    schema = resources().user_profile_schema.singleton
    facts = (
        UserProfileFact(path="identity.tax_id", value="B66012345"),
        UserProfileFact(path="iva.regime", value="GENERAL"),
        UserProfileFact(path="taxpayer_type.entity_type", value="legal_entity"),
        UserProfileFact(path="taxpayer_type.fiscal_residency", value="non_resident_irnr"),
        UserProfileFact(path="taxpayer_type.country_of_fiscal_residence", value="GB"),
    )

    report = ProfileValidationService(schema=schema).validate_facts("77777777-7777-4777-8777-777777777777", facts)

    error_paths = {issue.path for issue in report.issues if issue.severity.value == "error"}
    assert "taxpayer_type.representante_fiscal_nif" in error_paths
    assert "taxpayer_type.representante_fiscal_nombre" in error_paths


def test_profile_preflight_reports_irnr_country_as_missing_before_modelo_work() -> None:
    schema = resources().user_profile_schema.singleton
    record = UserProfileRecord(
        profile_id="88888888-8888-4888-8888-888888888888",
        display_name="IRNR no country",
        facts=(
            UserProfileFact(path="identity.tax_id", value="X1234567L"),
            UserProfileFact(path="iva.regime", value="GENERAL"),
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
