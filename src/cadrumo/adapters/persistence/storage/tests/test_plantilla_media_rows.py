"""Average-workforce years written and read through the encrypted profile."""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from typing import TypedDict

import pytest

from cadrumo.adapters.persistence.profile.tests.profile_registration import register_minimal_profile
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.application.user_profile.capsule_record import ProfileRecordConflictError
from cadrumo.application.user_profile.login_session import login_profile
from cadrumo.application.user_profile.plantilla_media_rows import (
    PlantillaMediaMutation,
    PlantillaMediaWriteSurface,
    list_plantilla_media_years,
    remove_plantilla_media_year,
    set_plantilla_media_year,
)
from cadrumo.application.user_profile.profile_record_repository import ProfileRecordRepository
from cadrumo.application.user_profile.registration import register_profile_with_credentials
from cadrumo.core.config import override_settings
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.authority_artifact import ProfileDecodeContext
from cadrumo.domain.user_profile.errors import ProfileSchemaValidationError, UserProfileValidationError
from cadrumo.domain.user_profile.plantilla_media import PlantillaMediaState

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]

_CLI = PlantillaMediaWriteSurface.CLI
_OBSERVED = PlantillaMediaState.OBSERVED
_COMMITTED = PlantillaMediaState.COMMITTED


class _CommonArgs(TypedDict):
    profile_id: str
    surface: PlantillaMediaWriteSurface
    profile_decode_context: ProfileDecodeContext


@pytest.fixture
def profile(tmp_path: Path) -> Iterator[tuple[str, ProfileDecodeContext]]:
    """Register, log in and seed one complete profile inside a leased authority."""
    passphrase = f"plantilla-media-{tmp_path.name}"
    with (
        override_settings(cadrumo_secret_passphrase=passphrase),
        isolated_profile_storage_root(tmp_path=tmp_path),
        bundled_indexed_authority().operation() as operation,
    ):
        outcome = register_profile_with_credentials(
            label="Average workforce",
            passphrase=passphrase,
            profile_create_context=operation.profile_create_context(),
            profile_decode_context=operation.profile_decode_context(),
        )
        login_profile(
            name=outcome.label,
            passphrase_callback=passphrase.__str__,
            profile_decode_context=operation.profile_decode_context(),
        )
        register_minimal_profile(profile_id=outcome.profile_id)
        yield outcome.profile_id, operation.profile_decode_context()


def _indices(profile_id: str, context: ProfileDecodeContext) -> set[str]:
    record = ProfileRecordRepository.for_current_session(profile_id, profile_decode_context=context).load(profile_id)
    return {
        fact.path.split(".")[2]
        for fact in record.facts
        if fact.path.startswith("irpf.plantilla_media.") and fact.value is not None
    }


def test_years_are_set_replaced_and_listed_in_year_order(profile: tuple[str, ProfileDecodeContext]) -> None:
    profile_id, context = profile
    common: _CommonArgs = {"profile_id": profile_id, "surface": _CLI, "profile_decode_context": context}

    set_plantilla_media_year(year=2025, average_workforce=Decimal("12.50"), state=_COMMITTED, **common)
    set_plantilla_media_year(year=2024, average_workforce=Decimal("10.00"), state=_OBSERVED, **common)
    replaced = set_plantilla_media_year(year=2025, average_workforce=Decimal("11.75"), state=_OBSERVED, **common)

    assert isinstance(replaced, PlantillaMediaMutation)
    assert replaced.changed
    assert [(item.year, item.average_workforce, item.state) for item in replaced.years] == [
        (2024, Decimal("10.00"), _OBSERVED),
        (2025, Decimal("11.75"), _OBSERVED),
    ]
    # Replacing 2025 rewrote its own instance; no third instance appeared.
    assert _indices(profile_id, context) == {"0", "1"}
    assert list_plantilla_media_years(profile_id=profile_id, profile_decode_context=context) == replaced.years


def test_removing_a_year_renumbers_nothing_and_a_new_year_takes_a_fresh_index(
    profile: tuple[str, ProfileDecodeContext],
) -> None:
    profile_id, context = profile
    common: _CommonArgs = {"profile_id": profile_id, "surface": _CLI, "profile_decode_context": context}
    set_plantilla_media_year(year=2024, average_workforce=Decimal("10.00"), state=_OBSERVED, **common)
    set_plantilla_media_year(year=2025, average_workforce=Decimal("12.00"), state=_OBSERVED, **common)

    remaining = remove_plantilla_media_year(year=2024, **common)
    added = set_plantilla_media_year(year=2026, average_workforce=Decimal("12.00"), state=_COMMITTED, **common)

    assert [item.year for item in remaining.years] == [2025]
    assert [item.year for item in added.years] == [2025, 2026]
    # 2025 kept index 1, and 2026 did not reuse the withdrawn index 0.
    assert _indices(profile_id, context) == {"1", "2"}
    record = added.record
    assert {fact.path for fact in record.facts if fact.path.startswith("irpf.plantilla_media.0.")} == {
        "irpf.plantilla_media.0.year",
        "irpf.plantilla_media.0.average_workforce",
        "irpf.plantilla_media.0.state",
    }
    assert all(fact.value is None for fact in record.facts if fact.path.startswith("irpf.plantilla_media.0."))


def test_an_undeclared_year_and_an_invalid_value_refuse(profile: tuple[str, ProfileDecodeContext]) -> None:
    profile_id, context = profile
    common: _CommonArgs = {"profile_id": profile_id, "surface": _CLI, "profile_decode_context": context}

    with pytest.raises(UserProfileValidationError, match="2030 is not declared"):
        remove_plantilla_media_year(year=2030, **common)
    with pytest.raises(ProfileSchemaValidationError):
        set_plantilla_media_year(year=2025, average_workforce=Decimal("12.505"), state=_OBSERVED, **common)
    assert list_plantilla_media_years(profile_id=profile_id, profile_decode_context=context) == ()


def test_same_value_is_a_noop_with_the_original_commit_witness(profile: tuple[str, ProfileDecodeContext]) -> None:
    profile_id, context = profile
    common: _CommonArgs = {"profile_id": profile_id, "surface": _CLI, "profile_decode_context": context}
    first = set_plantilla_media_year(year=2025, average_workforce=Decimal("12.50"), state=_COMMITTED, **common)

    repeated = set_plantilla_media_year(
        year=2025,
        average_workforce=Decimal("12.50"),
        state=_COMMITTED,
        expected_revision=first.record.record_revision,
        expected_content_digest=first.record.content_digest,
        **common,
    )

    assert first.changed
    assert not repeated.changed
    assert repeated.record == first.record
    assert repeated.years == first.years


def test_stale_or_partial_baseline_refuses_before_noop(profile: tuple[str, ProfileDecodeContext]) -> None:
    profile_id, context = profile
    common: _CommonArgs = {"profile_id": profile_id, "surface": _CLI, "profile_decode_context": context}
    before = ProfileRecordRepository.for_current_session(profile_id, profile_decode_context=context).load(profile_id)
    first = set_plantilla_media_year(year=2025, average_workforce=Decimal("12.50"), state=_COMMITTED, **common)

    with pytest.raises(ProfileRecordConflictError, match="baseline is stale"):
        set_plantilla_media_year(
            year=2025,
            average_workforce=Decimal("12.50"),
            state=_COMMITTED,
            expected_revision=before.record_revision,
            expected_content_digest=before.content_digest,
            **common,
        )
    with pytest.raises(ProfileRecordConflictError, match="baseline is stale"):
        remove_plantilla_media_year(
            year=2025,
            expected_revision=before.record_revision,
            expected_content_digest=before.content_digest,
            **common,
        )
    with pytest.raises(ValueError, match="paired record baseline"):
        set_plantilla_media_year(
            year=2025,
            average_workforce=Decimal("12.50"),
            state=_COMMITTED,
            expected_revision=first.record.record_revision,
            **common,
        )
    with pytest.raises(ValueError, match="paired record baseline"):
        remove_plantilla_media_year(
            year=2025,
            expected_content_digest=first.record.content_digest,
            **common,
        )
    current = ProfileRecordRepository.for_current_session(profile_id, profile_decode_context=context).load(profile_id)
    assert current == first.record
