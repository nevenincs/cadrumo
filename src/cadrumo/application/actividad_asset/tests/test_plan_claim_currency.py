"""A plan claim says whether it still matches the current schedule, by the rule the timeline uses."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from cadrumo.application.actividad_asset.activity_asset_read_models import (
    ActivityAssetClaimStaleReason,
    ActivityAssetPlanClaim,
)
from cadrumo.application.actividad_asset.operations import ActivityAssetOperations
from cadrumo.domain.renta.actividad_asset.election import DirectEstimationRegime
from cadrumo.domain.renta.actividad_asset.errors import ActividadAssetUnsupportedError
from cadrumo.domain.renta.actividad_asset.lifecycle import ActivityAssetRevision
from cadrumo.domain.renta.actividad_asset.register_records import ActivityAssetDescriptorFacts, ActivityAssetEventKind
from cadrumo.domain.renta.actividad_asset.schedule import (
    AssetScheduleHistory,
    ScheduleAuthority,
    ScheduledAmortizationCharge,
    schedule_charge,
)

from .ledger_support import MemoryLedger, acquisition_transaction
from .register_support import MemoryRepository, memory_register_authority
from .test_filing_handoff_without_period import _operations, _revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _recorded_claim(operations: ActivityAssetOperations, *, year: int = 2025) -> str:
    return operations.record_claim(
        operations.forecast(asset_id="laptop-1", covered_from=date(year, 1, 1), covered_until=date(year + 1, 1, 1)),
        creating_operation="test.plan-claim",
    ).claim.claim_id


def _plan_claim(operations: ActivityAssetOperations, claim_id: str) -> ActivityAssetPlanClaim:
    return next(claim for row in operations.plan("laptop-1") for claim in row.claims if claim.claim_id == claim_id)


def _timeline_use(
    operations: ActivityAssetOperations, claim_id: str
) -> tuple[bool, ActivityAssetClaimStaleReason | None]:
    event = next(
        event
        for event in operations.timeline("laptop-1")
        if event.kind is ActivityAssetEventKind.CLAIM and event.record_id == claim_id
    )
    assert event.claim is not None
    return event.claim.matches_current_schedule, event.claim.stale_reason


def test_a_claim_under_the_current_schedule_matches_it() -> None:
    operations = _operations()
    claim_id = _recorded_claim(operations)

    claim = _plan_claim(operations, claim_id)

    assert claim.matches_current_schedule is True
    assert claim.stale_reason is None
    assert (claim.matches_current_schedule, claim.stale_reason) == _timeline_use(operations, claim_id)


def test_a_claim_recorded_under_an_earlier_revision_is_stale_with_the_timelines_reason() -> None:
    operations = _operations()
    claim_id = _recorded_claim(operations)
    first = operations.inspect("laptop-1")[0]
    operations.correct(_revision(number=2, supersedes=first.revision_id, basis="1000"), origin="test.correct")

    claim = _plan_claim(operations, claim_id)

    assert claim.matches_current_schedule is False
    assert claim.stale_reason is ActivityAssetClaimStaleReason.REVISION_CHANGED
    assert (claim.matches_current_schedule, claim.stale_reason) == _timeline_use(operations, claim_id)


def test_the_plan_and_the_timeline_agree_on_every_claim_of_the_element() -> None:
    operations = _operations()
    first_year = _recorded_claim(operations, year=2025)
    second_year = _recorded_claim(operations, year=2026)
    operations.correct(
        _revision(number=2, supersedes=operations.inspect("laptop-1")[0].revision_id, basis="1500"),
        origin="test.correct",
    )

    for claim_id in (first_year, second_year):
        claim = _plan_claim(operations, claim_id)
        assert (claim.matches_current_schedule, claim.stale_reason) == _timeline_use(operations, claim_id)


def test_the_stale_reason_is_stated_exactly_when_the_claim_no_longer_matches() -> None:
    operations = _operations()
    document = _plan_claim(operations, _recorded_claim(operations)).model_dump(mode="json")

    assert ActivityAssetPlanClaim.model_validate_json(json.dumps(document)).stale_reason is None
    with pytest.raises(ValidationError, match="stale exactly when"):
        ActivityAssetPlanClaim.model_validate_json(json.dumps({**document, "stale_reason": "authority_changed"}))
    with pytest.raises(ValidationError, match="stale exactly when"):
        ActivityAssetPlanClaim.model_validate_json(json.dumps({**document, "matches_current_schedule": False}))


class _Authority:
    """A forecast whose published rate, or availability, the test moves after a claim is recorded."""

    def __init__(self) -> None:
        self.rate = Decimal("0.26")
        self.available = True

    def __call__(
        self,
        revision: ActivityAssetRevision,
        *,
        covered_from: date,
        covered_until: date,
        history: AssetScheduleHistory,
        requested_free_amount: Decimal | None = None,
    ) -> ScheduledAmortizationCharge:
        if not self.available:
            raise ActividadAssetUnsupportedError(translated_message="ledger.actividad_asset.errors.test_unavailable")
        return schedule_charge(
            revision,
            ScheduleAuthority(
                tax_year=covered_from.year,
                asset_kind=revision.asset_kind,
                method=revision.amortization.method,
                election_fingerprint=revision.amortization.fingerprint,
                annual_rate=self.rate,
                authority_generation="plan-claim-test",
                source_reference="plan claim test table",
                maximum_period_ends_on=date(2035, 1, 1),
            ),
            covered_from=covered_from,
            covered_until=covered_until,
            history=history,
            requested_free_amount=requested_free_amount,
        )


@pytest.mark.parametrize(
    ("move", "reason"),
    [
        (
            lambda authority: setattr(authority, "rate", Decimal("0.25")),
            ActivityAssetClaimStaleReason.AUTHORITY_CHANGED,
        ),
        (lambda authority: setattr(authority, "available", False), ActivityAssetClaimStaleReason.SCHEDULE_UNAVAILABLE),
    ],
)
def test_a_moved_authority_makes_the_claim_stale_for_the_plan_as_for_the_timeline(
    move: Callable[[_Authority], None], reason: ActivityAssetClaimStaleReason
) -> None:
    authority = _Authority()
    operations = ActivityAssetOperations(
        repository=MemoryRepository(),
        ledger=MemoryLedger(acquisition_transaction()),
        forecast_operation=authority,
        taxpayer_modality=lambda: DirectEstimationRegime.SIMPLIFIED,
        register_authority=memory_register_authority(),
    )
    operations.create(_revision(), ActivityAssetDescriptorFacts(name="Office laptop"))
    claim_id = _recorded_claim(operations)

    move(authority)

    claim = _plan_claim(operations, claim_id)
    assert (claim.matches_current_schedule, claim.stale_reason) == (False, reason)
    assert (claim.matches_current_schedule, claim.stale_reason) == _timeline_use(operations, claim_id)
