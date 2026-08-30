"""Persist one completed synchronisation run: record and event, one transaction.

Every surface calls :func:`record_sync_run` at the point its run finishes, on
partial failure as well as on success. Nothing else writes this store.

The write is a co-write and not two writes. The record and the bucket event it
carries the id of are handed to the :class:`SecureObjectRepository` batch save
in one call, with both repositories bound to the SAME instance so they share
one session scope and roll back together. That is the shipped pattern rather
than a per-repository wrapper method: the wrappers that exist are sugar over the
same batch save, and a record type that owns no catalogue of its own has the
shorter path.

Splitting the two would reintroduce exactly the failure the pairing prevents. A
record written without its event is provenance no history mentions; an event
written without its record is a history entry whose counts nobody can read,
because a bucket-event payload value is capped and the counts live in the
record. The namespace keys the record on the event's own content-addressed id,
so the two are joined by identity rather than by a field that could drift -- and
that identity only means anything if neither can land alone.
"""

from __future__ import annotations

from datetime import datetime

from ....core import SyncSurface
from ....core.time import validate_utc_aware
from ....domain.buckets.event import BucketEventObjectType, BucketEventType
from ....domain.buckets.event_repository import build_bucket_event
from ._records import SyncRunCoverage, SyncRunRecord, SyncRunRecordRepositoryProtocol

__all__ = [
    "record_sync_run",
]

#: Which bucket event each surface's completion emits. A mapping rather than a
#: derived string: the event values are permanent and operator-visible once
#: written into anyone's history, so they are declared rather than constructed,
#: and adding a surface without its event becomes a KeyError at the write rather
#: than a run that silently records nothing.
_COMPLETION_EVENT_BY_SURFACE: dict[SyncSurface, BucketEventType] = {
    SyncSurface.FILED_DECLARATIONS: BucketEventType.SYNC_RUN_FILED_DECLARATIONS_COMPLETED,
    SyncSurface.CALC_SHEETS_EXPORT: BucketEventType.SYNC_RUN_CALC_SHEETS_EXPORT_COMPLETED,
}


def record_sync_run(
    *,
    bucket_id: str,
    surface: SyncSurface,
    resolved_scope: str,
    succeeded: bool,
    coverage: SyncRunCoverage,
    completed_at: datetime,
    repository: SyncRunRecordRepositoryProtocol,
    actor: str = "system",
) -> SyncRunRecord:
    """Persist one completed run and its bucket event in a single transaction.

    Call this on EVERY completion of a real run, including one that failed
    partway. A record written only on success makes every truncated sweep
    invisible, which is the state a reader would otherwise mistake for complete
    coverage.

    Do NOT call it from a preview branch. A dry run reads the remote surface and
    persists nothing, so it has no last-sync provenance -- nothing was synced --
    and a provenance record is itself a persist that would defeat the guard whose
    purpose is leaving no trace.

    Args:
        bucket_id: Profile bucket the run belongs to.
        surface: Which surface the run covered.
        resolved_scope: What the run actually resolved its scope to. Empty only
            when the run failed before any scope could be resolved.
        succeeded: Whether the run completed without a refusal. Recorded
            independently of ``divergence_count``, because a clean run can find
            divergences and a failed run can find none for want of getting far
            enough to look.
        coverage: What the run covered, derived from ONE source through
            :func:`coverage_of`. Taken as a derived pair rather than as two
            integers because two integer parameters let a caller pair counts
            drawn from different populations, which is exactly how a run once
            reported more divergences than units and refused its own record at
            the end of a real sweep.
        completed_at: UTC instant the run finished, successfully or not.
        repository: Persistence port that co-writes this record and its history
            event through one encrypted storage transaction.
        actor: Who invoked the run.

    Returns:
        The persisted :class:`SyncRunRecord`, carrying the id of the event it
        was written with.
    """
    completed_at = validate_utc_aware(completed_at)
    actor = actor.strip()
    event_type = _COMPLETION_EVENT_BY_SURFACE[surface]
    # The counts are stringified into the event and kept typed on the record.
    # A bucket-event payload value is capped, and the record is where a reader
    # goes for anything the cap cannot hold -- the same split the reconciliation
    # store was built for.
    payload = {
        "surface": surface.value,
        "resolved_scope": resolved_scope,
        "succeeded": str(succeeded).lower(),
        "unit_count": str(coverage.unit_count),
        "divergence_count": str(coverage.divergence_count),
    }
    event = build_bucket_event(
        bucket_id=bucket_id,
        event_type=event_type,
        occurred_at=completed_at,
        actor=actor,
        object_type=BucketEventObjectType.BUCKET,
        object_id=surface.value,
        payload_version=1,
        payload=payload,
    )
    record = SyncRunRecord(
        bucket_event_id=event.event_id,
        bucket_id=bucket_id,
        surface=surface,
        resolved_scope=resolved_scope,
        succeeded=succeeded,
        unit_count=coverage.unit_count,
        divergence_count=coverage.divergence_count,
        completed_at=completed_at,
    )

    repository.save_with_bucket_event(record, event)
    return record
