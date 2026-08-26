"""Proofs for the settled profile presentation contract (D6).

Every assertion drives the real production schema through a real registered
profile record -- no synthetic schema, since `build_profile_presentation`
resolves the one committed `load_user_profile_schema()` rather than an
injectable one, matching every other presentation-layer consumer of that
schema.
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError

from ....domain.user_profile.values import UserProfileFact
from ....tests.secure_sql import isolated_profile_storage_root
from ..login_session import login_profile
from ..presentation import (
    ProfileFieldClassification,
    ProfileFieldPresentationV1,
    ProfileFieldSourceClass,
    build_profile_presentation,
    profile_field_source_class,
)
from ..profile_record_repository import ProfileRecordRepository
from ..registration import register_profile_with_credentials

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_PASSPHRASE = "profile-presentation-passphrase"  # noqa: S105 - isolated integration fixture


def _real_record(tmp_path: Path, *, facts: tuple[UserProfileFact, ...]):
    with isolated_profile_storage_root(tmp_path=tmp_path):
        enrolled = register_profile_with_credentials(
            label="Profile presentation subject",
            passphrase=_PASSPHRASE,
            facts=facts,
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
        )
        login_profile(name=enrolled.profile_id, passphrase_callback=lambda: _PASSPHRASE)
        profile_id = UUID(enrolled.profile_id)
        return ProfileRecordRepository.for_current_session(profile_id).load(profile_id)


def test_a_conditional_field_with_no_trigger_answer_needs_applicability(tmp_path: Path) -> None:
    """auth.clave_movil_route is unassessed, not not-applicable, while auth.provider is blank."""
    record = _real_record(tmp_path, facts=())

    presentation = build_profile_presentation(record)

    row = next(field for field in presentation.fields if field.path == "auth.clave_movil_route")
    assert row.classification is ProfileFieldClassification.NEEDS_APPLICABILITY
    assert row.applicability_assessed is False
    assert row.blocks_ready is True
    assert row.source is None


def test_answering_the_trigger_resolves_the_conditional_field_as_missing(tmp_path: Path) -> None:
    """Once auth.provider names clave_movil, the route field becomes an applicable requirement."""
    record = _real_record(
        tmp_path,
        facts=(UserProfileFact(path="auth.provider", value="clave_movil", source="manual_cli"),),
    )

    presentation = build_profile_presentation(record)

    provider_row = next(field for field in presentation.fields if field.path == "auth.provider")
    assert provider_row.classification is ProfileFieldClassification.OPTIONAL
    assert provider_row.present is True
    assert provider_row.source is ProfileFieldSourceClass.MANUAL_EDIT

    route_row = next(field for field in presentation.fields if field.path == "auth.clave_movil_route")
    assert route_row.classification is ProfileFieldClassification.APPLICABLE_REQUIRED_MISSING
    assert route_row.applicability_assessed is True
    assert route_row.blocks_ready is True


def test_answering_the_conditional_field_itself_clears_the_block(tmp_path: Path) -> None:
    """A fully answered conditional pair carries no blocking row for either field."""
    record = _real_record(
        tmp_path,
        facts=(
            UserProfileFact(path="auth.provider", value="clave_movil", source="manual_cli"),
            UserProfileFact(path="auth.clave_movil_route", value="qr", source="manual_cli"),
        ),
    )

    presentation = build_profile_presentation(record)

    route_row = next(field for field in presentation.fields if field.path == "auth.clave_movil_route")
    assert route_row.classification is ProfileFieldClassification.APPLICABLE_REQUIRED_PRESENT
    assert route_row.blocks_ready is False
    assert route_row.source is ProfileFieldSourceClass.MANUAL_EDIT


def test_a_trigger_answered_away_from_the_gated_value_is_not_applicable(tmp_path: Path) -> None:
    """auth.provider naming a non-clave_movil provider settles the route field as not applicable."""
    record = _real_record(
        tmp_path,
        facts=(UserProfileFact(path="auth.provider", value="certificate", source="manual_cli"),),
    )

    presentation = build_profile_presentation(record)

    route_row = next(field for field in presentation.fields if field.path == "auth.clave_movil_route")
    assert route_row.classification is ProfileFieldClassification.NOT_APPLICABLE
    assert route_row.applicability_assessed is True
    assert route_row.blocks_ready is False


def test_static_schema_required_field_missing_blocks_readiness(tmp_path: Path) -> None:
    """A field the schema unconditionally requires blocks readiness while blank."""
    record = _real_record(tmp_path, facts=())

    presentation = build_profile_presentation(record)

    required_rows = [
        f for f in presentation.fields if f.classification is ProfileFieldClassification.APPLICABLE_REQUIRED_MISSING
    ]
    assert required_rows, "a freshly registered profile must carry at least one unconditionally required blank field"
    assert presentation.ready is False
    assert set(presentation.blocking_fields) >= set(required_rows)


def test_aeat_censo_read_source_maps_to_aeat_census_acquisition(tmp_path: Path) -> None:
    """The schema's real censo-read provenance token classifies as AEAT census acquisition."""
    record = _real_record(
        tmp_path,
        facts=(UserProfileFact(path="contact.postcode", value="28013", source="aeat_censo_read"),),
    )

    presentation = build_profile_presentation(record)

    row = next(field for field in presentation.fields if field.path == "contact.postcode")
    assert row.source is ProfileFieldSourceClass.AEAT_CENSUS_ACQUISITION


def test_profile_field_source_class_refuses_an_undeclared_token() -> None:
    with pytest.raises(ValueError, match="unmapped provenance source token"):
        profile_field_source_class("not-a-declared-token")


def test_presentation_row_refuses_a_present_field_without_a_source() -> None:
    with pytest.raises(ValidationError, match="must carry a source class"):
        ProfileFieldPresentationV1(
            path="auth.provider",
            classification=ProfileFieldClassification.OPTIONAL,
            present=True,
            applicability_assessed=True,
            source=None,
            blocks_ready=False,
        )


def test_presentation_row_refuses_blocks_ready_disagreeing_with_classification() -> None:
    with pytest.raises(ValidationError, match="must match the classification"):
        ProfileFieldPresentationV1(
            path="auth.clave_movil_route",
            classification=ProfileFieldClassification.OPTIONAL,
            present=False,
            applicability_assessed=True,
            source=None,
            blocks_ready=True,
        )
