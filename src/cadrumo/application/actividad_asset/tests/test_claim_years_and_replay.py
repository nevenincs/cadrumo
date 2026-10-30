"""One year filter on forecasts and walks, the claim ceiling, and replay of every write.

Figures use the 26% test table: 2,000.00 charges 520.00 a full year and 1,000.00 charges 260.00.
"""

from __future__ import annotations

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

from .ledger_support import MemoryLedger
from .register_support import MemoryRepository, memory_register_authority
from .test_baja_correction import _low_value_forecast, _low_value_revision
from .test_register import _ACQUISITION, _NAME, _forecast, _full_year, _operations, _revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ASSET = "laptop-1"


def _bounded(
    last_admitted_year: int, *, today: date = date(2025, 12, 31)
) -> tuple[ActivityAssetOperations, MemoryRepository]:
    repository = MemoryRepository()
    return (
        ActivityAssetOperations(
            repository=repository,
            ledger=MemoryLedger(_ACQUISITION),
            forecast_operation=_forecast,
            taxpayer_modality=lambda: DirectEstimationRegime.SIMPLIFIED,
            register_authority=memory_register_authority(today=today, last_admitted_year=last_admitted_year),
        ),
        repository,
    )


def _sale(on: date = date(2026, 6, 30), *, later_affectation_on: date | None = None) -> ActivityAssetDisposal:
    return ActivityAssetDisposal(
        disposal_date=on,
        reason=ActivityAssetDisposalReason.SALE,
        proceeds=Decimal("100.00"),
        transmission_costs=Decimal("0.00"),
        later_affectation_on=later_affectation_on,
    )


def test_a_later_claim_moves_neither_the_forecast_nor_the_walk_of_an_earlier_year() -> None:
    operations, repository = _operations(today=date(2031, 12, 31))
    operations.create(_revision(basis="1000"), _NAME)
    before = _full_year(operations, 2025)
    for year in (2028, 2029, 2030):
        operations.record_claim(_full_year(operations, year), creating_operation=f"test.{year}")

    forecast = _full_year(operations, 2025)
    walked = walk_element(repository.history.revisions[-1], repository.history, forecast=_forecast, through_year=2025)[
        0
    ]

    # Three later years at 260.00 leave 220.00, but the year's own charge stays 260.00 on both routes.
    assert forecast == before
    assert forecast.amount == Decimal("260.00")
    assert walked.charge is not None
    assert walked.charge.amount == forecast.amount
    assert walked.charge.schedule_fingerprint == forecast.schedule_fingerprint


def test_a_claim_behind_later_ones_that_consumed_the_basis_is_refused_at_the_write() -> None:
    operations, repository = _operations(today=date(2031, 12, 31))
    operations.create(_revision(basis="1000"), _NAME)
    for year in (2028, 2029, 2030):
        operations.record_claim(_full_year(operations, year), creating_operation=f"test.{year}")
    before = repository.history

    with pytest.raises(ActividadAssetClaimConflictError, match="claims_exceed_amortizable_basis"):
        operations.record_claim(_full_year(operations, 2025), creating_operation="test.2025")

    assert repository.history == before


def _constant_forecast(
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
            useful_life_ends_on=date(2035, 1, 1),
        ),
        covered_from=covered_from,
        covered_until=covered_until,
        history=history,
        requested_free_amount=requested_free_amount,
    )


def test_a_later_claim_still_refuses_a_method_that_follows_the_pending_value() -> None:
    operations = ActivityAssetOperations(
        repository=MemoryRepository(),
        ledger=MemoryLedger(_ACQUISITION),
        forecast_operation=_constant_forecast,
        taxpayer_modality=lambda: DirectEstimationRegime.SIMPLIFIED,
        register_authority=memory_register_authority(today=date(2031, 12, 31)),
    )
    operations.create(_revision(method=AmortizationMethod.CONSTANT_PERCENTAGE), _NAME)
    operations.record_claim(_full_year(operations, 2027), creating_operation="test.2027")

    with pytest.raises(ActividadAssetUnsupportedError, match="earlier_year_depends_on_pending_value"):
        _full_year(operations, 2025)


def test_the_last_admitted_year_takes_a_claim_and_the_next_is_refused_with_its_reason() -> None:
    operations, repository = _bounded(2026)
    operations.create(_revision(), _NAME)
    assert operations.record_claim(
        _full_year(operations, 2026), creating_operation="test.2026"
    ).claim.amount == Decimal("520.00")
    before = repository.history
    beyond = _full_year(operations, 2027)

    with pytest.raises(ActividadAssetUnsupportedError, match="claim_year_beyond_registry") as refused:
        operations.record_claim(beyond, creating_operation="test.2027")

    assert refused.value.context == {"tax_year": 2027, "last_admitted_year": 2026}
    assert beyond.amount == Decimal("520.00")
    assert repository.history == before


def test_the_list_offers_admitted_years_and_marks_later_ones_as_projection() -> None:
    operations, _ = _bounded(2026)
    operations.create(_revision(), _NAME)

    (row,) = operations.list_elements()
    plan = {item.tax_year: item for item in operations.plan(_ASSET)}

    assert row.years == (2025, 2026)
    assert row.projected_years == (2027, 2028, 2029)
    assert plan[2027].edition is not None
    assert plan[2027].edition.projected is True


def test_an_identical_create_retry_returns_the_recorded_history() -> None:
    operations, repository = _operations()
    operations.create(_revision(), _NAME)
    before = repository.history

    assert operations.create(_revision(), _NAME) == before
    assert repository.history == before


@pytest.mark.parametrize(
    ("revision_basis", "descriptor"),
    [
        ("2100", _NAME),
        ("2000", ActivityAssetDescriptorFacts(name="Another name")),
    ],
)
def test_a_differing_create_retry_is_refused(revision_basis: str, descriptor: ActivityAssetDescriptorFacts) -> None:
    operations, repository = _operations()
    operations.create(_revision(), _NAME)
    before = repository.history

    with pytest.raises(ActividadAssetValidationError, match="asset_already_exists"):
        operations.create(_revision(basis=revision_basis), descriptor)

    assert repository.history == before


def test_a_replayed_effective_claim_is_reused() -> None:
    operations, repository = _operations()
    operations.create(_revision(), _NAME)
    charge = _full_year(operations, 2025)
    first = operations.record_claim(charge, creating_operation="test.claim")
    before = repository.history

    again = operations.record_claim(charge, creating_operation="test.claim")

    assert again.reused_existing_claim is True
    assert again.claim == first.claim
    assert repository.history == before


def test_a_replayed_superseded_claim_is_refused_and_never_reported_as_reused() -> None:
    operations, repository = _operations()
    operations.create(_revision(), _NAME)
    charge = _full_year(operations, 2025)
    first = operations.record_claim(charge, creating_operation="test.claim").claim
    operations.record_claim(
        operations.forecast(
            asset_id=_ASSET,
            covered_from=date(2025, 1, 1),
            covered_until=date(2026, 1, 1),
            supersedes_claim_id=first.claim_id,
        ),
        creating_operation="test.replacement",
        supersedes_claim_id=first.claim_id,
    )
    before = repository.history

    with pytest.raises(ActividadAssetClaimConflictError, match="claim_superseded_replay"):
        operations.record_claim(charge, creating_operation="test.claim")

    assert repository.history == before


def test_a_useful_life_ending_on_entry_gives_no_minimum_rather_than_dividing_by_zero() -> None:
    revision = _revision()

    assert (
        year_minimum(
            revision,
            tax_year=2025,
            boundary=date(2026, 1, 1),
            bounds=ActivityAssetDisposalBounds(useful_life_ends_on=revision.in_service_date),
        )
        is None
    )


def test_a_zero_baja_claim_accrues_nothing_in_modelo_130() -> None:
    repository = MemoryRepository()
    operations = ActivityAssetOperations(
        repository=repository,
        ledger=MemoryLedger(_ACQUISITION),
        forecast_operation=_low_value_forecast,
        taxpayer_modality=lambda: DirectEstimationRegime.SIMPLIFIED,
        register_authority=memory_register_authority(today=date(2026, 12, 31)),
    )
    operations.create(_low_value_revision(), _NAME)
    elected = operations.forecast(
        asset_id=_ASSET,
        covered_from=date(2025, 7, 1),
        covered_until=date(2026, 1, 1),
        requested_free_amount=Decimal("180.00"),
    )
    operations.record_claim(elected, creating_operation="test.free")
    operations.dispose(_ASSET, _sale(date(2025, 3, 31)))

    handoff = operations.filing_handoff(tax_year=2025, m130_period=Period.from_year_and_code(2025, "4T"))

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
    operations, repository = _operations(today=date(2026, 12, 31))
    operations.create(_revision(in_service=date(2025, 1, 1)), _NAME)
    before = repository.history

    with pytest.raises(ActividadAssetValidationError, match="later_affectation_out_of_order"):
        operations.dispose(_ASSET, _sale(later_affectation_on=date(2025, 1, 2)))

    assert repository.history == before


@pytest.mark.parametrize("affected", [date(2024, 6, 1), date(2025, 1, 1)])
def test_a_later_affectation_up_to_entry_into_service_is_admitted(affected: date) -> None:
    operations, _ = _operations(today=date(2026, 12, 31))
    operations.create(_revision(in_service=date(2025, 1, 1)), _NAME)

    after = operations.dispose(_ASSET, _sale(later_affectation_on=affected))

    assert after.revisions[-1].disposal is not None
    assert after.revisions[-1].disposal.later_affectation_on == affected
