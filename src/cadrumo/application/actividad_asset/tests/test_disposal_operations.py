"""A baja through the register: one write, claim supersession, refusals, reads and its calculation.

Figures are hand-worked from the 26% linear charge on a 2,000.00 basis in service from
1 January of the first year that the register tests use: 520.00 a full year.  A baja on 30 June of
the second year ends service at 1 July, so the days of that year up to it remain: 520 x days / days
in the year.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from cadrumo.application.actividad_asset.activity_asset_read_models import ActivityAssetRegisterState
from cadrumo.application.actividad_asset.disposal_calculation import project_disposal_calculation
from cadrumo.application.actividad_asset.history import ActivityAssetHistory
from cadrumo.application.actividad_asset.operations import ActivityAssetOperations
from cadrumo.domain.contribuyente.tax_residence import ResidenceTerritory
from cadrumo.domain.renta.actividad_asset.claims import AmortizationClaim, effective_claims
from cadrumo.domain.renta.actividad_asset.disposal import ActivityAssetDisposal, ActivityAssetDisposalReason
from cadrumo.domain.renta.actividad_asset.election import DirectEstimationRegime
from cadrumo.domain.renta.actividad_asset.errors import (
    ActividadAssetClaimConflictError,
    ActividadAssetIncompleteError,
    ActividadAssetValidationError,
)
from cadrumo.domain.renta.actividad_asset.lifecycle import OpeningAmortizationHistory, OpeningHistoryStatus
from cadrumo.domain.renta.actividad_asset.register_records import ActivityAssetEventKind

from .ledger_support import MemoryLedger
from .register_support import MemoryRepository, accrued_through, memory_register_authority
from .test_register import ACQUISITION, NAME, full_year, register_forecast, register_operations, register_revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_FIRST = register_revision().in_service_date.year

_AFTER_ALL = date(_FIRST + 3, 1, 1)
_AT = datetime(_FIRST + 1, 7, 1, 9, 0, tzinfo=UTC)
_ASSET = "laptop-1"


def _sale(
    on: date = date(_FIRST + 1, 6, 30), proceeds: str = "2000.00", costs: str = "100.00"
) -> ActivityAssetDisposal:
    return ActivityAssetDisposal(
        disposal_date=on,
        reason=ActivityAssetDisposalReason.SALE,
        proceeds=Decimal(proceeds),
        transmission_costs=Decimal(costs),
    )


def _claimed_through(last_year: int) -> tuple[ActivityAssetOperations, MemoryRepository]:
    operations, repository = register_operations(today=_AFTER_ALL, last_admitted_year=last_year)
    operations.create(register_revision(), NAME)
    for year in range(_FIRST, last_year + 1):
        operations.record_claim(full_year(operations, year), creating_operation="test.claim")
    return operations, repository


def test_a_baja_shortens_the_crossing_claim_and_zeroes_a_later_one_in_one_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    operations, repository = _claimed_through(_FIRST + 2)
    applied: list[ActivityAssetHistory] = []
    apply = repository.apply

    def counted(mutation: Callable[[ActivityAssetHistory], ActivityAssetHistory]) -> ActivityAssetHistory:
        applied.append(apply(mutation))
        return applied[-1]

    monkeypatch.setattr(repository, "apply", counted)

    after = operations.dispose(_ASSET, _sale(), recorded_at=_AT, origin="test.dispose")

    assert applied == [after]
    revision = after.revisions[-1]
    assert revision.out_of_service_date == date(_FIRST + 1, 7, 1)
    effective = {claim.tax_year: claim for claim in effective_claims(after.claims)}
    assert effective[_FIRST].amount == Decimal("520.00")
    assert effective[_FIRST + 1].amount == accrued_through(Decimal("520.00"), date(_FIRST + 1, 7, 1))
    assert effective[_FIRST + 1].covered_until == date(_FIRST + 1, 7, 1)
    assert effective[_FIRST + 2].amount == Decimal("0.00")
    assert effective[_FIRST + 2].disposal_revision_id == revision.revision_id
    assert after.events[-3].kind is ActivityAssetEventKind.BAJA


def test_an_identical_baja_retry_returns_the_recorded_history() -> None:
    operations, repository = _claimed_through(_FIRST + 1)
    operations.dispose(_ASSET, _sale())
    before = repository.history

    assert operations.dispose(_ASSET, _sale()) == before
    assert repository.history == before


def test_a_differing_second_baja_is_refused() -> None:
    operations, repository = _claimed_through(_FIRST + 1)
    recorded = _sale()
    operations.dispose(_ASSET, recorded)
    before = repository.history

    with pytest.raises(ActividadAssetClaimConflictError, match="disposal_already_recorded"):
        operations.dispose(_ASSET, recorded.model_copy(update={"proceeds": recorded.proceeds + Decimal("1.00")}))

    assert repository.history == before


def test_a_new_charge_past_the_boundary_is_refused() -> None:
    operations, repository = _claimed_through(_FIRST)
    forecast = full_year(operations, _FIRST + 1)
    after = operations.dispose(_ASSET, _sale())
    claim = AmortizationClaim.from_schedule(
        forecast,
        asset_kind=after.revisions[-1].asset_kind,
        creating_operation="test.claim",
    ).model_copy(
        update={"asset_revision_id": after.revisions[-1].revision_id},
    )

    with pytest.raises(ActividadAssetClaimConflictError, match="disposal_claim_past_boundary"):
        after.record_claim(type(claim).model_validate(claim.model_dump(exclude={"claim_id"})))

    assert repository.history == after


def test_a_foral_resident_is_refused_by_the_existing_refusal() -> None:
    repository = MemoryRepository()
    operations = ActivityAssetOperations(
        repository=repository,
        ledger=MemoryLedger(ACQUISITION),
        forecast_operation=register_forecast,
        taxpayer_modality=lambda: DirectEstimationRegime.SIMPLIFIED,
        register_authority=memory_register_authority(territory=ResidenceTerritory.FORAL),
    )
    operations.create(register_revision(), NAME)

    with pytest.raises(ActividadAssetValidationError, match="foral_territory"):
        operations.dispose(_ASSET, _sale())
    with pytest.raises(ActividadAssetValidationError, match="foral_territory"):
        operations.disposal_calculation(_ASSET, _sale())


def test_a_missing_claim_never_refuses_and_the_figures_use_the_minimum() -> None:
    operations, _ = _claimed_through(_FIRST)
    operations.dispose(_ASSET, _sale())

    _, calculation = operations.disposal_calculation(_ASSET)

    # The second year has no charge: only 520.00 was deducted, above the table's 10% minimum:
    # 200.00 + 2,000 x 10% x elapsed days / days in the year stays below it, so the reduction stays 520.00.
    assert calculation.deducted == Decimal("520.00")
    assert calculation.reduction == Decimal("520.00")
    assert calculation.net_value == Decimal("1480.00")
    # 2,000.00 less 100.00 of costs, less the net value 1,480.00.
    assert calculation.result == Decimal("420.00")
    assert [finding.kind.value for finding in calculation.findings] == ["claim_gap", "exemption_not_computed"]

    view = project_disposal_calculation(_sale(), calculation)

    assert [finding.label_key for finding in view.findings] == [
        "ledger.actividad_asset.disposal_finding.claim_gap",
        "ledger.actividad_asset.disposal_finding.exemption_not_computed",
    ]
    assert [finding.kind for finding in view.findings] == [finding.kind for finding in calculation.findings]
    assert [finding.tax_year for finding in view.findings] == [_FIRST + 1, None]
    assert all(finding.effect_on_cost is None for finding in view.findings)


def test_a_preview_writes_nothing_and_sees_the_shortened_charge() -> None:
    operations, repository = _claimed_through(_FIRST + 1)
    before = repository.history

    _, calculation = operations.disposal_calculation(_ASSET, _sale())

    assert repository.history == before
    # The full first year plus the second year's charge as the baja would leave it.
    deducted = Decimal("520.00") + accrued_through(Decimal("520.00"), date(_FIRST + 1, 7, 1))
    assert calculation.deducted == deducted
    # Proceeds 2,000.00 less costs 100.00, less the net value: the 2,000.00 basis less what was deducted.
    assert calculation.result == Decimal("2000.00") - Decimal("100.00") - (Decimal("2000.00") - deducted)


def test_a_preview_or_read_with_no_baja_stated_is_refused() -> None:
    operations, _ = _claimed_through(_FIRST)

    with pytest.raises(ActividadAssetValidationError, match="disposal_not_recorded"):
        operations.disposal_calculation(_ASSET)


def test_a_missing_opening_history_allows_the_baja_but_not_its_figures() -> None:
    operations, _ = register_operations(today=_AFTER_ALL)
    unknown = register_revision().model_copy(
        update={"opening_history": OpeningAmortizationHistory(status=OpeningHistoryStatus.MISSING)},
    )
    operations.create(type(unknown).model_validate(unknown.model_dump()), NAME)

    operations.dispose(_ASSET, _sale())

    with pytest.raises(ActividadAssetIncompleteError, match="opening_history_missing"):
        operations.disposal_calculation(_ASSET)


def test_a_withdrawal_computes_no_gain() -> None:
    operations, _ = _claimed_through(_FIRST)
    withdrawal = ActivityAssetDisposal(
        disposal_date=date(_FIRST + 1, 6, 30),
        reason=ActivityAssetDisposalReason.WITHDRAWAL,
        proceeds=Decimal("0.00"),
        transmission_costs=Decimal("0.00"),
    )
    operations.dispose(_ASSET, withdrawal)

    _, calculation = operations.disposal_calculation(_ASSET)

    assert calculation.result is None
    assert calculation.net_value == Decimal("1480.00")


def test_the_reads_show_the_baja_on_the_row_the_timeline_and_the_plan() -> None:
    operations, _ = _claimed_through(_FIRST)
    operations.dispose(_ASSET, _sale(), recorded_at=_AT)

    assert operations.list_elements()[0].state is ActivityAssetRegisterState.OUT_OF_SERVICE
    baja = [event for event in operations.timeline(_ASSET) if event.kind is ActivityAssetEventKind.BAJA]
    assert [event.effect_date for event in baja] == [date(_FIRST + 1, 6, 30)]
    plan = operations.plan(_ASSET)
    assert plan[-1].tax_year == _FIRST + 1
