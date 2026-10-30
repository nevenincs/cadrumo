"""Removing or redating a baja keeps every deduction it had zeroed.

Figures use 2,000.00 at 26% linear from 1 January 2025: 520.00 a full year.  A baja on
30 June 2026 keeps 181 of 365 days of that year: 520 x 181 / 365 = 257.86, and zeroes 2027.
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
from .register_support import MemoryRepository, memory_register_authority
from .test_register import _ACQUISITION, _NAME, _forecast, _full_year, _operations, _revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ASSET = "laptop-1"


def _sale(on: date) -> ActivityAssetDisposal:
    return ActivityAssetDisposal(
        disposal_date=on,
        reason=ActivityAssetDisposalReason.SALE,
        proceeds=Decimal("1000.00"),
        transmission_costs=Decimal("0.00"),
    )


def _disposed(on: date = date(2026, 6, 30)) -> tuple[ActivityAssetOperations, MemoryRepository, ActivityAssetRevision]:
    operations, repository = _operations(today=date(2028, 12, 31))
    operations.create(_revision(), _NAME)
    for year in (2025, 2026, 2027):
        operations.record_claim(_full_year(operations, year), creating_operation=f"test.{year}")
    after = operations.dispose(_ASSET, _sale(on))
    return operations, repository, after.revisions[-1]


def _effective_by_year(repository: MemoryRepository) -> dict[int, Decimal]:
    return {claim.tax_year: claim.amount for claim in effective_claims(repository.history.claims)}


def _without_baja(baja: ActivityAssetRevision) -> ActivityAssetRevision:
    return _revision(number=baja.revision_number + 1, supersedes=baja.revision_id)


def test_removing_a_baja_restores_the_year_it_zeroed_in_one_write(monkeypatch: pytest.MonkeyPatch) -> None:
    operations, repository, baja = _disposed()
    applied: list[object] = []
    apply = repository.apply

    def counted(mutation: Callable[[ActivityAssetHistory], ActivityAssetHistory]) -> ActivityAssetHistory:
        applied.append(mutation)
        return apply(mutation)

    monkeypatch.setattr(repository, "apply", counted)

    after = operations.correct(_without_baja(baja), origin="test.correct")

    assert len(applied) == 1
    assert after.revisions[-1].disposal is None
    assert _effective_by_year(repository) == {
        2025: Decimal("520.00"),
        2026: Decimal("257.86"),
        2027: Decimal("520.00"),
    }
    assert project_m100(
        after.claims, asset_kind=AssetKind.MATERIAL, tax_year=2027, target_casilla_id="0208"
    ).amount == Decimal("520.00")
    restored = next(claim for claim in effective_claims(after.claims) if claim.tax_year == 2027)
    assert restored.disposal_revision_id is None
    assert restored.asset_revision_id == after.revisions[-1].revision_id


def test_the_shortened_year_reads_as_a_gap_after_the_baja_is_removed() -> None:
    operations, repository, baja = _disposed()

    operations.correct(_without_baja(baja))

    row = {item.tax_year: item for item in operations.plan(_ASSET)}[2026]
    assert row.claim_state is ActivityAssetClaimState.PARTIAL
    assert row.claimable_intervals[0].covered_from == date(2026, 7, 1)
    # The rest of 2026 charges 520.00 - 257.86.
    rest = operations.forecast(asset_id=_ASSET, covered_from=date(2026, 7, 1), covered_until=date(2027, 1, 1))
    assert rest.amount == Decimal("262.14")
    assert operations.record_claim(rest, creating_operation="test.rest").claim.amount == Decimal("262.14")
    assert _effective_by_year(repository)[2025] == Decimal("520.00")


def test_redating_a_baja_later_restores_a_zeroed_year_now_inside_service() -> None:
    operations, repository, baja = _disposed()

    operations.correct(baja.with_disposal(_sale(date(2028, 6, 30))))

    assert _effective_by_year(repository)[2027] == Decimal("520.00")


def test_redating_a_baja_into_a_zeroed_year_charges_up_to_the_new_boundary() -> None:
    operations, repository, baja = _disposed()

    after = operations.correct(baja.with_disposal(_sale(date(2027, 6, 30))))

    assert _effective_by_year(repository)[2027] == Decimal("257.86")
    last = next(claim for claim in effective_claims(after.claims) if claim.tax_year == 2027)
    assert last.covered_until == date(2027, 7, 1)
    assert last.disposal_revision_id == after.revisions[-1].revision_id


def test_redating_a_baja_earlier_zeroes_what_now_lies_after_it() -> None:
    operations, repository, baja = _disposed()

    operations.correct(baja.with_disposal(_sale(date(2025, 12, 31))))

    assert _effective_by_year(repository) == {
        2025: Decimal("520.00"),
        2026: Decimal("0.00"),
        2027: Decimal("0.00"),
    }


def test_a_correction_that_keeps_the_baja_touches_no_claim() -> None:
    operations, repository, baja = _disposed()
    before = _effective_by_year(repository)
    corrected = baja.model_copy(
        update={"revision_number": baja.revision_number + 1, "supersedes_revision_id": baja.revision_id}
    )

    after = operations.correct(type(corrected).model_validate(corrected.model_dump()))

    assert after.revisions[-1].disposal == baja.disposal
    assert _effective_by_year(repository) == before


def test_removing_a_baja_is_refused_for_a_foral_resident_and_writes_nothing() -> None:
    operations, repository, baja = _disposed()
    before = repository.history
    foral = ActivityAssetOperations(
        repository=repository,
        ledger=MemoryLedger(_ACQUISITION),
        forecast_operation=_forecast,
        taxpayer_modality=lambda: DirectEstimationRegime.SIMPLIFIED,
        register_authority=replace(
            memory_register_authority(today=date(2028, 12, 31)),
            residence_territory=lambda _on: ResidenceTerritory.FORAL,
        ),
    )

    with pytest.raises(ActividadAssetValidationError, match="foral_territory"):
        foral.correct(_without_baja(baja))

    assert repository.history == before
    assert operations.plan(_ASSET)


def _low_value_revision(*, number: int = 1, supersedes: str | None = None) -> ActivityAssetRevision:
    base = _revision(number=number, supersedes=supersedes, basis="250", method=AmortizationMethod.LINEAR)
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


def _low_value_forecast(
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
    baja = operations.dispose(_ASSET, _sale(date(2025, 3, 31))).revisions[-1]
    assert _effective_by_year(repository) == {2025: Decimal("0.00")}

    operations.correct(_low_value_revision(number=baja.revision_number + 1, supersedes=baja.revision_id))

    assert _effective_by_year(repository) == {2025: Decimal("180.00")}


def test_a_walk_after_removal_shows_the_claim_against_its_charge() -> None:
    operations, repository, baja = _disposed()

    operations.correct(_without_baja(baja))

    rows = {
        row.tax_year: row
        for row in walk_element(
            repository.history.revisions[-1],
            repository.history,
            forecast=_forecast,
            through_year=2027,
        )
    }
    assert rows[2027].claimed == Decimal("520.00")
    assert rows[2027].gaps == ()
