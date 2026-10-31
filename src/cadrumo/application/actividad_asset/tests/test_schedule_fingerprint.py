"""A schedule fingerprint moves with what a charge rests on, and with nothing else.

Figures use the register tests' element: 2,000.00 at 26% linear from 1 January 2025.
A full year charges 520.00.  With 1,800.00 claimed before 2028 only 200.00 remains.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from cadrumo.application.actividad_asset.activity_asset_read_models import ActivityAssetClaimStaleReason
from cadrumo.application.actividad_asset.operations import ActivityAssetOperations
from cadrumo.domain.renta.actividad_asset.claims import AmortizationClaim, record_claim
from cadrumo.domain.renta.actividad_asset.disposal import ActivityAssetDisposal, ActivityAssetDisposalReason
from cadrumo.domain.renta.actividad_asset.election import AmortizationMethod, DirectEstimationRegime
from cadrumo.domain.renta.actividad_asset.register_records import ActivityAssetEventKind
from cadrumo.domain.renta.actividad_asset.schedule import (
    AssetScheduleHistory,
    ScheduleAuthority,
    ScheduledAmortizationCharge,
    schedule_charge,
)

from .ledger_support import MemoryLedger
from .register_support import MemoryRepository, memory_register_authority
from .test_register import _ACQUISITION, _NAME, _full_year, _operations, _revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ASSET = "laptop-1"


def _authority(
    tax_year: int = 2025,
    *,
    generation: str = "generation-1",
    source: str = "table entry",
    rate: str = "0.26",
    method: AmortizationMethod = AmortizationMethod.LINEAR,
) -> ScheduleAuthority:
    revision = _revision(method=method)
    constant = method is AmortizationMethod.CONSTANT_PERCENTAGE
    return ScheduleAuthority(
        tax_year=tax_year,
        asset_kind=revision.asset_kind,
        method=method,
        election_fingerprint=revision.amortization.fingerprint,
        annual_rate=Decimal(rate),
        authority_generation=generation,
        source_reference=source,
        useful_life_ends_on=date(2035, 1, 1) if constant else None,
        maximum_period_ends_on=None if constant else date(2035, 1, 1),
    )


def _charge(
    authority: ScheduleAuthority,
    *,
    before: str = "0",
    method: AmortizationMethod = AmortizationMethod.LINEAR,
) -> ScheduledAmortizationCharge:
    year = authority.tax_year
    return schedule_charge(
        _revision(method=method),
        authority,
        covered_from=date(year, 1, 1),
        covered_until=date(year + 1, 1, 1),
        history=AssetScheduleHistory(accumulated_before_tax_year=Decimal(before)),
    )


def test_a_new_generation_with_identical_law_keeps_the_fingerprint() -> None:
    first = _charge(_authority(generation="generation-1", source="table entry"))
    second = _charge(_authority(generation="generation-2", source="republished entry;another"))

    assert first.amount == second.amount == Decimal("520.00")
    assert first.schedule_fingerprint == second.schedule_fingerprint


def test_the_same_coefficient_written_at_another_scale_keeps_the_fingerprint() -> None:
    assert _authority(rate="0.26").fingerprint == _authority(rate="0.260").fingerprint


def test_a_changed_coefficient_moves_the_fingerprint() -> None:
    assert (
        _charge(_authority(rate="0.26")).schedule_fingerprint != _charge(_authority(rate="0.20")).schedule_fingerprint
    )


def test_a_prior_claim_moves_a_constant_percentage_fingerprint_with_its_figure() -> None:
    method = AmortizationMethod.CONSTANT_PERCENTAGE
    authority = _authority(2026, method=method)

    untouched = _charge(authority, method=method)
    after_prior_claim = _charge(authority, before="520.00", method=method)

    # 26% of 2,000.00, then 26% of 1,480.00.
    assert (untouched.amount, after_prior_claim.amount) == (Decimal("520.00"), Decimal("384.80"))
    assert untouched.schedule_fingerprint != after_prior_claim.schedule_fingerprint


def test_a_prior_claim_leaves_a_linear_fingerprint_until_the_cap_reaches_the_charge() -> None:
    authority = _authority(2028)

    untouched = _charge(authority)
    still_within = _charge(authority, before="1000.00")
    capped = _charge(authority, before="1800.00")
    capped_lower = _charge(authority, before="1900.00")

    assert (untouched.amount, still_within.amount) == (Decimal("520.00"), Decimal("520.00"))
    assert untouched.schedule_fingerprint == still_within.schedule_fingerprint
    assert (capped.amount, capped_lower.amount) == (Decimal("200.00"), Decimal("100.00"))
    assert len({untouched.schedule_fingerprint, capped.schedule_fingerprint, capped_lower.schedule_fingerprint}) == 3


def test_a_claim_identity_stays_exact_across_revisions_sharing_a_fingerprint() -> None:
    first = _revision()
    second = _revision(number=2, supersedes=first.revision_id)
    charge = _charge(_authority())
    claim_under_first = AmortizationClaim.from_schedule(
        charge.model_copy(update={"asset_revision_id": first.revision_id}),
        asset_kind=first.asset_kind,
        creating_operation="test",
    )
    claim_under_second = AmortizationClaim.from_schedule(
        charge.model_copy(update={"asset_revision_id": second.revision_id}),
        asset_kind=first.asset_kind,
        creating_operation="test",
    )

    assert claim_under_first.schedule_fingerprint == claim_under_second.schedule_fingerprint
    assert claim_under_first.claim_id != claim_under_second.claim_id


def test_a_held_forecast_replays_and_so_does_the_same_figure_under_a_new_generation() -> None:
    first = _charge(_authority(generation="generation-1"))
    second = _charge(_authority(generation="generation-2"))
    claim = AmortizationClaim.from_schedule(first, asset_kind=_revision().asset_kind, creating_operation="test")
    recorded = record_claim((), claim)

    replay = record_claim(
        recorded.claims,
        AmortizationClaim.from_schedule(first, asset_kind=claim.asset_kind, creating_operation="test"),
    )

    assert replay.reused_existing_claim is True
    assert replay.claim.claim_id == claim.claim_id
    assert first.schedule_fingerprint == second.schedule_fingerprint
    newer = record_claim(
        recorded.claims,
        AmortizationClaim.from_schedule(second, asset_kind=claim.asset_kind, creating_operation="test"),
    )
    assert newer.reused_existing_claim is True
    assert newer.claim.claim_id == claim.claim_id


def _operations_under_generation(
    repository: MemoryRepository,
    generation: str,
) -> ActivityAssetOperations:
    def forecast(
        revision,
        *,
        covered_from: date,
        covered_until: date,
        history: AssetScheduleHistory,
        requested_free_amount: Decimal | None = None,
    ) -> ScheduledAmortizationCharge:
        return schedule_charge(
            revision,
            _authority(covered_from.year, generation=generation),
            covered_from=covered_from,
            covered_until=covered_until,
            history=history,
            requested_free_amount=requested_free_amount,
        )

    return ActivityAssetOperations(
        repository=repository,
        ledger=MemoryLedger(_ACQUISITION),
        forecast_operation=forecast,
        taxpayer_modality=lambda: DirectEstimationRegime.SIMPLIFIED,
        register_authority=replace(memory_register_authority(today=date(2026, 12, 31))),
    )


def test_a_claim_stays_current_under_a_new_generation_of_identical_law() -> None:
    repository = MemoryRepository()
    operations = _operations_under_generation(repository, "generation-1")
    operations.create(_revision(), _NAME)
    operations.record_claim(_full_year(operations, 2025), creating_operation="test.claim")

    reread = _operations_under_generation(repository, "generation-2")

    claim_event = next(event for event in reread.timeline(_ASSET) if event.kind is ActivityAssetEventKind.CLAIM)
    assert claim_event.claim is not None
    assert claim_event.claim.matches_current_schedule is True
    assert reread.list_elements()[0].findings.stale == 0


def test_a_claim_whose_later_interval_rests_on_earlier_claims_reads_current() -> None:
    operations, _ = _operations(today=date(2026, 12, 31))
    operations.create(_revision(method=AmortizationMethod.LINEAR), _NAME)
    operations.record_claim(_full_year(operations, 2025), creating_operation="test.2025")
    operations.record_claim(_full_year(operations, 2026), creating_operation="test.2026")

    assert operations.list_elements()[0].findings.stale == 0


def test_a_disposal_only_revision_leaves_earlier_claims_current() -> None:
    operations, _ = _operations(today=date(2026, 12, 31))
    operations.create(_revision(), _NAME)
    operations.record_claim(_full_year(operations, 2025), creating_operation="test.claim")

    operations.dispose(
        _ASSET,
        ActivityAssetDisposal(
            disposal_date=date(2026, 6, 30),
            reason=ActivityAssetDisposalReason.SALE,
            proceeds=Decimal("1000.00"),
            transmission_costs=Decimal("0.00"),
        ),
    )

    claim_event = next(event for event in operations.timeline(_ASSET) if event.kind is ActivityAssetEventKind.CLAIM)
    assert claim_event.claim is not None
    assert claim_event.claim.stale_reason is None
    assert operations.list_elements()[0].findings.stale == 0


def test_a_correction_changing_a_tax_fact_still_reads_as_a_changed_revision() -> None:
    operations, _ = _operations(today=date(2026, 12, 31))
    first = _revision()
    operations.create(first, _NAME)
    operations.record_claim(_full_year(operations, 2025), creating_operation="test.claim")

    operations.correct(_revision(number=2, supersedes=first.revision_id, basis="1000"))

    claim_event = next(event for event in operations.timeline(_ASSET) if event.kind is ActivityAssetEventKind.CLAIM)
    assert claim_event.claim is not None
    assert claim_event.claim.stale_reason is ActivityAssetClaimStaleReason.REVISION_CHANGED
