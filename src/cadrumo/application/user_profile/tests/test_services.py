"""Tests for user-profile validation and preflight services."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from cadrumo.application.user_profile.commands import ProfilePreflightRequirement
from cadrumo.application.user_profile.preflight import ProfilePreflightService, build_profile_preflight_requirement
from cadrumo.application.user_profile.validation import ProfileValidationService

from ....core import Modelo, Period
from ....core.errors import BaseSeverity
from ....core.resources import resources
from ....domain.calculations.registry import ProfileKeyGrounding
from ....domain.user_profile import (
    ProfileSchemaDefinition,
    ProfileSetupState,
    UserProfileFact,
    UserProfileRecord,
    profile_field_label,
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


def test_preflight_ready_with_no_modelo_selectors_matched_is_not_assessed(schema: ProfileSchemaDefinition) -> None:
    """``ready=True`` here reflects zero schema-required fields examined, not a complete profile.

    No shipped schema field declares a ``modelo_200`` selector - the shipped
    schema populates ``modelo_036``, ``modelo_100`` and ``modelo_303`` tokens
    only, because those are the only modelos with a live ``source =
    "profile"`` registry binding today. For modelo 200,
    ``ProfilePreflightService.report()``'s schema-required walk still never
    runs, so ``ready`` reflects only the (here, trivially-passing)
    export-identity and conditional checks. The unassessed case must be
    distinguishable from a passing one - this test asserts both halves
    together so a future reader cannot read `ready is True` alone as a clean
    bill of health.
    """
    svc = ProfilePreflightService(schema=schema)
    record = UserProfileRecord(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id="11111111-1111-4111-8111-111111111111",
        facts=(UserProfileFact(path="identity.tax_id", value="12345678Z"),),
    )
    report = svc.report(
        record=record,
        modelo="200",
        revision_id="2024-y-siguientes",
        period=Period.from_year_and_code(2024, "0A"),
    )
    assert report.ready is True
    assert report.missing == ()
    assert report.per_operation_requirements_assessed is False


def test_preflight_modelo_100_per_operation_axis_now_contributes(schema: ProfileSchemaDefinition) -> None:
    """``identity.tax_id`` is grounded for modelo 100 - the axis is not universally empty.

    ``identity.tax_id`` is ``required=true`` and carries
    ``model_selectors = ("tax.id", "modelo_100")``, grounded by a live
    modelo 100 ``source = "profile"`` registry binding. A profile missing
    ``tax_id`` must surface it as a real, assessed requirement; a profile
    carrying it must report ``ready`` with the axis still marked assessed.
    """
    svc = ProfilePreflightService(schema=schema)
    period = Period.from_year_and_code(2024, "0A")

    empty_record = UserProfileRecord(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id="11111111-1111-4111-8111-111111111111",
        facts=(),
    )
    missing_report = svc.report(
        record=empty_record,
        modelo="100",
        revision_id="2024-y-siguientes",
        period=period,
    )
    assert missing_report.per_operation_requirements_assessed is True
    assert any(item.section_key == "identity" and item.field_key == "tax_id" for item in missing_report.missing)

    complete_record = UserProfileRecord(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id="11111111-1111-4111-8111-111111111111",
        facts=(UserProfileFact(path="identity.tax_id", value="12345678Z"),),
    )
    ready_report = svc.report(
        record=complete_record,
        modelo="100",
        revision_id="2024-y-siguientes",
        period=period,
    )
    assert ready_report.per_operation_requirements_assessed is True
    assert not any(item.section_key == "identity" and item.field_key == "tax_id" for item in ready_report.missing)


def test_preflight_modelo_111_requires_an_explicit_colegio_concertado_declaration(
    schema: ProfileSchemaDefinition,
) -> None:
    """Both boolean declarations are complete; absence remains a refusal."""
    service = ProfilePreflightService(schema=schema)
    period = Period.from_year_and_code(2026, "1T")

    missing = service.report(
        record=UserProfileRecord(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id="11111111-1111-4111-8111-111111111111",
            facts=(),
        ),
        modelo=Modelo.M111.value,
        revision_id="2019-y-siguientes",
        period=period,
    )

    assert missing.ready is False
    assert missing.per_operation_requirements_assessed is True
    assert [(item.section_key, item.field_key) for item in missing.missing] == [
        ("withholding", "colegio_concertado"),
    ]

    for declared in (False, True):
        ready = service.report(
            record=UserProfileRecord(
                setup_state=ProfileSetupState.COMPLETE,
                profile_id="11111111-1111-4111-8111-111111111111",
                facts=(UserProfileFact(path="withholding.colegio_concertado", value=declared),),
            ),
            modelo=Modelo.M111.value,
            revision_id="2019-y-siguientes",
            period=period,
        )
        assert ready.ready is True
        assert ready.missing == ()


def test_preflight_does_not_require_the_m111_declaration_for_another_modelo(
    schema: ProfileSchemaDefinition,
) -> None:
    report = ProfilePreflightService(schema=schema).report(
        record=UserProfileRecord(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id="11111111-1111-4111-8111-111111111111",
            facts=(),
        ),
        modelo=Modelo.M200.value,
        revision_id="2024-y-siguientes",
        period=Period.from_year_and_code(2024, "0A"),
    )

    assert not any(item.field_key == "colegio_concertado" for item in report.missing)


def test_preflight_accepts_legal_entity_legal_name_for_export_headers(schema: ProfileSchemaDefinition) -> None:
    period = Period.from_year_and_code(2026, "1P")
    snapshot = resources().modelos.authority.snapshot("202", filing_year=2026, period=period.registry_token)
    record = UserProfileRecord(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id="11111111-1111-4111-8111-111111111111",
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
            setup_state=ProfileSetupState.COMPLETE,
            profile_id="11111111-1111-4111-8111-111111111111",
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
    record = UserProfileRecord(
        setup_state=ProfileSetupState.COMPLETE, profile_id="11111111-1111-4111-8111-111111111111", facts=()
    )
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


def test_preflight_requirement_carries_catalogue_label_and_legal_refs(schema: ProfileSchemaDefinition) -> None:
    field = schema.field("identity.tax_id")

    requirement = build_profile_preflight_requirement(
        "identity.tax_id",
        schema=schema,
        selector="identity.tax_id",
        grounding_index={},
    )

    assert requirement.label == profile_field_label("identity", field)
    assert requirement.legal_refs == tuple(sorted(field.legal_refs))
    assert requirement.modelos == ()


def test_preflight_requirement_modelos_reflects_grounding_union_not_the_call_target(
    schema: ProfileSchemaDefinition,
) -> None:
    """``modelos`` is the registry-grounded consuming set, never the caller's target."""
    grounding = ProfileKeyGrounding(
        profile_key="identity.tax_id",
        modelos=(Modelo.M100,),
        legal_refs=("orden-hac-242-2025:art-3",),
        source_refs=(),
    )

    requirement = build_profile_preflight_requirement(
        "identity.tax_id",
        schema=schema,
        selector="identity.tax_id",
        grounding_index={"identity.tax_id": grounding},
    )

    # The grounding names M100; the call itself carries no target-modelo concept
    # any more, so the row must reflect the grounded set exactly, not a caller hint.
    assert requirement.modelos == (Modelo.M100.value,)
    assert "orden-hac-242-2025:art-3" in requirement.legal_refs


def test_preflight_requirement_never_invents_grounding_for_unknown_path(
    schema: ProfileSchemaDefinition,
) -> None:
    requirement = build_profile_preflight_requirement(
        "not_a_real_section.not_a_real_field",
        schema=schema,
        selector="not.a.real.schema.path",
        grounding_index={},
    )

    assert requirement.label == "not.a.real.schema.path"
    assert requirement.legal_refs == ()


def test_preflight_requirement_builder_matches_service_report_output_for_tax_id(
    schema: ProfileSchemaDefinition,
) -> None:
    """Parity: the shared builder reproduces what the service's own walk produces.

    ``ProfilePreflightService.report`` and the modelo-work readiness gate's
    baseline/validation checks route through one shared requirement-row
    builder. This proves ``build_profile_preflight_requirement`` produces,
    for the same path, selector and grounding, an identical row to what
    ``ProfilePreflightService.report`` surfaces for a profile missing
    ``identity.tax_id`` under Modelo 100.
    """
    svc = ProfilePreflightService(schema=schema)
    period = Period.from_year_and_code(2024, "0A")
    record = UserProfileRecord(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id="11111111-1111-4111-8111-111111111111",
        facts=(),
    )

    report = svc.report(record=record, modelo="100", revision_id="2024-y-siguientes", period=period)
    (from_report,) = [item for item in report.missing if item.field_key == "tax_id"]

    direct = build_profile_preflight_requirement(
        "identity.tax_id",
        schema=schema,
        selector=from_report.selector,
        grounding_index={},
    )

    assert direct == from_report


def test_preflight_requirement_model_roundtrips_every_field_populated() -> None:
    requirement = ProfilePreflightRequirement(
        selector="identity.tax_id",
        section_key="identity",
        field_key="tax_id",
        label="Tax identification number",
        legal_refs=("LGT art. 1",),
        modelos=("100", "303"),
    )

    roundtripped = ProfilePreflightRequirement.model_validate(requirement.model_dump())

    assert roundtripped == requirement


def test_preflight_requirement_anti_tautology_dropped_label_refuses_to_load() -> None:
    """A payload missing the required ``label`` must not silently reload as valid.

    Proves the roundtrip above is not vacuous: mutate a valid dump by
    deleting the required ``label`` field, and confirm the strict model
    actually refuses it rather than defaulting or coercing it away.
    """
    payload = ProfilePreflightRequirement(
        selector="identity.tax_id",
        section_key="identity",
        field_key="tax_id",
        label="Tax identification number",
        legal_refs=("LGT art. 1",),
        modelos=("100",),
    ).model_dump()
    del payload["label"]

    with pytest.raises(ValidationError):
        ProfilePreflightRequirement.model_validate(payload)
