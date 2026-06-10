"""Tests for user-profile validation and preflight services."""

from __future__ import annotations

import pytest

from ....core.errors import BaseSeverity
from ....core.resources import resources
from ....domain.user_profile import (
    ProfileSchemaDefinition,
    UserProfileFact,
    UserProfileRecord,
)
from .. import (
    ProfilePreflightService,
    ProfileValidationService,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.fixture(scope="module")
def schema() -> ProfileSchemaDefinition:
    return resources().user_profile_schema.singleton


def test_validation_rejects_unknown_field_path(schema: ProfileSchemaDefinition) -> None:
    svc = ProfileValidationService(schema=schema)
    report = svc.validate_facts("operator", [UserProfileFact(path="identity.does_not_exist", value="x")])
    codes = {issue.code for issue in report.issues}
    assert "unknown_field" in codes


def test_validation_reports_missing_required_fields(schema: ProfileSchemaDefinition) -> None:
    svc = ProfileValidationService(schema=schema)
    report = svc.validate_facts("operator", [])
    required_misses = [
        issue
        for issue in report.issues
        if issue.code == "required_field_missing" and issue.severity is BaseSeverity.ERROR
    ]
    assert len(required_misses) >= 1


def test_validation_accepts_known_field(schema: ProfileSchemaDefinition) -> None:
    svc = ProfileValidationService(schema=schema)
    report = svc.validate_facts("operator", [UserProfileFact(path="identity.tax_id", value="12345678Z")])
    assert not any(issue.code == "unknown_field" for issue in report.issues)


@pytest.mark.parametrize(
    "garbage",
    [
        "1978-13-45",  # month 13, day 45 — impossible calendar date
        "15/03/1978",  # DD/MM/YYYY layout, not ISO 8601
        "1978-02-30",  # February never has 30 days
        "not-a-date",  # plainly not a date
        "1978-3-15",  # non-zero-padded ISO components
        "19780315",  # ISO-ish but missing separators
    ],
)
def test_validation_rejects_non_iso_date_value(schema: ProfileSchemaDefinition, garbage: str) -> None:
    svc = ProfileValidationService(schema=schema)
    report = svc.validate_facts(
        "operator",
        [UserProfileFact(path="renta_taxpayer.birth_date", value=garbage)],
    )
    date_errors = [
        issue for issue in report.issues if issue.code == "invalid_date_value" and issue.severity is BaseSeverity.ERROR
    ]
    assert len(date_errors) == 1
    assert "YYYY-MM-DD" in date_errors[0].message
    assert date_errors[0].path == "renta_taxpayer.birth_date"


def test_validation_accepts_valid_iso_date_value(schema: ProfileSchemaDefinition) -> None:
    svc = ProfileValidationService(schema=schema)
    report = svc.validate_facts(
        "operator",
        [UserProfileFact(path="renta_taxpayer.birth_date", value="1978-03-15")],
    )
    assert not any(issue.code == "invalid_date_value" for issue in report.issues)


def test_validation_covers_every_date_typed_field(schema: ProfileSchemaDefinition) -> None:
    """A garbage value is refused on every field the schema types as a date."""

    date_paths = [
        f"{section.key}.{field.key}"
        for section in schema.sections
        for field in section.fields
        if str(field.type) == "date"
    ]
    assert date_paths  # the schema declares at least one date field
    svc = ProfileValidationService(schema=schema)
    for path in date_paths:
        report = svc.validate_facts("operator", [UserProfileFact(path=path, value="2024-13-99")])
        assert any(issue.code == "invalid_date_value" and issue.path == path for issue in report.issues), (
            f"date field {path!r} did not reject a garbage value"
        )


def test_preflight_returns_ready_when_no_modelo_selectors_match(schema: ProfileSchemaDefinition) -> None:
    svc = ProfilePreflightService(schema=schema)
    record = UserProfileRecord(
        profile_id="operator",
        display_name="Operator",
        facts=(UserProfileFact(path="identity.tax_id", value="12345678Z"),),
    )
    report = svc.report(
        record=record,
        modelo="100",
        revision_id="2024-y-siguientes",
        filing_year=2024,
        period="0A",
    )
    assert report.ready is True
    assert report.missing == ()


def test_preflight_carries_request_fields_through(schema: ProfileSchemaDefinition) -> None:
    svc = ProfileValidationService(schema=schema)  # warm domain
    pre = ProfilePreflightService(schema=schema)
    record = UserProfileRecord(profile_id="operator", display_name="Operator", facts=())
    report = pre.report(
        record=record,
        modelo="303",
        revision_id="rev-2024",
        filing_year=2024,
        period="1T",
    )
    assert report.profile_id == "operator"
    assert report.modelo == "303"
    assert report.revision_id == "rev-2024"
    assert report.filing_year == 2024
    assert report.period == "1T"
    del svc
