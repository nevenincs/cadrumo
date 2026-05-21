"""Source mesh coverage for profile-backed calculation sources."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ...core.resources import resources
from ...domain.user_profile import UserProfileFact, UserProfileRecord
from ..modelo._profile_binding import resolve_profile_sourced_bindings
from . import CalculationSourceContext, ProfileSourceResolver

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_CLOCK = datetime(2026, 5, 21, 10, 0, 0, tzinfo=UTC)
_BUCKET_ID = "operator"
_CCAA_BINDING = "renta-2025-profile-tax-residence-ccaa"


def _modelo_100_snapshot():
    return resources().modelos.authority.snapshot("100", filing_year=2025, period="0A")


def _profile_with_ccaa(ccaa: str) -> UserProfileRecord:
    return UserProfileRecord(
        profile_id=_BUCKET_ID,
        display_name="Renta profile taxpayer",
        facts=(
            UserProfileFact(path="identity.tax_id", value="12345678Z"),
            UserProfileFact(path="tax_residence.ccaa", value=ccaa),
        ),
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )


def test_profile_source_resolver_matches_existing_profile_binding_resolution() -> None:
    snapshot = _modelo_100_snapshot()
    profile_record = _profile_with_ccaa("madrid")

    legacy = resolve_profile_sourced_bindings(
        snapshot,
        bucket_id=_BUCKET_ID,
        profile_record=profile_record,
    )
    resolution = ProfileSourceResolver(
        registry_snapshot=snapshot,
        profile_record=profile_record,
    ).resolve(
        CalculationSourceContext(
            bucket_id=_BUCKET_ID,
            modelo="100",
            filing_year=2025,
            period="0A",
            revision=snapshot.revision,
        )
    )

    assert resolution.binding_values == legacy.binding_values
    assert resolution.enum_binding_values == legacy.enum_binding_values
    assert resolution.source_transaction_ids == ()
    assert resolution.provenance
    assert {
        item.source_ref for item in resolution.provenance if item.source_kind == "profile"
    } == {f"profile:{_BUCKET_ID}:binding:{_CCAA_BINDING}"}


def test_profile_source_resolver_respects_caller_owned_precedence() -> None:
    snapshot = _modelo_100_snapshot()
    profile_record = _profile_with_ccaa("cataluna")

    resolution = ProfileSourceResolver(
        registry_snapshot=snapshot,
        profile_record=profile_record,
        caller_binding_ids=(_CCAA_BINDING,),
    ).resolve(
        CalculationSourceContext(
            bucket_id=_BUCKET_ID,
            modelo="100",
            filing_year=2025,
            period="0A",
            revision=snapshot.revision,
        )
    )

    assert _CCAA_BINDING not in resolution.binding_values
    assert _CCAA_BINDING not in resolution.enum_binding_values
    assert resolution.provenance == ()
