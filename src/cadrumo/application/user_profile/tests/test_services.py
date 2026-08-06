"""Tests for user-profile validation and preflight services."""

from __future__ import annotations

import pytest

from ....core import Period
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

_NON_ISO_DATE_VALUES = (
    "1978-13-45",  # month 13, day 45 — impossible calendar date
    "15/03/1978",  # DD/MM/YYYY layout, not ISO 8601
    "1978-02-30",  # February never has 30 days
    "not-a-date",  # plainly not a date
    "1978-3-15",  # non-zero-padded ISO components
    "19780315",  # ISO-ish but missing separators
)


@pytest.fixture(scope="module")
def schema() -> ProfileSchemaDefinition:
    return resources().user_profile_schema.singleton


def test_validation_rejects_unknown_field_path(schema: ProfileSchemaDefinition) -> None:
    svc = ProfileValidationService(schema=schema)
    report = svc.validate_facts(
        "11111111-1111-4111-8111-111111111111", [UserProfileFact(path="identity.does_not_exist", value="x")]
    )
    codes = {issue.code for issue in report.issues}
    assert "unknown_field" in codes


def test_validation_reports_missing_required_fields(schema: ProfileSchemaDefinition) -> None:
    svc = ProfileValidationService(schema=schema)
    report = svc.validate_facts("11111111-1111-4111-8111-111111111111", [])
    required_misses = [
        issue
        for issue in report.issues
        if issue.code == "required_field_missing" and issue.severity is BaseSeverity.ERROR
    ]
    assert len(required_misses) >= 1


def test_validation_accepts_known_field(schema: ProfileSchemaDefinition) -> None:
    svc = ProfileValidationService(schema=schema)
    report = svc.validate_facts(
        "11111111-1111-4111-8111-111111111111", [UserProfileFact(path="identity.tax_id", value="12345678Z")]
    )
    assert not any(issue.code == "unknown_field" for issue in report.issues)


def test_validation_rejects_non_iso_date_value(schema: ProfileSchemaDefinition) -> None:
    svc = ProfileValidationService(schema=schema)
    failures: list[str] = []
    for garbage in _NON_ISO_DATE_VALUES:
        report = svc.validate_facts(
            "11111111-1111-4111-8111-111111111111",
            [UserProfileFact(path="renta_taxpayer.birth_date", value=garbage)],
        )
        date_errors = [
            issue
            for issue in report.issues
            if issue.code == "invalid_date_value" and issue.severity is BaseSeverity.ERROR
        ]
        if len(date_errors) != 1:
            failures.append(f"{garbage!r}: expected one invalid_date_value error, got {len(date_errors)}")
            continue
        if "YYYY-MM-DD" not in date_errors[0].message:
            failures.append(f"{garbage!r}: message did not mention YYYY-MM-DD")
        if date_errors[0].path != "renta_taxpayer.birth_date":
            failures.append(f"{garbage!r}: error path was {date_errors[0].path!r}")

    assert not failures, "\n".join(failures)


def test_validation_accepts_valid_iso_date_value(schema: ProfileSchemaDefinition) -> None:
    svc = ProfileValidationService(schema=schema)
    report = svc.validate_facts(
        "11111111-1111-4111-8111-111111111111",
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
        report = svc.validate_facts(
            "11111111-1111-4111-8111-111111111111", [UserProfileFact(path=path, value="2024-13-99")]
        )
        assert any(issue.code == "invalid_date_value" and issue.path == path for issue in report.issues), (
            f"date field {path!r} did not reject a garbage value"
        )


def test_validation_covers_every_enum_typed_field(schema: ProfileSchemaDefinition) -> None:
    """An undeclared token is refused on every field the schema types as an enum.

    Enumerated FROM the schema rather than listed here, mirroring the date
    sibling above, so a newly declared enum field enrols itself and cannot
    ship unenforced. The probe value is deliberately absurd: any real token
    risks being legitimately declared by some field and would then pass for
    the wrong reason.
    """

    enum_paths = [
        f"{section.key}.{field.key}"
        for section in schema.sections
        for field in section.fields
        if str(field.type) == "enum"
    ]
    assert enum_paths  # the schema declares at least one enum field
    svc = ProfileValidationService(schema=schema)
    for path in enum_paths:
        report = svc.validate_facts(
            "11111111-1111-4111-8111-111111111111",
            [UserProfileFact(path=path, value="__undeclared_probe_token__")],
        )
        assert any(issue.code == "invalid_enum_value" and issue.path == path for issue in report.issues), (
            f"enum field {path!r} accepted an undeclared value"
        )


def test_every_declared_enum_value_is_accepted(schema: ProfileSchemaDefinition) -> None:
    """Every value a field declares must pass its own constraint.

    The refusal test above would be satisfied by a check that rejected
    everything. This is the other half: each declared token is accepted by
    the field that declares it, so the constraint cannot pass by being
    uniformly hostile.
    """

    svc = ProfileValidationService(schema=schema)
    for section in schema.sections:
        for field in section.fields:
            if str(field.type) != "enum":
                continue
            path = f"{section.key}.{field.key}"
            for declared in field.enum_values:
                report = svc.validate_facts(
                    "11111111-1111-4111-8111-111111111111",
                    [UserProfileFact(path=path, value=declared)],
                )
                assert not any(issue.code == "invalid_enum_value" for issue in report.issues), (
                    f"enum field {path!r} refused its own declared value {declared!r}"
                )


def test_preflight_returns_ready_when_no_modelo_selectors_match(schema: ProfileSchemaDefinition) -> None:
    svc = ProfilePreflightService(schema=schema)
    record = UserProfileRecord(
        profile_id="11111111-1111-4111-8111-111111111111",
        display_name="Operator",
        facts=(UserProfileFact(path="identity.tax_id", value="12345678Z"),),
    )
    report = svc.report(
        record=record,
        modelo="100",
        revision_id="2024-y-siguientes",
        period=Period.from_year_and_code(2024, "0A"),
    )
    assert report.ready is True
    assert report.missing == ()


def test_preflight_accepts_legal_entity_legal_name_for_export_headers(schema: ProfileSchemaDefinition) -> None:
    period = Period.from_year_and_code(2026, "1P")
    snapshot = resources().modelos.authority.snapshot("202", filing_year=2026, period=period.registry_token)
    record = UserProfileRecord(
        profile_id="11111111-1111-4111-8111-111111111111",
        display_name="Rocio Ferrer Administracion Sociedad Limitada",
        facts=(
            UserProfileFact(path="identity.tax_id", value="B12345674"),
            UserProfileFact(path="identity.legal_name", value="Rocio Ferrer Administracion Sociedad Limitada"),
            UserProfileFact(path="taxpayer_type.entity_type", value="legal_entity"),
            UserProfileFact(path="taxpayer_type.legal_entity_form", value="sl"),
        ),
    )

    report = ProfilePreflightService(schema=schema).report(
        record=record,
        modelo="202",
        revision_id=snapshot.revision.id,
        period=period,
        revision=snapshot.revision,
    )

    assert report.ready is True
    assert report.missing == ()


def test_preflight_rejects_legal_entity_export_identity_fragments(
    schema: ProfileSchemaDefinition,
) -> None:
    period = Period.from_year_and_code(2026, "1P")
    snapshot = resources().modelos.authority.snapshot("202", filing_year=2026, period=period.registry_token)
    failures: list[str] = []
    for case_id, identity_fact in (
        ("surnames-only", UserProfileFact(path="identity.surnames", value="Ferrer")),
        ("short-name-only", UserProfileFact(path="identity.name", value="Rocio")),
    ):
        record = UserProfileRecord(
            profile_id="11111111-1111-4111-8111-111111111111",
            display_name="Incomplete legal entity",
            facts=(
                UserProfileFact(path="identity.tax_id", value="B12345674"),
                identity_fact,
                UserProfileFact(path="taxpayer_type.entity_type", value="legal_entity"),
                UserProfileFact(path="taxpayer_type.legal_entity_form", value="sl"),
            ),
        )

        report = ProfilePreflightService(schema=schema).report(
            record=record,
            modelo="202",
            revision_id=snapshot.revision.id,
            period=period,
            revision=snapshot.revision,
        )
        if report.ready is not False:
            failures.append(f"{case_id}: report was unexpectedly ready")
        if not any(item.section_key == "identity" and item.field_key == "legal_name" for item in report.missing):
            failures.append(f"{case_id}: legal_name was not reported missing")

    assert not failures, "\n".join(failures)


def test_preflight_carries_request_fields_through(schema: ProfileSchemaDefinition) -> None:
    svc = ProfileValidationService(schema=schema)  # warm domain
    pre = ProfilePreflightService(schema=schema)
    record = UserProfileRecord(profile_id="11111111-1111-4111-8111-111111111111", display_name="Operator", facts=())
    report = pre.report(
        record=record,
        modelo="303",
        revision_id="rev-2024",
        period=Period.from_year_and_code(2024, "1T"),
    )
    assert report.profile_id == "11111111-1111-4111-8111-111111111111"
    assert report.modelo == "303"
    assert report.revision_id == "rev-2024"
    assert report.filing_year == 2024
    assert report.period == Period.from_year_and_code(2024, "1T")
    del svc
