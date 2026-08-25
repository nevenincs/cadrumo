"""Integrated real-filesystem proof for durable operation persistence modules."""

from __future__ import annotations

import asyncio
import json
import multiprocessing
import os
import stat
from datetime import UTC, datetime, timedelta
from multiprocessing.queues import Queue
from multiprocessing.synchronize import Event
from pathlib import Path

import pytest

from .....application.operations.capabilities import OperationRequestStoragePolicy
from .....application.operations.models import OperationIdentity
from .....application.operations.persistence.events import OperationPhaseEvent
from .....application.operations.persistence.journal import OperationPersistedSnapshot
from .....application.operations.persistence.leases import (
    OperationLeaseDisposition,
    OperationLeaseObservationDisposition,
    OperationOwnerLease,
    operation_conflict_scope_reference,
)
from .....application.operations.persistence.replay import OperationReplayStatus
from .....core import OperationEffect, OperationLifecycle
from .....core.directory_scan import scan_directory
from ...storage import RepositoryError
from ..journal import OperationJournalRepository
from ..lease import OperationLeaseFilesystemRepository

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]

_STARTED = datetime(2026, 8, 14, 12, tzinfo=UTC)
_OPERATION_ID = "a" * 64
_REQUEST_REFERENCE = "d" * 64
_IDENTITY = OperationIdentity(
    operation_id=_OPERATION_ID, definition_id="operations.persistence.integration", subject_ref="test-subject"
)
_SCOPE_REF = operation_conflict_scope_reference(
    definition_id=_IDENTITY.definition_id,
    subject_ref=_IDENTITY.subject_ref,
)


def _lease(
    *,
    owner_id: str,
    token: str,
    acquired_at: datetime,
    expires_at: datetime,
) -> OperationOwnerLease:
    return OperationOwnerLease(
        operation_id=_OPERATION_ID,
        scope_ref=_SCOPE_REF,
        owner_id=owner_id,
        token=token,
        acquired_at=acquired_at,
        expires_at=expires_at,
    )


def _snapshot(*, revision: int, sequence: int, updated_at: datetime) -> OperationPersistedSnapshot:
    event = OperationPhaseEvent(
        identity=_IDENTITY,
        revision=revision,
        sequence=sequence,
        timestamp=updated_at,
        code=f"operation.phase.{revision}",
        phase_code=f"operation.phase.{revision}",
    )
    return OperationPersistedSnapshot(
        identity=_IDENTITY,
        definition_contract_digest="9" * 64,
        request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
        request_reference=_REQUEST_REFERENCE,
        revision=revision,
        lifecycle=OperationLifecycle.RUNNING,
        effect=OperationEffect.NONE,
        phase_code=event.phase_code,
        started_at=_STARTED,
        updated_at=updated_at,
        execution_deadline=None,
        cleanup_deadline=None,
        cancellation_requested_at=None,
        cancellation_acknowledged_at=None,
        cancellation_deferred=False,
        event_cursor=sequence,
        events=(event,),
    )


def _take_over_in_process(
    storage_root: str,
    predecessor_payload: str,
    successor_payload: str,
    observed_at: str,
    start: Event,
    results: Queue[str],
) -> None:
    """Race one actual durable lease compare-and-swap from a fresh process."""
    if not start.wait(timeout=15):
        raise RuntimeError("lease race start signal was not received")
    result = asyncio.run(
        OperationLeaseFilesystemRepository(storage_root=Path(storage_root)).compare_and_swap(
            OperationOwnerLease.model_validate_json(predecessor_payload),
            OperationOwnerLease.model_validate_json(successor_payload),
            observed_at=datetime.fromisoformat(observed_at),
        )
    )
    results.put(result.disposition.value)


def _commit_in_process(
    storage_root: str,
    snapshot_payload: str,
    lease_payload: str,
    start: Event,
    results: Queue[str],
) -> None:
    """Race one actual snapshot compare-and-swap from a fresh process."""
    if not start.wait(timeout=15):
        raise RuntimeError("journal race start signal was not received")
    try:
        asyncio.run(
            OperationJournalRepository(storage_root=Path(storage_root)).commit(
                OperationPersistedSnapshot.model_validate_json(snapshot_payload),
                expected_revision=0,
                lease=OperationOwnerLease.model_validate_json(lease_payload),
            )
        )
    except RepositoryError:
        results.put("rejected")
        return
    results.put("committed")


def _assert_no_staging_residue(directory: Path) -> None:
    assert scan_directory(directory, pattern="*.tmp") == ()


def test_public_persistence_modules_commit_replay_and_reload_credential_free_history(tmp_path: Path) -> None:
    """A restart sees one complete credential-free snapshot and idempotent cursor pages."""
    owner = _lease(
        owner_id="b" * 64,
        token="c" * 64,
        acquired_at=_STARTED,
        expires_at=_STARTED + timedelta(minutes=10),
    )
    leases = OperationLeaseFilesystemRepository(storage_root=tmp_path)
    journal = OperationJournalRepository(storage_root=tmp_path)
    assert asyncio.run(leases.acquire(owner, observed_at=_STARTED)).disposition is OperationLeaseDisposition.ACQUIRED

    initial = _snapshot(revision=0, sequence=1, updated_at=_STARTED)
    successor = _snapshot(revision=1, sequence=2, updated_at=_STARTED + timedelta(minutes=1))
    asyncio.run(journal.create(initial, lease=owner))
    asyncio.run(journal.commit(successor, expected_revision=0, lease=owner))

    journal_path = tmp_path / "operation-journals" / f"{_OPERATION_ID}.json"
    raw_text = journal_path.read_text(encoding="utf-8")
    raw_document = json.loads(raw_text)
    assert set(raw_document) == {"snapshot", "history"}
    assert raw_document["snapshot"]["request_reference"] == _REQUEST_REFERENCE
    assert raw_text.count(_REQUEST_REFERENCE) == 1
    assert owner.owner_id not in raw_text
    assert owner.token not in raw_text
    assert raw_document["snapshot"]["credential_free_request_json"] is None
    assert raw_document["snapshot"]["secret_requirement"] is None
    assert journal_path.parent == tmp_path / "operation-journals"
    assert journal_path.resolve(strict=True).parent.parent == tmp_path.resolve(strict=True)
    assert not journal_path.is_symlink()
    _assert_no_staging_residue(journal_path.parent)
    if os.name != "nt":
        assert stat.S_IMODE(journal_path.parent.stat().st_mode) == 0o700
        assert stat.S_IMODE(journal_path.stat().st_mode) == 0o600

    restarted = OperationJournalRepository(storage_root=tmp_path)
    assert asyncio.run(restarted.load(_OPERATION_ID)) == successor
    first_page = asyncio.run(restarted.read_after(_OPERATION_ID, 0, limit=1))
    repeated_first_page = asyncio.run(restarted.read_after(_OPERATION_ID, 0, limit=1))
    assert first_page == repeated_first_page
    assert first_page.status is OperationReplayStatus.PAGE
    assert tuple(event.sequence for event in first_page.events) == (1,)
    assert first_page.next_cursor == 1
    second_page = asyncio.run(restarted.read_after(_OPERATION_ID, first_page.next_cursor, limit=1))
    assert second_page.status is OperationReplayStatus.PAGE
    assert tuple(event.sequence for event in second_page.events) == (2,)
    assert second_page.next_cursor == 2
    caught_up = asyncio.run(restarted.read_after(_OPERATION_ID, second_page.next_cursor, limit=1))
    assert caught_up.status is OperationReplayStatus.CAUGHT_UP
    assert caught_up.events == ()
    assert caught_up.next_cursor == second_page.next_cursor

    stable_bytes = journal_path.read_bytes()
    with pytest.raises(RepositoryError, match="stale"):
        asyncio.run(
            restarted.commit(
                _snapshot(revision=2, sequence=3, updated_at=_STARTED + timedelta(minutes=2)),
                expected_revision=0,
                lease=owner,
            )
        )
    assert journal_path.read_bytes() == stable_bytes
    _assert_no_staging_residue(journal_path.parent)


def test_public_persistence_modules_enforce_exact_owner_across_conflict_takeover_and_release(tmp_path: Path) -> None:
    """Only the exact live owner can advance the journal before or after takeover."""
    initial_owner = _lease(
        owner_id="b" * 64,
        token="c" * 64,
        acquired_at=_STARTED,
        expires_at=_STARTED + timedelta(minutes=2),
    )
    renewed_owner = _lease(
        owner_id="b" * 64,
        token="c" * 64,
        acquired_at=_STARTED,
        expires_at=_STARTED + timedelta(minutes=3),
    )
    takeover_time = _STARTED + timedelta(minutes=4)
    replacement_owner = _lease(
        owner_id="e" * 64,
        token="f" * 64,
        acquired_at=takeover_time,
        expires_at=takeover_time + timedelta(minutes=2),
    )
    leases = OperationLeaseFilesystemRepository(storage_root=tmp_path)
    journal = OperationJournalRepository(storage_root=tmp_path)
    assert (
        asyncio.run(leases.acquire(initial_owner, observed_at=_STARTED)).disposition
        is OperationLeaseDisposition.ACQUIRED
    )
    asyncio.run(journal.create(_snapshot(revision=0, sequence=1, updated_at=_STARTED), lease=initial_owner))

    conflict = asyncio.run(leases.acquire(replacement_owner, observed_at=_STARTED + timedelta(minutes=1)))
    assert conflict.disposition is OperationLeaseDisposition.CONFLICT
    renewal = asyncio.run(
        leases.compare_and_swap(initial_owner, renewed_owner, observed_at=_STARTED + timedelta(minutes=1))
    )
    assert renewal.disposition is OperationLeaseDisposition.RENEWED
    assert (
        asyncio.run(leases.inspect(_SCOPE_REF, _OPERATION_ID, observed_at=takeover_time)).disposition
        is OperationLeaseObservationDisposition.EXPIRED
    )
    takeover = asyncio.run(leases.compare_and_swap(renewed_owner, replacement_owner, observed_at=takeover_time))
    assert takeover.disposition is OperationLeaseDisposition.TAKEN_OVER
    assert takeover.current == replacement_owner

    journal_path = tmp_path / "operation-journals" / f"{_OPERATION_ID}.json"
    before_stale_owner = journal_path.read_bytes()
    successor = _snapshot(revision=1, sequence=2, updated_at=takeover_time)
    with pytest.raises(RepositoryError, match="exact current"):
        asyncio.run(journal.commit(successor, expected_revision=0, lease=renewed_owner))
    assert journal_path.read_bytes() == before_stale_owner

    asyncio.run(journal.commit(successor, expected_revision=0, lease=replacement_owner))
    assert asyncio.run(OperationJournalRepository(storage_root=tmp_path).load(_OPERATION_ID)) == successor
    released = asyncio.run(leases.release(replacement_owner, observed_at=takeover_time + timedelta(minutes=1)))
    assert released.disposition is OperationLeaseDisposition.RELEASED
    assert (
        asyncio.run(
            leases.inspect(_SCOPE_REF, _OPERATION_ID, observed_at=takeover_time + timedelta(minutes=1))
        ).disposition
        is OperationLeaseObservationDisposition.ABSENT
    )

    stable_bytes = journal_path.read_bytes()
    with pytest.raises(RepositoryError, match="requires a current durable"):
        asyncio.run(
            journal.commit(
                _snapshot(revision=2, sequence=3, updated_at=takeover_time + timedelta(minutes=1)),
                expected_revision=1,
                lease=replacement_owner,
            )
        )
    assert journal_path.read_bytes() == stable_bytes
    _assert_no_staging_residue(journal_path.parent)


def test_public_persistence_modules_serialize_expired_takeover_races_without_residue(tmp_path: Path) -> None:
    """Two fresh processes race an expired lease CAS and preserve one durable winner."""
    predecessor = _lease(
        owner_id="b" * 64,
        token="c" * 64,
        acquired_at=_STARTED,
        expires_at=_STARTED + timedelta(minutes=1),
    )
    observed_at = _STARTED + timedelta(minutes=2)
    successors = (
        _lease(
            owner_id="e" * 64, token="f" * 64, acquired_at=observed_at, expires_at=observed_at + timedelta(minutes=2)
        ),
        _lease(
            owner_id="1" * 64, token="2" * 64, acquired_at=observed_at, expires_at=observed_at + timedelta(minutes=2)
        ),
    )
    leases = OperationLeaseFilesystemRepository(storage_root=tmp_path)
    assert (
        asyncio.run(leases.acquire(predecessor, observed_at=_STARTED)).disposition is OperationLeaseDisposition.ACQUIRED
    )

    context = multiprocessing.get_context("spawn")
    start = context.Event()
    results: Queue[str] = context.Queue()
    processes = tuple(
        context.Process(
            target=_take_over_in_process,
            args=(
                str(tmp_path),
                predecessor.model_dump_json(),
                successor.model_dump_json(),
                observed_at.isoformat(),
                start,
                results,
            ),
        )
        for successor in successors
    )
    for process in processes:
        process.start()
    start.set()
    dispositions = sorted(results.get(timeout=15) for _ in processes)
    for process in processes:
        process.join(timeout=15)
        assert process.exitcode == 0

    assert dispositions == [OperationLeaseDisposition.OWNER_LOST.value, OperationLeaseDisposition.TAKEN_OVER.value]
    current = asyncio.run(
        OperationLeaseFilesystemRepository(storage_root=tmp_path).inspect(
            _SCOPE_REF, _OPERATION_ID, observed_at=observed_at
        )
    ).current
    assert current in successors
    lease_path = tmp_path / "operation-journals" / f"{_SCOPE_REF}.lease.json"
    stable_bytes = lease_path.read_bytes()
    assert (
        asyncio.run(leases.release(predecessor, observed_at=observed_at)).disposition
        is OperationLeaseDisposition.OWNER_LOST
    )
    assert lease_path.read_bytes() == stable_bytes
    _assert_no_staging_residue(lease_path.parent)


def test_public_persistence_modules_serialize_snapshot_cas_and_refuse_linked_roots(tmp_path: Path) -> None:
    """Concurrent snapshot CAS leaves one complete winner, while linked roots cannot redirect bytes."""
    owner = _lease(
        owner_id="b" * 64,
        token="c" * 64,
        acquired_at=_STARTED,
        expires_at=_STARTED + timedelta(minutes=10),
    )
    leases = OperationLeaseFilesystemRepository(storage_root=tmp_path)
    journal = OperationJournalRepository(storage_root=tmp_path)
    assert asyncio.run(leases.acquire(owner, observed_at=_STARTED)).disposition is OperationLeaseDisposition.ACQUIRED
    asyncio.run(journal.create(_snapshot(revision=0, sequence=1, updated_at=_STARTED), lease=owner))
    successor = _snapshot(revision=1, sequence=2, updated_at=_STARTED + timedelta(minutes=1))

    context = multiprocessing.get_context("spawn")
    start = context.Event()
    results: Queue[str] = context.Queue()
    processes = tuple(
        context.Process(
            target=_commit_in_process,
            args=(str(tmp_path), successor.model_dump_json(), owner.model_dump_json(), start, results),
        )
        for _ in range(2)
    )
    for process in processes:
        process.start()
    start.set()
    outcomes = sorted(results.get(timeout=15) for _ in processes)
    for process in processes:
        process.join(timeout=15)
        assert process.exitcode == 0

    assert outcomes == ["committed", "rejected"]
    journal_path = tmp_path / "operation-journals" / f"{_OPERATION_ID}.json"
    stable_bytes = journal_path.read_bytes()
    assert asyncio.run(OperationJournalRepository(storage_root=tmp_path).load(_OPERATION_ID)) == successor
    with pytest.raises(RepositoryError, match="stale"):
        asyncio.run(journal.commit(successor, expected_revision=0, lease=owner))
    assert journal_path.read_bytes() == stable_bytes
    _assert_no_staging_residue(journal_path.parent)

    linked_storage_root = tmp_path / "linked-root"
    redirected_directory = tmp_path / "redirected-directory"
    linked_storage_root.mkdir()
    redirected_directory.mkdir()
    (linked_storage_root / "operation-journals").symlink_to(redirected_directory, target_is_directory=True)
    linked_leases = OperationLeaseFilesystemRepository(storage_root=linked_storage_root)
    with pytest.raises(RepositoryError, match="symlink or junction"):
        asyncio.run(linked_leases.acquire(owner, observed_at=_STARTED))
    assert scan_directory(redirected_directory, pattern="*.json") == ()
