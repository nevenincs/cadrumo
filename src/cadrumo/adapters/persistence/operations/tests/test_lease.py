"""Real-filesystem contracts for durable operation owner leases."""

from __future__ import annotations

import asyncio
import json
import multiprocessing
from datetime import UTC, datetime, timedelta
from multiprocessing.queues import Queue
from multiprocessing.synchronize import Event
from pathlib import Path
from queue import Empty

import pytest

from .....application.operations import (
    OperationIdentity,
    OperationRequestStoragePolicy,
)
from .....application.operations._events import OperationPhaseEvent
from .....application.operations._journal import OperationPersistedSnapshot
from .....application.operations._leases import (
    OperationLeaseDisposition,
    OperationLeaseObservationDisposition,
    OperationOwnerLease,
    operation_conflict_scope_reference,
)
from .....core import OperationEffect, OperationLifecycle, exclusive_file_lock
from ...storage import RepositoryError
from .._journal import OperationJournalRepository
from .._lease import OperationLeaseFilesystemRepository, OperationLeaseStorage

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_STARTED = datetime(2026, 8, 14, 9, tzinfo=UTC)
_OPERATION_ID = "a" * 64
_SCOPE_REF = operation_conflict_scope_reference(definition_id="test.operation", subject_ref="subject")


def _lease(
    *,
    operation_id: str = _OPERATION_ID,
    scope_ref: str = _SCOPE_REF,
    owner_id: str = "b" * 64,
    token: str = "c" * 64,
    acquired_at: datetime = _STARTED,
    expires_at: datetime = _STARTED + timedelta(minutes=5),
) -> OperationOwnerLease:
    return OperationOwnerLease(
        operation_id=operation_id,
        scope_ref=scope_ref,
        owner_id=owner_id,
        token=token,
        acquired_at=acquired_at,
        expires_at=expires_at,
    )


def _snapshot(*, revision: int) -> OperationPersistedSnapshot:
    identity = OperationIdentity(operation_id=_OPERATION_ID, definition_id="test.operation", subject_ref="subject")
    updated_at = _STARTED + timedelta(minutes=revision)
    event = OperationPhaseEvent(
        identity=identity,
        revision=revision,
        sequence=revision + 1,
        timestamp=updated_at,
        code=f"phase.{revision}",
        phase_code=f"phase.{revision}",
    )
    return OperationPersistedSnapshot(
        identity=identity,
        definition_contract_digest="c" * 64,
        request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
        request_reference="d" * 64,
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
        event_cursor=event.sequence,
        events=(event,),
    )


def _acquire_in_process(
    storage_root: str,
    candidate_payload: str,
    observed_at: str,
    start: Event,
    results: Queue[str],
) -> None:
    """Race one production repository acquisition from a separate process."""
    candidate = OperationOwnerLease.model_validate_json(candidate_payload)
    start.wait()
    result = asyncio.run(
        OperationLeaseFilesystemRepository(storage_root=Path(storage_root)).acquire(
            candidate,
            observed_at=datetime.fromisoformat(observed_at),
        )
    )
    results.put(result.disposition.value)


def _commit_in_process(
    storage_root: str,
    snapshot_payload: str,
    lease_payload: str,
    attempting: Event,
    results: Queue[str],
) -> None:
    """Commit with the production journal after announcing the lock attempt."""
    attempting.set()
    snapshot = OperationPersistedSnapshot.model_validate_json(snapshot_payload)
    lease = OperationOwnerLease.model_validate_json(lease_payload)
    try:
        asyncio.run(
            OperationJournalRepository(storage_root=Path(storage_root)).commit(
                snapshot,
                expected_revision=0,
                lease=lease,
            )
        )
    except RepositoryError as exc:
        results.put(f"error:{exc}")
        return
    results.put("committed")


def test_lease_acquires_absent_state_and_persists_exact_reload(tmp_path: Path) -> None:
    """An absent operation acquires the caller-created lease and reloads exactly."""
    repository = OperationLeaseFilesystemRepository(storage_root=tmp_path)
    candidate = _lease()

    absent = asyncio.run(repository.inspect(_SCOPE_REF, _OPERATION_ID, observed_at=_STARTED))
    assert absent.disposition is OperationLeaseObservationDisposition.ABSENT

    acquired = asyncio.run(repository.acquire(candidate, observed_at=_STARTED))
    assert acquired.disposition is OperationLeaseDisposition.ACQUIRED
    assert acquired.current == candidate
    lease_path = tmp_path / "operation-journals" / f"{_SCOPE_REF}.lease.json"
    assert json.loads(lease_path.read_text(encoding="utf-8"))["schema_version"] == 2

    reloaded = OperationLeaseFilesystemRepository(storage_root=tmp_path)
    observed = asyncio.run(reloaded.inspect(_SCOPE_REF, _OPERATION_ID, observed_at=_STARTED + timedelta(minutes=1)))
    assert observed.disposition is OperationLeaseObservationDisposition.ACTIVE
    assert observed.current == candidate


def test_lease_scope_conflicts_distinct_operations_for_one_subject_but_not_another(tmp_path: Path) -> None:
    """A definition-and-subject scope excludes peers without blocking a different subject."""
    repository = OperationLeaseFilesystemRepository(storage_root=tmp_path)
    same_subject_scope = operation_conflict_scope_reference(definition_id="test.operation", subject_ref="subject")
    other_subject_scope = operation_conflict_scope_reference(
        definition_id="test.operation", subject_ref="other-subject"
    )
    first = _lease(scope_ref=same_subject_scope)
    conflicting = _lease(
        operation_id="e" * 64,
        scope_ref=same_subject_scope,
        owner_id="f" * 64,
        token="1" * 64,
    )
    independent = _lease(
        operation_id="2" * 64,
        scope_ref=other_subject_scope,
        owner_id="3" * 64,
        token="4" * 64,
    )

    assert (
        asyncio.run(repository.acquire(first, observed_at=_STARTED)).disposition is OperationLeaseDisposition.ACQUIRED
    )
    conflict = asyncio.run(repository.acquire(conflicting, observed_at=_STARTED))
    assert conflict.disposition is OperationLeaseDisposition.CONFLICT
    assert conflict.operation_id == conflicting.operation_id
    assert conflict.scope_ref == same_subject_scope
    assert conflict.current == first
    assert (
        asyncio.run(repository.acquire(independent, observed_at=_STARTED)).disposition
        is OperationLeaseDisposition.ACQUIRED
    )

    same_subject_observation = asyncio.run(
        repository.inspect(same_subject_scope, conflicting.operation_id, observed_at=_STARTED)
    )
    assert same_subject_observation.operation_id == conflicting.operation_id
    assert same_subject_observation.current == first
    independent_observation = asyncio.run(
        repository.inspect(other_subject_scope, independent.operation_id, observed_at=_STARTED)
    )
    assert independent_observation.current == independent
    assert (tmp_path / "operation-journals" / f"{same_subject_scope}.lease.json").exists()
    assert (tmp_path / "operation-journals" / f"{other_subject_scope}.lease.json").exists()


def test_lease_refuses_retired_operation_path_without_byte_mutation(tmp_path: Path) -> None:
    """A historical operation-keyed lease is refused without opening or rewriting it."""
    candidate = _lease()
    storage = OperationLeaseStorage(storage_root=tmp_path)
    storage.ensure_root()
    retired_path = tmp_path / "operation-journals" / f"{candidate.operation_id}.lease.json"
    retired_document = {
        "schema_version": 1,
        "operation_id": candidate.operation_id,
        "recorded_at": candidate.acquired_at.isoformat(),
        "lease": candidate.model_dump(mode="json"),
    }
    retired_path.write_text(json.dumps(retired_document), encoding="utf-8")
    original_bytes = retired_path.read_bytes()
    canonical_path = storage.path_for(candidate.scope_ref)
    repository = OperationLeaseFilesystemRepository(storage_root=tmp_path)

    with pytest.raises(RepositoryError, match="retired operation-keyed path"):
        asyncio.run(repository.inspect(candidate.scope_ref, candidate.operation_id, observed_at=_STARTED))
    with pytest.raises(RepositoryError, match="retired operation-keyed path"):
        asyncio.run(repository.acquire(candidate, observed_at=_STARTED))
    assert retired_path.read_bytes() == original_bytes
    assert not canonical_path.exists()


def test_lease_scope_operation_id_collision_keeps_current_v2_path_usable(tmp_path: Path) -> None:
    """A valid v2 path shared by the scope and operation identity remains usable."""
    candidate = _lease(operation_id=_SCOPE_REF, scope_ref=_SCOPE_REF)
    storage = OperationLeaseStorage(storage_root=tmp_path)
    storage.ensure_root()
    path = storage.path_for(candidate.scope_ref)
    document = {
        "schema_version": 2,
        "scope_ref": candidate.scope_ref,
        "operation_id": candidate.operation_id,
        "recorded_at": candidate.acquired_at.isoformat(),
        "lease": candidate.model_dump(mode="json"),
    }
    path.write_text(json.dumps(document), encoding="utf-8")
    original_bytes = path.read_bytes()
    repository = OperationLeaseFilesystemRepository(storage_root=tmp_path)

    observed = asyncio.run(repository.inspect(candidate.scope_ref, candidate.operation_id, observed_at=_STARTED))
    assert observed.disposition is OperationLeaseObservationDisposition.ACTIVE
    assert observed.current == candidate
    conflict = _lease(operation_id="e" * 64, scope_ref=_SCOPE_REF, owner_id="f" * 64, token="1" * 64)
    acquired = asyncio.run(repository.acquire(conflict, observed_at=_STARTED))
    assert acquired.disposition is OperationLeaseDisposition.CONFLICT
    assert path.read_bytes() == original_bytes


def test_lease_refuses_live_conflict_and_expired_acquire_without_byte_mutation(tmp_path: Path) -> None:
    """Fresh acquisition never overwrites either a live or an expired predecessor."""
    repository = OperationLeaseFilesystemRepository(storage_root=tmp_path)
    initial = _lease(expires_at=_STARTED + timedelta(minutes=1))
    assert (
        asyncio.run(repository.acquire(initial, observed_at=_STARTED)).disposition is OperationLeaseDisposition.ACQUIRED
    )
    path = tmp_path / "operation-journals" / f"{_SCOPE_REF}.lease.json"
    original_bytes = path.read_bytes()

    conflict_candidate = _lease(
        owner_id="e" * 64,
        token="f" * 64,
        acquired_at=_STARTED + timedelta(seconds=30),
        expires_at=_STARTED + timedelta(minutes=3),
    )
    conflict = asyncio.run(repository.acquire(conflict_candidate, observed_at=conflict_candidate.acquired_at))
    assert conflict.disposition is OperationLeaseDisposition.CONFLICT
    assert path.read_bytes() == original_bytes

    expired_candidate = _lease(
        owner_id="9" * 64,
        token="8" * 64,
        acquired_at=_STARTED + timedelta(minutes=2),
        expires_at=_STARTED + timedelta(minutes=4),
    )
    expired = asyncio.run(repository.acquire(expired_candidate, observed_at=expired_candidate.acquired_at))
    assert expired.disposition is OperationLeaseDisposition.EXPIRED
    assert expired.predecessor == initial
    assert path.read_bytes() == original_bytes


def test_lease_renews_then_proves_expired_takeover_and_owner_loss(tmp_path: Path) -> None:
    """Exact CAS distinguishes renewal, expired takeover, and stale ownership loss."""
    repository = OperationLeaseFilesystemRepository(storage_root=tmp_path)
    initial = _lease(expires_at=_STARTED + timedelta(minutes=1))
    assert (
        asyncio.run(repository.acquire(initial, observed_at=_STARTED)).disposition is OperationLeaseDisposition.ACQUIRED
    )

    renewed = _lease(expires_at=_STARTED + timedelta(minutes=3))
    renewal = asyncio.run(repository.compare_and_swap(initial, renewed, observed_at=_STARTED + timedelta(seconds=30)))
    assert renewal.disposition is OperationLeaseDisposition.RENEWED
    assert renewal.current == renewed

    takeover_time = _STARTED + timedelta(minutes=4)
    takeover = _lease(
        owner_id="e" * 64,
        token="f" * 64,
        acquired_at=takeover_time,
        expires_at=takeover_time + timedelta(minutes=2),
    )
    taken_over = asyncio.run(repository.compare_and_swap(renewed, takeover, observed_at=takeover_time))
    assert taken_over.disposition is OperationLeaseDisposition.TAKEN_OVER
    assert taken_over.predecessor == renewed
    assert taken_over.current == takeover

    path = tmp_path / "operation-journals" / f"{_SCOPE_REF}.lease.json"
    bytes_after_takeover = path.read_bytes()
    lost = asyncio.run(repository.release(renewed, observed_at=takeover_time))
    assert lost.disposition is OperationLeaseDisposition.OWNER_LOST
    assert lost.current == takeover
    assert path.read_bytes() == bytes_after_takeover


def test_lease_releases_exact_predecessor_and_refuses_corruption(tmp_path: Path) -> None:
    """Release records absence, and invalid durable bytes fail closed on a fresh reload."""
    repository = OperationLeaseFilesystemRepository(storage_root=tmp_path)
    candidate = _lease()
    assert (
        asyncio.run(repository.acquire(candidate, observed_at=_STARTED)).disposition
        is OperationLeaseDisposition.ACQUIRED
    )

    released = asyncio.run(repository.release(candidate, observed_at=_STARTED + timedelta(minutes=1)))
    assert released.disposition is OperationLeaseDisposition.RELEASED
    assert (
        asyncio.run(
            repository.inspect(_SCOPE_REF, _OPERATION_ID, observed_at=_STARTED + timedelta(minutes=1))
        ).disposition
        is OperationLeaseObservationDisposition.ABSENT
    )

    replacement = _lease(
        owner_id="e" * 64,
        token="f" * 64,
        acquired_at=_STARTED + timedelta(minutes=2),
        expires_at=_STARTED + timedelta(minutes=4),
    )
    assert (
        asyncio.run(repository.acquire(replacement, observed_at=replacement.acquired_at)).disposition
        is OperationLeaseDisposition.ACQUIRED
    )
    path = tmp_path / "operation-journals" / f"{_SCOPE_REF}.lease.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["lease"]["operation_id"] = "9" * 64
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(RepositoryError, match="invalid operation lease"):
        asyncio.run(
            OperationLeaseFilesystemRepository(storage_root=tmp_path).inspect(
                _SCOPE_REF,
                _OPERATION_ID,
                observed_at=_STARTED + timedelta(minutes=3),
            )
        )


def test_concurrent_acquire_has_one_durable_winner(tmp_path: Path) -> None:
    """Two real processes contend through one operation-journal repository lock."""
    context = multiprocessing.get_context("spawn")
    start = context.Event()
    results: Queue[str] = context.Queue()
    observed_at = _STARTED.isoformat()
    candidates = (
        _lease(owner_id="b" * 64, token="c" * 64),
        _lease(owner_id="e" * 64, token="f" * 64),
    )
    processes = tuple(
        context.Process(
            target=_acquire_in_process,
            args=(str(tmp_path), candidate.model_dump_json(), observed_at, start, results),
        )
        for candidate in candidates
    )
    for process in processes:
        process.start()
    start.set()
    dispositions = sorted(results.get(timeout=15) for _ in processes)
    for process in processes:
        process.join(timeout=15)
        assert process.exitcode == 0

    assert dispositions == [OperationLeaseDisposition.ACQUIRED.value, OperationLeaseDisposition.CONFLICT.value]
    current = asyncio.run(
        OperationLeaseFilesystemRepository(storage_root=tmp_path).inspect(
            _SCOPE_REF, _OPERATION_ID, observed_at=_STARTED
        )
    ).current
    assert current in candidates


def test_journal_commit_holds_the_exact_operation_journal_lock(tmp_path: Path) -> None:
    """A journal transition waits on the same JRB lock that guards durable leases."""
    lease = _lease()
    lease_repository = OperationLeaseFilesystemRepository(storage_root=tmp_path)
    assert (
        asyncio.run(lease_repository.acquire(lease, observed_at=_STARTED)).disposition
        is OperationLeaseDisposition.ACQUIRED
    )
    storage = OperationLeaseStorage(storage_root=tmp_path)
    assert storage.lock_target == tmp_path / "operation-journals" / ".repository"
    journal = OperationJournalRepository(storage_root=tmp_path)
    asyncio.run(journal.create(_snapshot(revision=0), lease=lease))

    context = multiprocessing.get_context("spawn")
    attempting = context.Event()
    results: Queue[str] = context.Queue()
    process = context.Process(
        target=_commit_in_process,
        args=(str(tmp_path), _snapshot(revision=1).model_dump_json(), lease.model_dump_json(), attempting, results),
    )
    with exclusive_file_lock(storage.lock_target):
        process.start()
        assert attempting.wait(timeout=15)
        with pytest.raises(Empty):
            results.get(timeout=0.3)
    assert results.get(timeout=15) == "committed"
    process.join(timeout=15)
    assert process.exitcode == 0


def test_journal_refuses_absent_expired_and_stale_durable_leases_without_byte_mutation(tmp_path: Path) -> None:
    """Journal CAS never advances unless its supplied lease is exact and active."""
    cases = (
        ("absent", _lease(), _STARTED + timedelta(minutes=1)),
        ("expired", _lease(expires_at=_STARTED + timedelta(seconds=30)), _STARTED + timedelta(minutes=1)),
        ("stale_owner", _lease(), _STARTED + timedelta(minutes=1)),
        ("stale_token", _lease(), _STARTED + timedelta(minutes=1)),
        ("wrong_scope", _lease(), _STARTED + timedelta(minutes=1)),
    )
    for case, lease, observed_at in cases:
        storage_root = tmp_path / case
        lease_repository = OperationLeaseFilesystemRepository(storage_root=storage_root)
        assert (
            asyncio.run(lease_repository.acquire(lease, observed_at=_STARTED)).disposition
            is OperationLeaseDisposition.ACQUIRED
        )
        journal = OperationJournalRepository(storage_root=storage_root)
        asyncio.run(journal.create(_snapshot(revision=0), lease=lease))
        path = storage_root / "operation-journals" / f"{_OPERATION_ID}.json"
        original_bytes = path.read_bytes()

        supplied_lease = lease
        if case == "absent":
            assert (
                asyncio.run(lease_repository.release(lease, observed_at=_STARTED + timedelta(seconds=30))).disposition
                is OperationLeaseDisposition.RELEASED
            )
        if case == "stale_owner":
            supplied_lease = lease.model_copy(update={"owner_id": "e" * 64})
        if case == "stale_token":
            supplied_lease = lease.model_copy(update={"token": "f" * 64})
        if case == "wrong_scope":
            supplied_lease = lease.model_copy(
                update={
                    "scope_ref": operation_conflict_scope_reference(
                        definition_id="test.operation",
                        subject_ref="different-subject",
                    )
                }
            )
            assert (
                asyncio.run(lease_repository.acquire(supplied_lease, observed_at=_STARTED)).disposition
                is OperationLeaseDisposition.ACQUIRED
            )

        successor = _snapshot(revision=1)
        assert successor.updated_at == observed_at
        with pytest.raises(RepositoryError, match=r"durable operation lease|supplied evidence time|conflict scope"):
            asyncio.run(journal.commit(successor, expected_revision=0, lease=supplied_lease))
        assert path.read_bytes() == original_bytes
