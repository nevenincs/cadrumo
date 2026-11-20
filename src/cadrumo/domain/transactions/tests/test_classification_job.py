"""The classification job record: its invariants and the transitions a stored change may make."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....core.hashing import sha256_hex
from ..classification_job import (
    CLASSIFICATION_ITEM_TRANSITIONS,
    ClassificationConsentScope,
    ClassificationItemFailureCause,
    ClassificationItemState,
    ClassificationJob,
    ClassificationJobConsent,
    ClassificationJobItem,
    ClassificationJobLane,
    ClassificationJobScope,
    ClassificationJobScopeKind,
    ClassificationJobStatus,
    ClassificationProposal,
)
from ..enums import BusinessClassification
from ..errors import ClassificationJobError

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_AT = datetime(2026, 3, 2, 10, 0, tzinfo=UTC)
_LATER = _AT + timedelta(minutes=1)
_BUCKET = "7d1c3a52-0e4b-4f6a-9b21-5c8e2f1a0d47"
_LOCAL_LANE = ClassificationJobLane(
    provider_id="local", transport="http", model="synthetic-model", reads_off_host=False
)
_OFF_HOST_LANE = ClassificationJobLane(
    provider_id="hosted", transport="api", model="synthetic-hosted", effort="low", reads_off_host=True
)
_CONSENT = ClassificationJobConsent(
    scope=ClassificationConsentScope.ONCE, consent_reference="consent-synthetic-1", granted_at=_AT
)


def _movement(label: str) -> str:
    return sha256_hex(f"synthetic movement {label}".encode())


def _proposal(revision: str = "rev-1") -> ClassificationProposal:
    return ClassificationProposal(
        movement_revision_id=revision,
        classification=BusinessClassification.BUSINESS,
        confidence=Decimal("0.8"),
        provenance="llm:local-text:synthetic-model",
        proposed_at=_LATER,
    )


def _job(*labels: str, kind: ClassificationJobScopeKind = ClassificationJobScopeKind.SELECTION) -> ClassificationJob:
    return ClassificationJob.enqueue(
        bucket_id=_BUCKET,
        scope=ClassificationJobScope(kind=kind),
        movement_ids=tuple(_movement(label) for label in labels or ("a", "b")),
        lane=_LOCAL_LANE,
        consent=None,
        at=_AT,
    )


def test_an_enqueued_job_is_queued_at_revision_one_with_every_movement_pending() -> None:
    job = _job("a", "b", "c")

    assert job.revision == 1
    assert job.status is ClassificationJobStatus.QUEUED
    assert job.movement_ids == (_movement("a"), _movement("b"), _movement("c"))
    assert all(item.state is ClassificationItemState.PENDING and item.attempt == 0 for item in job.items)
    assert len(job.job_id) == 64
    assert job.job_id != _job("a").job_id


def test_a_job_names_each_movement_once_and_a_single_scope_holds_one() -> None:
    with pytest.raises(ValidationError, match="each movement once"):
        _job("a", "a")
    with pytest.raises(ValidationError, match="exactly one item"):
        _job("a", "b", kind=ClassificationJobScopeKind.SINGLE)
    assert _job("a", kind=ClassificationJobScopeKind.SINGLE).movement_ids == (_movement("a"),)


def test_a_period_scope_carries_ordered_bounds_and_no_other_scope_does() -> None:
    period = ClassificationJobScope(
        kind=ClassificationJobScopeKind.PERIOD, period_start=date(2026, 1, 1), period_end=date(2026, 3, 31)
    )
    assert period.period_end == date(2026, 3, 31)
    with pytest.raises(ValidationError, match="both bounds"):
        ClassificationJobScope(kind=ClassificationJobScopeKind.PERIOD, period_start=date(2026, 1, 1))
    with pytest.raises(ValidationError, match="end before it starts"):
        ClassificationJobScope(
            kind=ClassificationJobScopeKind.PERIOD, period_start=date(2026, 3, 1), period_end=date(2026, 1, 1)
        )
    with pytest.raises(ValidationError, match="only a period scope"):
        ClassificationJobScope(kind=ClassificationJobScopeKind.SELECTION, period_start=date(2026, 1, 1))


def test_an_off_host_lane_needs_a_consent_and_an_on_host_lane_takes_none() -> None:
    def enqueue(lane: ClassificationJobLane, consent: ClassificationJobConsent | None) -> ClassificationJob:
        return ClassificationJob.enqueue(
            bucket_id=_BUCKET,
            scope=ClassificationJobScope(kind=ClassificationJobScopeKind.SINGLE),
            movement_ids=(_movement("a"),),
            lane=lane,
            consent=consent,
            at=_AT,
        )

    assert enqueue(_OFF_HOST_LANE, _CONSENT).consent == _CONSENT
    with pytest.raises(ValidationError, match="off-host lane needs a consent"):
        enqueue(_OFF_HOST_LANE, None)
    with pytest.raises(ValidationError, match="on-host lane takes no consent"):
        enqueue(_LOCAL_LANE, _CONSENT)


def test_an_item_result_matches_its_state() -> None:
    movement = _movement("a")
    with pytest.raises(ValidationError, match="needs proposal"):
        ClassificationJobItem(movement_id=movement, state=ClassificationItemState.PROPOSED, attempt=1)
    with pytest.raises(ValidationError, match="needs failure cause"):
        ClassificationJobItem(movement_id=movement, state=ClassificationItemState.FAILED, attempt=1)
    with pytest.raises(ValidationError, match="has no proposal"):
        ClassificationJobItem(
            movement_id=movement, state=ClassificationItemState.RUNNING, attempt=1, proposal=_proposal()
        )
    with pytest.raises(ValidationError, match="run at least once"):
        ClassificationJobItem(movement_id=movement, state=ClassificationItemState.UNKNOWN, attempt=0)


def test_every_item_transition_outside_the_table_is_refused() -> None:
    running = ClassificationJobItem.pending(_movement("a")).transitioned(ClassificationItemState.RUNNING)
    samples = {
        ClassificationItemState.PENDING: ClassificationJobItem.pending(_movement("a")),
        ClassificationItemState.RUNNING: running,
        ClassificationItemState.PROPOSED: running.transitioned(ClassificationItemState.PROPOSED, proposal=_proposal()),
        ClassificationItemState.FAILED: running.transitioned(
            ClassificationItemState.FAILED, failure_cause=ClassificationItemFailureCause.INVALID_RESPONSE
        ),
        ClassificationItemState.UNKNOWN: running.transitioned(ClassificationItemState.UNKNOWN),
        ClassificationItemState.CANCELLED: running.transitioned(ClassificationItemState.CANCELLED),
        ClassificationItemState.STALE: running.transitioned(
            ClassificationItemState.PROPOSED, proposal=_proposal()
        ).transitioned(ClassificationItemState.STALE),
    }
    for source, item in samples.items():
        for target in ClassificationItemState:
            if target in CLASSIFICATION_ITEM_TRANSITIONS[source]:
                continue
            with pytest.raises(ClassificationJobError, match="cannot move"):
                item.transitioned(target)
    assert CLASSIFICATION_ITEM_TRANSITIONS[ClassificationItemState.CANCELLED] == frozenset()


def test_a_run_counts_its_attempts_and_a_stale_item_keeps_the_proposal_it_had() -> None:
    running = ClassificationJobItem.pending(_movement("a")).transitioned(ClassificationItemState.RUNNING)
    assert running.attempt == 1
    proposed = running.transitioned(ClassificationItemState.PROPOSED, proposal=_proposal("rev-1"))
    assert proposed.proposal_is_current("rev-1")
    assert not proposed.proposal_is_current("rev-2")
    assert not proposed.proposal_is_current(None)

    stale = proposed.transitioned(ClassificationItemState.STALE)
    assert stale.proposal == _proposal("rev-1")
    retried = stale.transitioned(ClassificationItemState.PENDING).transitioned(ClassificationItemState.RUNNING)
    assert retried.attempt == 2
    assert retried.proposal is None


def test_a_successor_rises_one_revision_and_keeps_identity_scope_lane_and_movements() -> None:
    job = _job("a", "b")
    running = job.successor(
        at=_LATER,
        status=ClassificationJobStatus.RUNNING,
        items=(job.items[0].transitioned(ClassificationItemState.RUNNING), job.items[1]),
    )
    assert running.revision == 2
    assert running.created_at == job.created_at
    assert running.updated_at == _LATER

    reordered = running.model_copy(update={"items": tuple(reversed(running.items))})
    with pytest.raises(ClassificationJobError, match="movements never change"):
        reordered.require_follows(job)
    skipped = running.model_copy(update={"revision": 3})
    with pytest.raises(ClassificationJobError, match="exactly one"):
        skipped.require_follows(job)
    relaned = running.model_copy(update={"lane": _LOCAL_LANE.model_copy(update={"model": "another"})})
    with pytest.raises(ClassificationJobError, match="never change"):
        relaned.require_follows(job)


def test_a_successor_refuses_an_item_jump_and_a_status_outside_the_table() -> None:
    job = _job("a")
    jumped = ClassificationJobItem(
        movement_id=_movement("a"), state=ClassificationItemState.PROPOSED, attempt=1, proposal=_proposal()
    )
    with pytest.raises(ClassificationJobError, match="cannot move from pending to proposed"):
        job.successor(at=_LATER, status=ClassificationJobStatus.RUNNING, items=(jumped,))
    with pytest.raises(ClassificationJobError, match="cannot move from queued to settled"):
        job.successor(at=_LATER, status=ClassificationJobStatus.SETTLED, items=(jumped,))


def test_an_interrupted_run_leaves_its_in_flight_item_unknown_and_never_settles_it() -> None:
    job = _job("a", "b")
    running = job.successor(
        at=_LATER,
        status=ClassificationJobStatus.RUNNING,
        items=(job.items[0].transitioned(ClassificationItemState.RUNNING), job.items[1]),
    )
    with pytest.raises(ValidationError, match="forbidden state"):
        running.successor(at=_LATER, status=ClassificationJobStatus.INTERRUPTED)

    interrupted = running.successor(
        at=_LATER,
        status=ClassificationJobStatus.INTERRUPTED,
        items=(running.items[0].transitioned(ClassificationItemState.UNKNOWN), running.items[1]),
    )
    assert interrupted.items[0].state is ClassificationItemState.UNKNOWN
    with pytest.raises(ValidationError, match="forbidden state"):
        interrupted.successor(at=_LATER, status=ClassificationJobStatus.SETTLED)

    resumed = interrupted.successor(at=_LATER, status=ClassificationJobStatus.QUEUED)
    assert resumed.items[0].state is ClassificationItemState.UNKNOWN
    assert resumed.items[1].state is ClassificationItemState.PENDING


def test_a_dismissed_job_is_final() -> None:
    job = _job("a")
    cancelled = job.successor(
        at=_LATER,
        status=ClassificationJobStatus.CANCELLED,
        items=(job.items[0].transitioned(ClassificationItemState.CANCELLED),),
    )
    dismissed = cancelled.successor(at=_LATER, status=ClassificationJobStatus.DISMISSED)
    for status in ClassificationJobStatus:
        if status is ClassificationJobStatus.DISMISSED:
            continue
        with pytest.raises((ClassificationJobError, ValidationError)):
            dismissed.successor(at=_LATER, status=status)
