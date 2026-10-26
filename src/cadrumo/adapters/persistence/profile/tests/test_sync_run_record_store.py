"""Persistence-adapter integration tests for encrypted sync-run provenance."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.sync_runs import SyncRunRecordRepository
from cadrumo.adapters.persistence.profile.tests.profile_registration import register_minimal_profile
from cadrumo.adapters.persistence.storage.secure_object_namespaces import SYNC_RUN_RECORDS_NAMESPACE
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import open_test_profile_session
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.application.storage.sync_runs.persist import record_sync_run
from cadrumo.application.storage.sync_runs.records import SyncRunCoverage, SyncRunRecord
from cadrumo.application.workflow.persistence import workflow_state_repository
from cadrumo.core.sync_surface import SyncSurface
from cadrumo.domain.buckets.event import BucketEventType

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "11111111-1111-4111-8111-111111111111"
_COMPLETED_AT = datetime(2026, 8, 10, 9, 30, tzinfo=UTC)


@pytest.fixture
def active_profile(tmp_path: Path) -> Iterator[str]:
    """Bind a real isolated encrypted profile bucket for one test."""
    with isolated_profile_storage_root(tmp_path=tmp_path), open_test_profile_session(_BUCKET_ID):
        # Seeded through a detached WorkflowState, never a repository read:
        # the capsule publishes by an atomic no-replace rename onto
        # ``buckets/<profile-id>``, which a workflow-state repository
        # construction would otherwise materialise first and collide with.
        register_minimal_profile(profile_id=_BUCKET_ID)
        bucket_id = workflow_state_repository().load().active_profile_bucket_id()
        assert bucket_id is not None
        yield bucket_id


def test_every_defaultable_field_survives_the_round_trip_carrying_a_non_default_value(
    active_profile: str,
) -> None:
    """A strict round trip through the real encrypted store, no field left at its default.

    ``resolved_scope``, ``unit_count`` and ``divergence_count`` all carry
    defaults, so each is populated with a value the default could not produce.
    A save that dropped one and a load that re-defaulted it would be invisible
    against a fixture that used the defaults.
    """
    record = SyncRunRecord(
        bucket_event_id="a" * 64,
        bucket_id=active_profile,
        surface=SyncSurface.CALC_SHEETS_EXPORT,
        resolved_scope="303 2026-1T",
        succeeded=False,
        unit_count=17,
        divergence_count=5,
        completed_at=_COMPLETED_AT,
    )
    repository = SyncRunRecordRepository()
    repository.save(record)

    loaded = repository.load(repository.extract_identifier(record))

    assert loaded == record, "the record must survive the encrypted boundary under strict equality"
    assert loaded is not None
    assert loaded.resolved_scope == "303 2026-1T"
    assert loaded.unit_count == 17
    assert loaded.divergence_count == 5
    assert loaded.succeeded is False


def test_a_payload_with_a_deleted_field_is_refused_rather_than_re_defaulted(
    active_profile: str,
) -> None:
    """Anti-tautology proof: corrupt the stored payload and require a refusal.

    Without this, the round trip above could pass while the boundary silently
    reconstructed missing fields from defaults -- which is precisely how a
    save-drops / load-re-defaults regression hides.
    """
    record = SyncRunRecord(
        bucket_event_id="b" * 64,
        bucket_id=active_profile,
        surface=SyncSurface.FILED_DECLARATIONS,
        resolved_scope="130 2025-2026",
        succeeded=True,
        unit_count=9,
        divergence_count=2,
        completed_at=_COMPLETED_AT,
    )
    repository = SyncRunRecordRepository()
    repository.save(record)
    identifier = repository.extract_identifier(record)

    objects = repository.secure_object_repository
    stored = objects.load(
        SYNC_RUN_RECORDS_NAMESPACE.namespace,
        identifier,
        expected_class=SYNC_RUN_RECORDS_NAMESPACE.sensitivity,
        max_supported_version=SYNC_RUN_RECORDS_NAMESPACE.schema_version,
    )
    assert stored is not None
    document = json.loads(stored.payload)
    del document["payload"]["completed_at"]
    objects.save(
        namespace=SYNC_RUN_RECORDS_NAMESPACE.namespace,
        object_key=identifier,
        classification=SYNC_RUN_RECORDS_NAMESPACE.sensitivity,
        schema_version=SYNC_RUN_RECORDS_NAMESPACE.schema_version,
        written_at=_COMPLETED_AT,
        payload=json.dumps(document).encode("utf-8"),
        expected_revision_id=stored.revision_id,
    )

    with pytest.raises(ValidationError):
        repository.load(identifier)


def test_two_runs_over_one_surface_do_not_collapse(active_profile: str) -> None:
    """N records per surface. A collapsing key would make the last sync the only sync.

    This is the store's whole reason for existing: the phase it serves is
    last-sync PROVENANCE, and a key scoped to the surface alone would overwrite
    the history rather than extend it.
    """
    first = record_sync_run(
        bucket_id=active_profile,
        surface=SyncSurface.FILED_DECLARATIONS,
        resolved_scope="303 2025-2025",
        succeeded=True,
        coverage=SyncRunCoverage(unit_count=3, divergence_count=0),
        completed_at=_COMPLETED_AT,
        repository=SyncRunRecordRepository(),
    )
    second = record_sync_run(
        bucket_id=active_profile,
        surface=SyncSurface.FILED_DECLARATIONS,
        resolved_scope="303 2026-2026",
        succeeded=False,
        coverage=SyncRunCoverage(unit_count=1, divergence_count=1),
        completed_at=_COMPLETED_AT + timedelta(hours=1),
        repository=SyncRunRecordRepository(),
    )

    assert first.bucket_event_id != second.bucket_event_id
    repository = SyncRunRecordRepository()
    stored_ids = set(repository.iter_ids())
    assert repository.extract_identifier(first) in stored_ids
    assert repository.extract_identifier(second) in stored_ids, "the second run must not overwrite the first"


def test_the_record_and_its_bucket_event_land_together(active_profile: str) -> None:
    """The pair is co-written, and the record is keyed on the event's own id.

    That identity is what joins the two surfaces without a cross-reference field
    that could drift, and it only means anything if neither can land alone.
    """
    record = record_sync_run(
        bucket_id=active_profile,
        surface=SyncSurface.CALC_SHEETS_EXPORT,
        resolved_scope="100 2026-0A",
        succeeded=True,
        coverage=SyncRunCoverage(unit_count=42, divergence_count=1),
        completed_at=_COMPLETED_AT,
        repository=SyncRunRecordRepository(),
    )

    # `.events` is a Mapping keyed by event id, not a sequence of events, so the
    # record's own id is a direct lookup rather than a scan.
    events = BucketEventHistoryRepository().load().events
    assert record.bucket_event_id in events, "the event the record names must exist in the history"
    event = events[record.bucket_event_id]
    assert event.event_type is BucketEventType.SYNC_RUN_CALC_SHEETS_EXPORT_COMPLETED
    assert event.payload["divergence_count"] == "1"

    loaded = SyncRunRecordRepository().load(SyncRunRecordRepository().extract_identifier(record))
    assert loaded is not None, "the record must be present alongside the event it names"
