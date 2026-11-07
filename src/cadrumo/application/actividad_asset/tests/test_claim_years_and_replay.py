"""One year filter on forecasts and walks, the claim ceiling, and replay of every write.

Figures use the 26% test table: 2,000.00 charges 520.00 a full year and 1,000.00 charges 260.00.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal

import pytest

from cadrumo.application.actividad_asset.activity_asset_read_models import (
    ActivityAssetReasonFact,
    project_reason_facts,
)
from cadrumo.application.actividad_asset.disposal_calculation import year_minimum
from cadrumo.application.actividad_asset.operations import ActivityAssetOperations
from cadrumo.application.actividad_asset.schedule_walk import walk_element
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.actividad_asset_bindings import ActivityAssetDisposalBounds
from cadrumo.domain.renta.actividad_asset.disposal import ActivityAssetDisposal, ActivityAssetDisposalReason
from cadrumo.domain.renta.actividad_asset.election import AmortizationMethod, DirectEstimationRegime
from cadrumo.domain.renta.actividad_asset.errors import (
    ActividadAssetClaimConflictError,
    ActividadAssetUnsupportedError,
    ActividadAssetValidationError,
)
from cadrumo.domain.renta.actividad_asset.lifecycle import ActivityAssetRevision
from cadrumo.domain.renta.actividad_asset.register_records import ActivityAssetDescriptorFacts
from cadrumo.domain.renta.actividad_asset.schedule import (
    AssetScheduleHistory,
    ScheduleAuthority,
    ScheduledAmortizationCharge,
    schedule_charge,
)

from ....domain.calculations.registry.authority import bundled_indexed_authority
from .ledger_support import MemoryLedger
from .register_support import MemoryRepository, memory_register_authority
from .test_baja_correction import low_value_forecast, low_value_revision
from .test_register import ACQUISITION, NAME, full_year, register_forecast, register_operations, register_revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_FIRST = register_revision().in_service_date.year


@pytest.fixture(autouse=True)
def _pinned_authority() -> Iterator[None]:
    """Hold the authority the runtime holds, so code that reads a form fact has it."""
    with bundled_indexed_authority().operation():
        yield


_ASSET = "laptop-1"


def _bounded(
    last_admitted_year: int, *, today: date = date(_FIRST, 12, 31)
) -> tuple[ActivityAssetOperations, MemoryRepository]:
    repository = MemoryRepository()
    return (
        ActivityAssetOperations(
            repository=repository,
            ledger=MemoryLedger(ACQUISITION),
            forecast_operation=register_forecast,
            taxpayer_modality=lambda: DirectEstimationRegime.SIMPLIFIED,
            register_authority=memory_register_authority(today=today, last_admitted_year=last_admitted_year),
        ),
        repository,
    )


def _sale(on: date = date(_FIRST + 1, 6, 30), *, later_affectation_on: date | None = None) -> ActivityAssetDisposal:
    return ActivityAssetDisposal(
        disposal_date=on,
        reason=ActivityAssetDisposalReason.SALE,
        proceeds=Decimal("100.00"),
        transmission_costs=Decimal("0.00"),
        later_affectation_on=later_affectation_on,
    )


def test_a_later_claim_moves_neither_the_forecast_nor_the_walk_of_an_earlier_year() -> None:
    operations, repository = register_operations(today=date(_FIRST + 6, 12, 31), last_admitted_year=_FIRST + 5)
    operations.create(register_revision(basis="1000"), NAME)
    before = full_year(operations, _FIRST)
    for year in (_FIRST + 3, _FIRST + 4, _FIRST + 5):
        operations.record_claim(full_year(operations, year), creating_operation=f"test.{year}")

    forecast = full_year(operations, _FIRST)
    walked = walk_element(
        repository.history.revisions[-1], repository.history, forecast=register_forecast, through_year=_FIRST
    )[0]

    # Three later years at 260.00 leave 220.00, but the year's own charge stays 260.00 on both routes.
    assert forecast == before
    assert forecast.amount == Decimal("260.00")
    assert walked.charge is not None
    assert walked.charge.amount == forecast.amount
    assert walked.charge.schedule_fingerprint == forecast.schedule_fingerprint


def test_a_claim_behind_later_ones_that_consumed_the_basis_is_refused_at_the_write() -> None:
    operations, repository = register_operations(today=date(_FIRST + 6, 12, 31), last_admitted_year=_FIRST + 5)
    operations.create(register_revision(basis="1000"), NAME)
    for year in (_FIRST + 3, _FIRST + 4, _FIRST + 5):
        operations.record_claim(full_year(operations, year), creating_operation=f"test.{year}")
    before = repository.history

    with pytest.raises(ActividadAssetClaimConflictError, match="claims_exceed_amortizable_basis"):
        operations.record_claim(full_year(operations, _FIRST), creating_operation=f"test.{_FIRST}")

    assert repository.history == before


def constant_forecast(
    revision: ActivityAssetRevision,
    *,
    covered_from: date,
    covered_until: date,
    history: AssetScheduleHistory,
    requested_free_amount: Decimal | None = None,
) -> ScheduledAmortizationCharge:
    return schedule_charge(
        revision,
        ScheduleAuthority(
            tax_year=covered_from.year,
            asset_kind=revision.asset_kind,
            method=revision.amortization.method,
            election_fingerprint=revision.amortization.fingerprint,
            annual_rate=Decimal("0.26"),
            authority_generation="replay-test",
            source_reference="replay test table",
            useful_life_ends_on=date(_FIRST + 10, 1, 1),
        ),
        covered_from=covered_from,
        covered_until=covered_until,
        history=history,
        requested_free_amount=requested_free_amount,
    )


def test_a_later_claim_still_refuses_a_method_that_follows_the_pending_value() -> None:
    operations = ActivityAssetOperations(
        repository=MemoryRepository(),
        ledger=MemoryLedger(ACQUISITION),
        forecast_operation=constant_forecast,
        taxpayer_modality=lambda: DirectEstimationRegime.SIMPLIFIED,
        register_authority=memory_register_authority(today=date(_FIRST + 6, 12, 31), last_admitted_year=_FIRST + 5),
    )
    operations.create(register_revision(method=AmortizationMethod.CONSTANT_PERCENTAGE), NAME)
    operations.record_claim(full_year(operations, _FIRST + 2), creating_operation=f"test.{_FIRST + 2}")

    with pytest.raises(ActividadAssetUnsupportedError, match="earlier_year_depends_on_pending_value"):
        full_year(operations, _FIRST)


def test_the_last_admitted_year_takes_a_claim_and_the_next_is_refused_with_its_reason() -> None:
    operations, repository = _bounded(_FIRST + 1)
    operations.create(register_revision(), NAME)
    assert operations.record_claim(
        full_year(operations, _FIRST + 1), creating_operation=f"test.{_FIRST + 1}"
    ).claim.amount == Decimal("520.00")
    before = repository.history
    beyond = full_year(operations, _FIRST + 2)

    with pytest.raises(ActividadAssetUnsupportedError, match="claim_year_beyond_registry") as refused:
        operations.record_claim(beyond, creating_operation=f"test.{_FIRST + 2}")

    assert refused.value.context == {"tax_year": _FIRST + 2, "last_admitted_year": _FIRST + 1}
    assert beyond.amount == Decimal("520.00")
    assert repository.history == before


def test_the_list_offers_admitted_years_and_marks_later_ones_as_projection() -> None:
    operations, _ = _bounded(_FIRST + 1)
    operations.create(register_revision(), NAME)

    (row,) = operations.list_elements()
    plan = {item.tax_year: item for item in operations.plan(_ASSET)}

    assert row.years == (_FIRST, _FIRST + 1)
    assert row.projected_years == (_FIRST + 2, _FIRST + 3, _FIRST + 4)
    edition = plan[_FIRST + 2].edition
    assert edition is not None
    assert edition.projected is True


def test_an_identical_create_retry_returns_the_recorded_history() -> None:
    operations, repository = register_operations()
    operations.create(register_revision(), NAME)
    before = repository.history

    assert operations.create(register_revision(), NAME) == before
    assert repository.history == before


@pytest.mark.parametrize(
    ("revision_basis", "descriptor"),
    [
        ("2100", NAME),
        (str(register_revision().basis.basis_amount), ActivityAssetDescriptorFacts(name="Another name")),
    ],
)
def test_a_differing_create_retry_is_refused(revision_basis: str, descriptor: ActivityAssetDescriptorFacts) -> None:
    operations, repository = register_operations()
    operations.create(register_revision(), NAME)
    before = repository.history

    with pytest.raises(ActividadAssetValidationError, match="asset_already_exists"):
        operations.create(register_revision(basis=revision_basis), descriptor)

    assert repository.history == before


def test_a_replayed_effective_claim_is_reused() -> None:
    operations, repository = register_operations()
    operations.create(register_revision(), NAME)
    charge = full_year(operations, _FIRST)
    first = operations.record_claim(charge, creating_operation="test.claim")
    before = repository.history

    again = operations.record_claim(charge, creating_operation="test.claim")

    assert again.reused_existing_claim is True
    assert again.claim == first.claim
    assert repository.history == before


def test_a_replayed_superseded_claim_is_refused_and_never_reported_as_reused() -> None:
    operations, repository = register_operations()
    operations.create(register_revision(), NAME)
    charge = full_year(operations, _FIRST)
    first = operations.record_claim(charge, creating_operation="test.claim").claim
    repository.record_claim(
        first.model_copy(
            update={
                "amount": first.amount - Decimal("10.00"),
                "supersedes_claim_id": first.claim_id,
                "creating_operation": "test.replacement",
            }
        )
    )
    before = repository.history

    with pytest.raises(ActividadAssetClaimConflictError, match="claim_superseded_replay"):
        operations.record_claim(charge, creating_operation="test.claim")

    assert repository.history == before


def test_a_useful_life_ending_on_entry_gives_no_minimum_rather_than_dividing_by_zero() -> None:
    revision = register_revision()

    assert (
        year_minimum(
            revision,
            tax_year=_FIRST,
            boundary=date(_FIRST + 1, 1, 1),
            bounds=ActivityAssetDisposalBounds(useful_life_ends_on=revision.in_service_date),
        )
        is None
    )


def test_a_zero_baja_claim_accrues_nothing_in_modelo_130() -> None:
    repository = MemoryRepository()
    operations = ActivityAssetOperations(
        repository=repository,
        ledger=MemoryLedger(ACQUISITION),
        forecast_operation=low_value_forecast,
        taxpayer_modality=lambda: DirectEstimationRegime.SIMPLIFIED,
        register_authority=memory_register_authority(today=date(_FIRST + 1, 12, 31)),
    )
    operations.create(low_value_revision(), NAME)
    elected = operations.forecast(
        asset_id=_ASSET,
        covered_from=date(_FIRST, 7, 1),
        covered_until=date(_FIRST + 1, 1, 1),
        requested_free_amount=Decimal("180.00"),
    )
    operations.record_claim(elected, creating_operation="test.free")
    operations.dispose(_ASSET, _sale(date(_FIRST, 3, 31)))

    handoff = operations.filing_handoff(tax_year=_FIRST, m130_period=Period.from_year_and_code(_FIRST, "4T"))

    assert handoff.material_m130 is not None
    assert handoff.material_m130.amount == Decimal("0.00")
    assert handoff.material_m130.contributions == ()
    assert handoff.material_m130.unavailable_asset_ids == ()


def test_a_reason_fact_is_bounded_and_its_projection_stays_within_the_bound() -> None:
    with pytest.raises(ValueError, match="at most 64"):
        ActivityAssetReasonFact(key="k" * 65, value="v")
    with pytest.raises(ValueError, match="at most 2048"):
        ActivityAssetReasonFact(key="k", value="v" * 2049)

    (fact,) = project_reason_facts({"k" * 70: "v" * 3000})

    assert (len(fact.key), len(fact.value)) == (64, 2048)


def test_a_later_affectation_after_entry_into_service_is_refused() -> None:
    operations, repository = register_operations(today=date(_FIRST + 1, 12, 31))
    operations.create(register_revision(in_service=date(_FIRST, 1, 1)), NAME)
    before = repository.history

    with pytest.raises(ActividadAssetValidationError, match="later_affectation_out_of_order"):
        operations.dispose(_ASSET, _sale(later_affectation_on=date(_FIRST, 1, 2)))

    assert repository.history == before


@pytest.mark.parametrize("affected", [date(_FIRST - 1, 6, 1), date(_FIRST, 1, 1)])
def test_a_later_affectation_up_to_entry_into_service_is_admitted(affected: date) -> None:
    operations, _ = register_operations(today=date(_FIRST + 1, 12, 31))
    operations.create(register_revision(in_service=date(_FIRST, 1, 1)), NAME)

    after = operations.dispose(_ASSET, _sale(later_affectation_on=affected))

    assert after.revisions[-1].disposal is not None
    assert after.revisions[-1].disposal.later_affectation_on == affected
