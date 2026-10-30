"""A foral or unreadable tax residence stops the register's work that reaches Modelos 100 and 130."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from datetime import date

import pytest

from cadrumo.application.actividad_asset.operations import ActivityAssetOperations, SupersedingClaimRequest
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.calculations.registry.tests.published_authority import leased_profile_create_context
from cadrumo.domain.renta.actividad_asset.errors import ActividadAssetValidationError
from cadrumo.domain.user_profile.values import (
    ProfileSetupState,
    UserProfileFact,
    UserProfileRecord,
    create_user_profile_record,
)

from ...aggregation.renta_ledger import resident_territory
from .register_support import MemoryRepository, describing, memory_register_authority
from .test_operations import _ledger, _linear_forecast, _revision, _simplified

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "11111111-1111-4111-8111-111111111111"
_FORAL_KEY = "ledger.actividad_asset.errors.foral_territory"
_UNRESOLVED_KEY = "ledger.actividad_asset.errors.tax_residence_unresolved"


@pytest.fixture
def operation() -> Iterator[PinnedAuthorityOperation]:
    with bundled_indexed_authority().operation() as pinned:
        yield pinned


def _profile(residence: str, *periods: UserProfileFact) -> UserProfileRecord:
    return create_user_profile_record(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_BUCKET_ID,
        facts=(
            UserProfileFact(path="identity.tax_id", value="X1234567L"),
            *(periods or (UserProfileFact(path="tax_residence.ccaa", value=residence),)),
        ),
        context=leased_profile_create_context(),
    )


def _registered(repository: MemoryRepository) -> ActivityAssetOperations:
    return ActivityAssetOperations(
        repository=repository,
        ledger=_ledger(),
        forecast_operation=_linear_forecast,
        taxpayer_modality=_simplified,
        register_authority=memory_register_authority(),
    )


def _resident_of(
    repository: MemoryRepository,
    residence: str,
    operation: PinnedAuthorityOperation,
    *periods: UserProfileFact,
) -> ActivityAssetOperations:
    """The same register, now answering the residence question from a real profile and the real catalogue."""
    record = _profile(residence, *periods)
    authority = replace(
        memory_register_authority(),
        residence_territory=lambda on: resident_territory(
            bucket_id=_BUCKET_ID, profile_record=record, operation=operation, as_of=on
        ),
    )
    return ActivityAssetOperations(
        repository=repository,
        ledger=_ledger(),
        forecast_operation=_linear_forecast,
        taxpayer_modality=_simplified,
        register_authority=authority,
    )


def _repository_with_a_claim() -> tuple[MemoryRepository, str, str]:
    repository = MemoryRepository()
    registered = _registered(repository)
    revision = _revision()
    registered.create(revision, describing(revision))
    forecast = registered.forecast(
        asset_id=revision.asset_id,
        covered_from=date(2025, 1, 1),
        covered_until=date(2025, 7, 1),
    )
    claim = registered.record_claim(forecast, creating_operation="test.claim").claim
    return repository, revision.asset_id, claim.claim_id


@pytest.mark.parametrize(
    "residence",
    ["araba", "alava", "bizkaia", "vizcaya", "gipuzkoa", "guipuzcoa", "navarra"],
)
def test_a_foral_resident_cannot_forecast_claim_correct_or_hand_off(
    residence: str,
    operation: PinnedAuthorityOperation,
) -> None:
    repository, asset_id, claim_id = _repository_with_a_claim()
    foral = _resident_of(repository, residence, operation)
    covered_from = date(2025, 7, 1)
    covered_until = date(2026, 1, 1)
    carried = _registered(repository).forecast(
        asset_id=asset_id, covered_from=covered_from, covered_until=covered_until
    )

    with pytest.raises(ActividadAssetValidationError) as forecast:
        foral.forecast(asset_id=asset_id, covered_from=covered_from, covered_until=covered_until)
    with pytest.raises(ActividadAssetValidationError) as claim:
        foral.record_claim(carried, creating_operation="test.foral")
    with pytest.raises(ActividadAssetValidationError) as correction:
        foral.correct(
            _revision(number=2, supersedes=foral.inspect(asset_id)[-1].revision_id),
            (SupersedingClaimRequest(supersedes_claim_id=claim_id),),
        )
    with pytest.raises(ActividadAssetValidationError) as handoff:
        foral.filing_handoff(tax_year=2025, m130_period=Period.from_year_and_code(2025, "4T"))

    assert [error.value.translated_message for error in (forecast, claim, correction, handoff)] == [_FORAL_KEY] * 4
    assert len(repository.history.claims) == 1


def test_a_write_is_refused_only_for_the_period_truly_in_foral_territory(
    operation: PinnedAuthorityOperation,
) -> None:
    repository, asset_id, _ = _repository_with_a_claim()
    moved = _resident_of(
        repository,
        "",
        operation,
        UserProfileFact(path="tax_residence.ccaa", value="madrid", valid_to=date(2025, 12, 30)),
        UserProfileFact(path="tax_residence.ccaa", value="navarra", valid_from=date(2025, 12, 31)),
    )

    with pytest.raises(ActividadAssetValidationError) as foral_year:
        moved.forecast(asset_id=asset_id, covered_from=date(2025, 7, 1), covered_until=date(2026, 1, 1))

    assert foral_year.value.translated_message == _FORAL_KEY


def test_a_write_for_a_year_before_a_move_to_foral_territory_still_goes_through(
    operation: PinnedAuthorityOperation,
) -> None:
    repository, asset_id, _ = _repository_with_a_claim()
    moved = _resident_of(
        repository,
        "",
        operation,
        UserProfileFact(path="tax_residence.ccaa", value="madrid", valid_to=date(2026, 12, 31)),
        UserProfileFact(path="tax_residence.ccaa", value="navarra", valid_from=date(2027, 1, 1)),
    )

    forecast = moved.forecast(asset_id=asset_id, covered_from=date(2025, 7, 1), covered_until=date(2026, 1, 1))

    assert forecast.asset_id == asset_id


def test_a_write_for_a_period_no_residence_covers_is_not_refused(
    operation: PinnedAuthorityOperation,
) -> None:
    repository, asset_id, _ = _repository_with_a_claim()
    later_only = _resident_of(
        repository,
        "",
        operation,
        UserProfileFact(path="tax_residence.ccaa", value="navarra", valid_from=date(2030, 1, 1)),
    )

    forecast = later_only.forecast(asset_id=asset_id, covered_from=date(2025, 7, 1), covered_until=date(2026, 1, 1))

    assert forecast.asset_id == asset_id


def test_an_unreadable_residence_is_refused_as_unresolved_not_treated_as_common(
    operation: PinnedAuthorityOperation,
) -> None:
    repository, asset_id, _ = _repository_with_a_claim()
    unreadable = _resident_of(repository, "atlantis", operation)

    with pytest.raises(ActividadAssetValidationError) as forecast:
        unreadable.forecast(asset_id=asset_id, covered_from=date(2025, 7, 1), covered_until=date(2026, 1, 1))

    assert forecast.value.translated_message == _UNRESOLVED_KEY


@pytest.mark.parametrize("residence", ["madrid", "cataluna", "andalucia"])
def test_a_common_territory_resident_forecasts_and_hands_off(
    residence: str,
    operation: PinnedAuthorityOperation,
) -> None:
    repository, asset_id, _ = _repository_with_a_claim()
    common = _resident_of(repository, residence, operation)

    forecast = common.forecast(asset_id=asset_id, covered_from=date(2025, 7, 1), covered_until=date(2026, 1, 1))
    handoff = common.filing_handoff(tax_year=2025, m130_period=Period.from_year_and_code(2025, "4T"))

    assert forecast.asset_id == asset_id
    assert handoff.material_m100.tax_year == 2025
