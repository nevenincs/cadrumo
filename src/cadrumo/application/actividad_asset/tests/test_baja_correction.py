"""Removing or redating a baja keeps every deduction it had zeroed.

Figures use 2,000.00 at 26% linear from 1 January of the first year: 520.00 a full year.  A baja on
30 June of the second year keeps its elapsed days of that year, 520 x days / days in the year, and
zeroes the third year.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from cadrumo.application.actividad_asset.activity_asset_read_models import ActivityAssetClaimState
from cadrumo.application.actividad_asset.history import ActivityAssetHistory
from cadrumo.application.actividad_asset.operations import ActivityAssetOperations
from cadrumo.application.actividad_asset.schedule_walk import walk_element
from cadrumo.domain.contribuyente.tax_residence import ResidenceTerritory
from cadrumo.domain.renta.actividad_asset.claims import effective_claims, project_m100
from cadrumo.domain.renta.actividad_asset.disposal import ActivityAssetDisposal, ActivityAssetDisposalReason
from cadrumo.domain.renta.actividad_asset.election import (
    AcquiredCondition,
    ActivityAssetAmortizationElection,
    AmortizationMethod,
    DirectEstimationRegime,
    LowValueElection,
)
from cadrumo.domain.renta.actividad_asset.errors import ActividadAssetValidationError
from cadrumo.domain.renta.actividad_asset.lifecycle import ActivityAssetRevision, AssetKind
from cadrumo.domain.renta.actividad_asset.schedule import (
    AssetScheduleHistory,
    ScheduleAuthority,
    ScheduledAmortizationCharge,
    schedule_charge,
)

from .ledger_support import MemoryLedger
from .register_support import MemoryRepository, accrued_through, memory_register_authority
from .test_register import ACQUISITION, NAME, full_year, register_forecast, register_operations, register_revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

ASSET = "laptop-1"
_FIRST = register_revision().in_service_date.year
_FULL_YEAR = Decimal("520.00")
_KEPT = accrued_through(_FULL_YEAR, date(_FIRST + 1, 7, 1))
_REST = _FULL_YEAR - _KEPT


def sale(on: date) -> ActivityAssetDisposal:
    return ActivityAssetDisposal(
        disposal_date=on,
        reason=ActivityAssetDisposalReason.SALE,
        proceeds=Decimal("1000.00"),
        transmission_costs=Decimal("0.00"),
    )


def disposed(
    on: date = date(_FIRST + 1, 6, 30),
) -> tuple[ActivityAssetOperations, MemoryRepository, ActivityAssetRevision]:
    operations, repository = register_operations(today=date(_FIRST + 3, 12, 31), last_admitted_year=_FIRST + 2)
    operations.create(register_revision(), NAME)
    for year in (_FIRST, _FIRST + 1, _FIRST + 2):
        operations.record_claim(full_year(operations, year), creating_operation=f"test.{year}")
    after = operations.dispose(ASSET, sale(on))
    return operations, repository, after.revisions[-1]


def _effective_by_year(repository: MemoryRepository) -> dict[int, Decimal]:
    return {claim.tax_year: claim.amount for claim in effective_claims(repository.history.claims)}


def baja_correction_without_baja(baja: ActivityAssetRevision) -> ActivityAssetRevision:
    return register_revision(number=baja.revision_number + 1, supersedes=baja.revision_id)


def test_removing_a_baja_restores_the_year_it_zeroed_in_one_write(monkeypatch: pytest.MonkeyPatch) -> None:
    operations, repository, baja = disposed()
    applied: list[object] = []
    apply = repository.apply

    def counted(mutation: Callable[[ActivityAssetHistory], ActivityAssetHistory]) -> ActivityAssetHistory:
        applied.append(mutation)
        return apply(mutation)

    monkeypatch.setattr(repository, "apply", counted)

    after = operations.correct(baja_correction_without_baja(baja), origin="test.correct")

    assert len(applied) == 1
    assert after.revisions[-1].disposal is None
    assert _effective_by_year(repository) == {
        _FIRST: Decimal("520.00"),
        _FIRST + 1: _KEPT,
        _FIRST + 2: Decimal("520.00"),
    }
    assert project_m100(
        after.claims, asset_kind=AssetKind.MATERIAL, tax_year=_FIRST + 2, target_casilla_id="0208"
    ).amount == Decimal("520.00")
    restored = next(claim for claim in effective_claims(after.claims) if claim.tax_year == _FIRST + 2)
    assert restored.disposal_revision_id is None
    assert restored.asset_revision_id == after.revisions[-1].revision_id


def test_the_shortened_year_reads_as_a_gap_after_the_baja_is_removed() -> None:
    operations, repository, baja = disposed()

    operations.correct(baja_correction_without_baja(baja))

    row = {item.tax_year: item for item in operations.plan(ASSET)}[_FIRST + 1]
    assert row.claim_state is ActivityAssetClaimState.PARTIAL
    assert row.claimable_intervals[0].covered_from == date(_FIRST + 1, 7, 1)
    # The rest of the year charges the full year less what the baja kept.
    rest = operations.forecast(
        asset_id=ASSET, covered_from=date(_FIRST + 1, 7, 1), covered_until=date(_FIRST + 2, 1, 1)
    )
    assert rest.amount == _REST
    assert operations.record_claim(rest, creating_operation="test.rest").claim.amount == _REST
    assert _effective_by_year(repository)[_FIRST] == Decimal("520.00")


def test_claiming_the_remainder_after_the_baja_is_removed_completes_the_year_at_the_full_charge() -> None:
    operations, repository, baja = disposed()
    operations.correct(baja_correction_without_baja(baja))
    rest = operations.forecast(
        asset_id=ASSET, covered_from=date(_FIRST + 1, 7, 1), covered_until=date(_FIRST + 2, 1, 1)
    )

    operations.record_claim(rest, creating_operation="test.rest")

    year = [claim for claim in effective_claims(repository.history.claims) if claim.tax_year == _FIRST + 1]
    assert sorted(claim.amount for claim in year) == sorted([_KEPT, _REST])
    assert sum((claim.amount for claim in year), Decimal("0")) == Decimal("520.00")
    row = {item.tax_year: item for item in operations.plan(ASSET)}[_FIRST + 1]
    assert row.claim_state is ActivityAssetClaimState.SUPERSEDED
    assert row.claimable_intervals == ()


def test_redating_a_baja_later_restores_a_zeroed_year_now_inside_service() -> None:
    operations, repository, baja = disposed()

    operations.correct(baja.with_disposal(sale(date(_FIRST + 3, 6, 30))))

    assert _effective_by_year(repository)[_FIRST + 2] == Decimal("520.00")


def test_redating_a_baja_into_a_zeroed_year_charges_up_to_the_new_boundary() -> None:
    operations, repository, baja = disposed()

    after = operations.correct(baja.with_disposal(sale(date(_FIRST + 2, 6, 30))))

    assert _effective_by_year(repository)[_FIRST + 2] == accrued_through(_FULL_YEAR, date(_FIRST + 2, 7, 1))
    last = next(claim for claim in effective_claims(after.claims) if claim.tax_year == _FIRST + 2)
    assert last.covered_until == date(_FIRST + 2, 7, 1)
    assert last.disposal_revision_id == after.revisions[-1].revision_id


def test_redating_a_baja_earlier_zeroes_what_now_lies_after_it() -> None:
    operations, repository, baja = disposed()

    operations.correct(baja.with_disposal(sale(date(_FIRST, 12, 31))))

    assert _effective_by_year(repository) == {
        _FIRST: Decimal("520.00"),
        _FIRST + 1: Decimal("0.00"),
        _FIRST + 2: Decimal("0.00"),
    }


def test_a_correction_that_keeps_the_baja_touches_no_claim() -> None:
    operations, repository, baja = disposed()
    before = _effective_by_year(repository)
    corrected = baja.model_copy(
        update={"revision_number": baja.revision_number + 1, "supersedes_revision_id": baja.revision_id}
    )

    after = operations.correct(type(corrected).model_validate(corrected.model_dump()))

    assert after.revisions[-1].disposal == baja.disposal
    assert _effective_by_year(repository) == before


def test_removing_a_baja_is_refused_for_a_foral_resident_and_writes_nothing() -> None:
    operations, repository, baja = disposed()
    before = repository.history
    foral = ActivityAssetOperations(
        repository=repository,
        ledger=MemoryLedger(ACQUISITION),
        forecast_operation=register_forecast,
        taxpayer_modality=lambda: DirectEstimationRegime.SIMPLIFIED,
        register_authority=replace(
            memory_register_authority(today=date(_FIRST + 3, 12, 31)),
            residence_territory=lambda _on: ResidenceTerritory.FORAL,
        ),
    )

    with pytest.raises(ActividadAssetValidationError, match="foral_territory"):
        foral.correct(baja_correction_without_baja(baja))

    assert repository.history == before
    assert operations.plan(ASSET)


def low_value_revision(*, number: int = 1, supersedes: str | None = None) -> ActivityAssetRevision:
    base = register_revision(number=number, supersedes=supersedes, basis="250", method=AmortizationMethod.LINEAR)
    facts = {name: getattr(base, name) for name in type(base).model_fields}
    facts["acquired_condition"] = AcquiredCondition.NEW
    facts["amortization"] = ActivityAssetAmortizationElection(
        regime=DirectEstimationRegime.SIMPLIFIED,
        method=AmortizationMethod.LOW_VALUE_FREE,
        low_value=LowValueElection(
            election_reference="election-1",
            new_material_evidence_reference="new-material-1",
        ),
    )
    return ActivityAssetRevision(**facts)


def low_value_forecast(
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
            low_value=revision.amortization.low_value,
            free_depreciation_unit_threshold=Decimal("300.00"),
            free_depreciation_annual_cap=Decimal("25000.00"),
            authority_generation="free-test",
            source_reference="free test table",
        ),
        covered_from=covered_from,
        covered_until=covered_until,
        history=history,
        requested_free_amount=requested_free_amount,
    )


def test_removing_a_baja_restores_a_free_amount_as_the_taxpayer_elected_it() -> None:
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
        asset_id=ASSET,
        covered_from=date(_FIRST, 7, 1),
        covered_until=date(_FIRST + 1, 1, 1),
        requested_free_amount=Decimal("180.00"),
    )
    operations.record_claim(elected, creating_operation="test.free")
    baja = operations.dispose(ASSET, sale(date(_FIRST, 3, 31))).revisions[-1]
    assert _effective_by_year(repository) == {_FIRST: Decimal("0.00")}

    operations.correct(low_value_revision(number=baja.revision_number + 1, supersedes=baja.revision_id))

    assert _effective_by_year(repository) == {_FIRST: Decimal("180.00")}


def test_a_walk_after_removal_shows_the_claim_against_its_charge() -> None:
    operations, repository, baja = disposed()

    operations.correct(baja_correction_without_baja(baja))

    rows = {
        row.tax_year: row
        for row in walk_element(
            repository.history.revisions[-1],
            repository.history,
            forecast=register_forecast,
            through_year=_FIRST + 2,
        )
    }
    assert rows[_FIRST + 2].claimed == Decimal("520.00")
    assert rows[_FIRST + 2].gaps == ()
