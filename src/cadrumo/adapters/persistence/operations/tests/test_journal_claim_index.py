"""The keyed idempotency-claim lookup reaches exactly the outcome of a full journal scan.

Every case runs the real filesystem journal. The reference resolution below is
the scan the journal used before claims were indexed: it reads every record
through the public repository and applies the same exact-claim comparison. Each
case compares the indexed lookup with it outcome for outcome, and counts the
records the indexed lookup decoded.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from typing import override

import pytest

from .....application.operations.capabilities import OperationRequestStoragePolicy
from .....application.operations.models import OperationIdentity, OperationTerminalReceipt
from .....application.operations.persistence.events import OperationPhaseEvent, OperationTerminalEvent
from .....application.operations.persistence.idempotency import OperationIdempotencyClaim
from .....application.operations.persistence.journal import OperationPersistedSnapshot
from .....application.operations.persistence.leases import (
    OperationLeaseDisposition,
    OperationOwnerLease,
    operation_conflict_scope_reference,
)
from .....core.directory_scan import scan_directory
from .....core.locks import exclusive_file_lock
from .....core.operations import OperationEffect, OperationLifecycle, OperationTerminalCondition
from .....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ...storage.errors import RepositoryError
from ..journal import OperationJournalRepository, SnapshotJournalRepository
from ..journal_validation import OperationJournalRecord
from ..lease import OperationLeaseFilesystemRepository

_YEAR = filing_year_envelope().horizon

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_STARTED = datetime(_YEAR, 9, 1, 9, tzinfo=UTC)
_DEFINITION_ID = "test.operation"

type Outcome = tuple[str, str | None]


def _operation_id(index: int) -> str:
    return sha256(f"operation-{index}".encode()).hexdigest()


def _request_reference(label: str) -> str:
    return sha256(f"request-{label}".encode()).hexdigest()


def _identity(index: int, *, subject: str) -> OperationIdentity:
    return OperationIdentity(operation_id=_operation_id(index), definition_id=_DEFINITION_ID, subject_ref=subject)


def _claim(index: int, *, subject: str, key: str, request: str) -> OperationIdempotencyClaim:
    return OperationIdempotencyClaim.bind(
        identity=_identity(index, subject=subject),
        idempotency_key=key,
        request_reference=_request_reference(request),
    )


def _created(index: int, *, subject: str, key: str | None, request: str) -> OperationPersistedSnapshot:
    identity = _identity(index, subject=subject)
    event = OperationPhaseEvent(
        identity=identity, revision=0, sequence=1, timestamp=_STARTED, code="phase.0", phase_code="phase.0"
    )
    return OperationPersistedSnapshot(
        identity=identity,
        definition_contract_digest="c" * 64,
        request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
        request_reference=_request_reference(request),
        revision=0,
        lifecycle=OperationLifecycle.RUNNING,
        phase_code=event.phase_code,
        started_at=_STARTED,
        updated_at=_STARTED,
        execution_deadline=None,
        cleanup_deadline=None,
        cancellation_requested_at=None,
        cancellation_acknowledged_at=None,
        cancellation_deferred=False,
        event_cursor=1,
        events=(event,),
        idempotency_claim=(None if key is None else _claim(index, subject=subject, key=key, request=request)),
    )


def _advanced(created: OperationPersistedSnapshot) -> OperationPersistedSnapshot:
    event = OperationPhaseEvent(
        identity=created.identity,
        revision=1,
        sequence=2,
        timestamp=_STARTED + timedelta(minutes=1),
        code="phase.1",
        phase_code="phase.1",
    )
    return created.model_copy(
        update={
            "revision": 1,
            "phase_code": event.phase_code,
            "updated_at": event.timestamp,
            "event_cursor": 2,
            "events": (event,),
        }
    )


def _terminal(created: OperationPersistedSnapshot) -> OperationPersistedSnapshot:
    settled_at = _STARTED + timedelta(minutes=1)
    receipt = OperationTerminalReceipt(
        identity=created.identity,
        revision=1,
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.NONE,
        settled_at=settled_at,
        result_ref="result:settled",
    )
    event = OperationTerminalEvent(
        identity=created.identity,
        revision=1,
        sequence=2,
        timestamp=settled_at,
        code="operation.terminal",
        receipt=receipt,
    )
    return OperationPersistedSnapshot.model_validate(
        created.model_copy(
            update={
                "revision": 1,
                "lifecycle": OperationLifecycle.TERMINAL,
                "terminal_condition": receipt.condition,
                "updated_at": settled_at,
                "event_cursor": 2,
                "events": (event,),
                "terminal_receipt": receipt,
            }
        ).model_dump()
    )


def _lease(index: int, *, subject: str) -> OperationOwnerLease:
    return OperationOwnerLease(
        operation_id=_operation_id(index),
        scope_ref=operation_conflict_scope_reference(definition_id=_DEFINITION_ID, subject_ref=subject),
        owner_id="b" * 64,
        token="c" * 64,
        acquired_at=_STARTED,
        expires_at=_STARTED + timedelta(hours=1),
    )


def _acquire(storage_root: Path, lease: OperationOwnerLease) -> None:
    acquired = asyncio.run(
        OperationLeaseFilesystemRepository(storage_root=storage_root).acquire(lease, observed_at=lease.acquired_at)
    )
    assert acquired.disposition is OperationLeaseDisposition.ACQUIRED


def _release(storage_root: Path, lease: OperationOwnerLease) -> None:
    released = asyncio.run(
        OperationLeaseFilesystemRepository(storage_root=storage_root).release(lease, observed_at=_STARTED)
    )
    assert released.disposition is OperationLeaseDisposition.RELEASED


class _CountingJournal(SnapshotJournalRepository):
    """The real substrate, recording which records a call decoded."""

    def __init__(self, *, storage_root: Path) -> None:
        super().__init__(storage_root=storage_root)
        self.decoded: list[str] = []

    @override
    def _load_unlocked(self, operation_id: str) -> OperationJournalRecord:
        self.decoded.append(operation_id)
        return super()._load_unlocked(operation_id)


def _outcome(resolve: Callable[[], str | None]) -> Outcome:
    try:
        resolved = resolve()
    except RepositoryError as exc:
        return ("refused", str(exc))
    return ("none", None) if resolved is None else ("operation", resolved)


def _full_scan_outcome(storage_root: Path, claim: OperationIdempotencyClaim) -> Outcome:
    """Resolve ``claim`` the unindexed way: read every record, compare every claim."""

    def scan() -> str | None:
        journal_root = storage_root / "operation-journals"
        repository = OperationJournalRepository(storage_root=storage_root)
        matched: str | None = None
        for path in scan_directory(journal_root, pattern="*.json"):
            operation_id = path.stem
            if len(operation_id) != 64 or any(character not in "0123456789abcdef" for character in operation_id):
                continue
            persisted = asyncio.run(repository.load(operation_id)).idempotency_claim
            if persisted is None or persisted.key_digest != claim.key_digest:
                continue
            if (
                persisted.definition_id,
                persisted.subject_ref,
                persisted.key_digest,
                persisted.request_reference,
            ) != (claim.definition_id, claim.subject_ref, claim.key_digest, claim.request_reference):
                raise RepositoryError("operation idempotency key is bound to a different request")
            if matched is not None and matched != persisted.operation_id:
                raise RepositoryError("operation idempotency key is bound to multiple operations")
            matched = persisted.operation_id
        return matched

    return _outcome(scan)


def _indexed_outcome(storage_root: Path, claim: OperationIdempotencyClaim) -> tuple[Outcome, list[str]]:
    journal = _CountingJournal(storage_root=storage_root)
    outcome = _outcome(lambda: journal.resolve_idempotency(claim))
    return outcome, journal.decoded


def _write_record(storage_root: Path, snapshot: OperationPersistedSnapshot) -> None:
    """Persist a record the way an earlier, unindexed journal did: the record alone."""
    substrate = SnapshotJournalRepository(storage_root=storage_root)
    substrate._ensure_root()
    with exclusive_file_lock(substrate.lock_target):
        substrate._write(
            substrate.path_for(snapshot.operation_id),
            OperationJournalRecord(snapshot=snapshot, history=snapshot.events),
        )


def _create(storage_root: Path, snapshot: OperationPersistedSnapshot, lease: OperationOwnerLease) -> str:
    _acquire(storage_root, lease)
    return asyncio.run(OperationJournalRepository(storage_root=storage_root).create(snapshot, lease=lease))


def _index_entries(storage_root: Path) -> dict[str, tuple[str, ...]]:
    index_root = SnapshotJournalRepository(storage_root=storage_root).claim_index_root
    entries: dict[str, tuple[str, ...]] = {}
    for path in scan_directory(index_root, pattern="*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload["operation_ids"]:
            entries[path.stem] = tuple(payload["operation_ids"])
    return entries


def _derived_entries(storage_root: Path) -> dict[str, tuple[str, ...]]:
    """What a full scan says each key digest is claimed by."""
    repository = OperationJournalRepository(storage_root=storage_root)
    derived: dict[str, set[str]] = {}
    for path in scan_directory(storage_root / "operation-journals", pattern="*.json"):
        if len(path.stem) != 64 or any(character not in "0123456789abcdef" for character in path.stem):
            continue
        claim = asyncio.run(repository.load(path.stem)).idempotency_claim
        if claim is not None:
            derived.setdefault(claim.key_digest, set()).add(claim.operation_id)
    return {key: tuple(sorted(ids)) for key, ids in derived.items()}


def _seed_neighbours(storage_root: Path, count: int) -> None:
    """Fill the journal with unrelated claim-bearing and claim-free records."""
    for index in range(100, 100 + count):
        subject = f"neighbour-{index}"
        key = None if index % 3 == 0 else f"key-{index}"
        _create(
            storage_root, _created(index, subject=subject, key=key, request=str(index)), _lease(index, subject=subject)
        )


@pytest.mark.parametrize("stage", ("created", "advanced", "terminal"))
def test_exact_replay_of_any_lifecycle_matches_the_full_scan_and_reads_one_record(tmp_path: Path, stage: str) -> None:
    """In-flight and settled claims replay the same operation, reading only that record."""
    _seed_neighbours(tmp_path, 12)
    created = _created(1, subject="replayed", key="retry-once", request="r1")
    lease = _lease(1, subject="replayed")
    assert _create(tmp_path, created, lease) == created.operation_id
    journal = OperationJournalRepository(storage_root=tmp_path)
    if stage == "advanced":
        asyncio.run(journal.commit(_advanced(created), expected_revision=0, lease=lease))
    if stage == "terminal":
        asyncio.run(journal.commit_settlement(_terminal(created), expected_revision=0, lease=lease))
    claim = created.idempotency_claim
    assert claim is not None

    outcome, decoded = _indexed_outcome(tmp_path, claim)

    assert outcome == _full_scan_outcome(tmp_path, claim) == ("operation", created.operation_id)
    assert decoded == [created.operation_id]


def test_create_with_a_replayed_claim_returns_the_original_and_writes_nothing(tmp_path: Path) -> None:
    """A retry under its own live lease names the first operation and publishes no record."""
    first = _created(1, subject="replayed", key="retry-once", request="r1")
    first_lease = _lease(1, subject="replayed")
    _create(tmp_path, first, first_lease)
    asyncio.run(
        OperationJournalRepository(storage_root=tmp_path).commit_settlement(
            _terminal(first), expected_revision=0, lease=first_lease
        )
    )
    retry = _created(2, subject="replayed", key="retry-once", request="r1")
    retry_lease = _lease(2, subject="replayed")
    _acquire(tmp_path, retry_lease)
    records_before = scan_directory(tmp_path / "operation-journals", pattern="*.json")

    replayed = asyncio.run(OperationJournalRepository(storage_root=tmp_path).create(retry, lease=retry_lease))

    assert replayed == first.operation_id
    assert scan_directory(tmp_path / "operation-journals", pattern="*.json") == records_before
    assert _index_entries(tmp_path) == _derived_entries(tmp_path)


def test_fresh_claims_resolve_to_nothing_without_reading_any_record(tmp_path: Path) -> None:
    """A new key, the same key under another subject or definition, all miss with zero reads."""
    _seed_neighbours(tmp_path, 12)
    _create(tmp_path, _created(1, subject="s", key="k", request="r"), _lease(1, subject="s"))
    other_definition = OperationIdempotencyClaim.bind(
        identity=OperationIdentity(operation_id=_operation_id(9), definition_id="test.other", subject_ref="s"),
        idempotency_key="k",
        request_reference=_request_reference("r"),
    )
    for claim in (
        _claim(2, subject="s", key="never-used", request="r"),
        _claim(3, subject="another-subject", key="k", request="r"),
        other_definition,
    ):
        outcome, decoded = _indexed_outcome(tmp_path, claim)
        assert outcome == _full_scan_outcome(tmp_path, claim) == ("none", None)
        assert decoded == []


def test_same_key_with_another_request_digest_is_refused_like_the_full_scan(tmp_path: Path) -> None:
    """The conflict refusal survives indexing, from the lookup and from create alike."""
    _seed_neighbours(tmp_path, 6)
    created = _created(1, subject="s", key="k", request="original")
    _create(tmp_path, created, _lease(1, subject="s"))
    conflicting = _claim(1, subject="s", key="k", request="different")

    outcome, decoded = _indexed_outcome(tmp_path, conflicting)

    assert outcome == _full_scan_outcome(tmp_path, conflicting)
    assert outcome == ("refused", "operation idempotency key is bound to a different request")
    assert decoded == [created.operation_id]
    _release(tmp_path, _lease(1, subject="s"))
    retry = _created(2, subject="s", key="k", request="different")
    retry_lease = _lease(2, subject="s")
    _acquire(tmp_path, retry_lease)
    with pytest.raises(RepositoryError, match="bound to a different request"):
        asyncio.run(OperationJournalRepository(storage_root=tmp_path).create(retry, lease=retry_lease))
    assert not (tmp_path / "operation-journals" / f"{retry.operation_id}.json").exists()


@pytest.mark.parametrize(
    ("lease_change", "message"),
    (
        ("foreign_token", "not the exact current durable operation lease"),
        ("expired", "expired at the supplied evidence time"),
        ("unacquired", "requires a current durable operation lease"),
        ("other_operation", "does not match the persisted snapshot identity"),
    ),
)
def test_create_checks_the_exact_live_lease_before_any_claim_is_resolved_or_indexed(
    tmp_path: Path, lease_change: str, message: str
) -> None:
    """A replayable claim never lets a foreign, expired, unheld or misbound lease through create."""
    first = _created(1, subject="s", key="k", request="r")
    first_lease = _lease(1, subject="s")
    _create(tmp_path, first, first_lease)
    asyncio.run(
        OperationJournalRepository(storage_root=tmp_path).commit_settlement(
            _terminal(first), expected_revision=0, lease=first_lease
        )
    )
    retry = _created(2, subject="s", key="k", request="r")
    held = _lease(2, subject="s")
    presented = held
    if lease_change == "foreign_token":
        _acquire(tmp_path, held)
        presented = held.model_copy(update={"token": "e" * 64})
    if lease_change == "expired":
        held = held.model_copy(update={"expires_at": _STARTED + timedelta(seconds=1)})
        _acquire(tmp_path, held)
        presented = held
        retry = retry.model_copy(update={"updated_at": _STARTED + timedelta(seconds=2)})
    if lease_change == "other_operation":
        _acquire(tmp_path, held)
        presented = held.model_copy(update={"operation_id": _operation_id(3)})
    entries_before = _index_entries(tmp_path)

    with pytest.raises(RepositoryError, match=message):
        asyncio.run(OperationJournalRepository(storage_root=tmp_path).create(retry, lease=presented))

    assert _index_entries(tmp_path) == entries_before
    assert not (tmp_path / "operation-journals" / f"{retry.operation_id}.json").exists()


def test_a_claim_in_one_storage_root_is_invisible_from_another(tmp_path: Path) -> None:
    """Each profile's journal and index answer only for that journal."""
    created = _created(1, subject="s", key="k", request="r")
    _create(tmp_path / "profile-a", created, _lease(1, subject="s"))
    _create(tmp_path / "profile-b", _created(5, subject="t", key="k", request="r"), _lease(5, subject="t"))
    claim = created.idempotency_claim
    assert claim is not None

    assert _indexed_outcome(tmp_path / "profile-a", claim)[0] == ("operation", created.operation_id)
    outcome, decoded = _indexed_outcome(tmp_path / "profile-b", claim)
    assert outcome == _full_scan_outcome(tmp_path / "profile-b", claim) == ("none", None)
    assert decoded == []


class _CrashBeforeRecordWrite(SnapshotJournalRepository):
    """The real substrate, dying at the instant between publishing a claim's entry and its record."""

    @override
    def _write(self, path: Path, operation: OperationJournalRecord) -> None:
        raise OSError("simulated crash before the record write")


def test_a_crash_between_entry_and_record_leaves_a_skipped_entry_never_a_lost_claim(tmp_path: Path) -> None:
    """The entry is published first, so a crash leaves no claim-bearing record unindexed."""
    _seed_neighbours(tmp_path, 3)
    created = _created(1, subject="s", key="k", request="r")
    lease = _lease(1, subject="s")
    _acquire(tmp_path, lease)
    with pytest.raises(OSError, match="simulated crash"):
        _CrashBeforeRecordWrite(storage_root=tmp_path).create(created, lease=lease)
    claim = created.idempotency_claim
    assert claim is not None
    assert _index_entries(tmp_path)[claim.key_digest] == (created.operation_id,)

    outcome, decoded = _indexed_outcome(tmp_path, claim)
    assert outcome == _full_scan_outcome(tmp_path, claim) == ("none", None)
    assert decoded == []

    assert asyncio.run(OperationJournalRepository(storage_root=tmp_path).create(created, lease=lease)) == (
        created.operation_id
    )
    assert _indexed_outcome(tmp_path, claim) == (("operation", created.operation_id), [created.operation_id])


def test_an_unindexed_journal_is_rebuilt_from_its_records_once(tmp_path: Path) -> None:
    """A journal from before indexing gets entries derived by one full scan, then keyed reads."""
    for index in range(20):
        key = None if index % 4 == 0 else f"key-{index}"
        _write_record(tmp_path, _created(index, subject=f"s-{index}", key=key, request=str(index)))
    target = _created(7, subject="s-7", key="key-7", request="7")
    claim = target.idempotency_claim
    assert claim is not None
    assert not SnapshotJournalRepository(storage_root=tmp_path).claim_index_root.exists()

    first, first_decoded = _indexed_outcome(tmp_path, claim)
    second, second_decoded = _indexed_outcome(tmp_path, claim)

    assert first == second == _full_scan_outcome(tmp_path, claim) == ("operation", target.operation_id)
    assert len(first_decoded) == 20 + 1
    assert second_decoded == [target.operation_id]
    assert _index_entries(tmp_path) == _derived_entries(tmp_path)


def test_an_unreadable_record_refuses_the_rebuild_exactly_as_the_scan_did(tmp_path: Path) -> None:
    """Until every record reads, no completeness witness exists and every lookup refuses."""
    _write_record(tmp_path, _created(1, subject="s", key="k", request="r"))
    _write_record(tmp_path, _created(2, subject="t", key="k", request="r"))
    (tmp_path / "operation-journals" / f"{_operation_id(2)}.json").write_text("{", encoding="utf-8")
    claim = _claim(1, subject="s", key="k", request="r")

    for _ in range(2):
        outcome, _decoded = _indexed_outcome(tmp_path, claim)
        assert outcome == _full_scan_outcome(tmp_path, claim)
        assert outcome[0] == "refused"
    index_root = SnapshotJournalRepository(storage_root=tmp_path).claim_index_root
    assert not (index_root / "complete").exists()


def test_after_indexing_only_a_candidate_record_can_refuse_a_lookup(tmp_path: Path) -> None:
    """A corrupt record under this key refuses as before; a corrupt unrelated record is not read."""
    created = _created(1, subject="s", key="k", request="r")
    _create(tmp_path, created, _lease(1, subject="s"))
    unrelated = _created(2, subject="t", key="other", request="r")
    _create(tmp_path, unrelated, _lease(2, subject="t"))
    claim = created.idempotency_claim
    unrelated_claim = unrelated.idempotency_claim
    assert claim is not None and unrelated_claim is not None
    (tmp_path / "operation-journals" / f"{unrelated.operation_id}.json").write_text("{", encoding="utf-8")

    assert _indexed_outcome(tmp_path, claim) == (("operation", created.operation_id), [created.operation_id])
    refused, decoded = _indexed_outcome(tmp_path, unrelated_claim)
    assert refused == _full_scan_outcome(tmp_path, unrelated_claim)
    assert refused[0] == "refused"
    assert decoded == [unrelated.operation_id]


@pytest.mark.parametrize(
    "damage",
    ("witness_removed", "witness_garbled", "entry_garbled", "entry_names_other_key", "index_removed", "entry_removed"),
)
def test_damaged_index_state_falls_back_to_the_records(tmp_path: Path, damage: str) -> None:
    """Every damage the adapter can detect is repaired from the records, not believed."""
    _seed_neighbours(tmp_path, 6)
    created = _created(1, subject="s", key="k", request="r")
    _create(tmp_path, created, _lease(1, subject="s"))
    claim = created.idempotency_claim
    assert claim is not None
    index_root = SnapshotJournalRepository(storage_root=tmp_path).claim_index_root
    entry = index_root / f"{claim.key_digest}.json"
    if damage == "witness_removed":
        (index_root / "complete").unlink()
    if damage == "witness_garbled":
        (index_root / "complete").write_text("not json", encoding="utf-8")
    if damage == "entry_garbled":
        entry.write_text("{", encoding="utf-8")
    if damage == "entry_names_other_key":
        payload = json.loads(entry.read_text(encoding="utf-8"))
        payload["key_digest"] = "f" * 64
        entry.write_text(json.dumps(payload), encoding="utf-8")
    if damage == "index_removed":
        shutil.rmtree(index_root)
    if damage == "entry_removed":
        # Removing one entry while leaving the witness is the one damage the
        # adapter cannot see; it is repaired only by a rebuild, so the witness
        # goes with it here to exercise that repair.
        entry.unlink()
        (index_root / "complete").unlink()

    outcome, _decoded = _indexed_outcome(tmp_path, claim)

    assert outcome == _full_scan_outcome(tmp_path, claim) == ("operation", created.operation_id)
    assert _index_entries(tmp_path) == _derived_entries(tmp_path)
    assert _indexed_outcome(tmp_path, claim) == (("operation", created.operation_id), [created.operation_id])


def test_stale_entries_for_removed_or_claim_free_records_are_discarded(tmp_path: Path) -> None:
    """An entry naming a record that is gone, or whose claim was purged, resolves nothing."""
    removed = _created(1, subject="s", key="k", request="r")
    purged = _created(2, subject="t", key="k", request="r")
    _create(tmp_path, removed, _lease(1, subject="s"))
    _create(tmp_path, purged, _lease(2, subject="t"))
    (tmp_path / "operation-journals" / f"{removed.operation_id}.json").unlink()
    _write_record(tmp_path, purged.model_copy(update={"idempotency_claim": None}))

    for claim in (removed.idempotency_claim, purged.idempotency_claim):
        assert claim is not None
        outcome, decoded = _indexed_outcome(tmp_path, claim)
        assert outcome == _full_scan_outcome(tmp_path, claim) == ("none", None)
        assert len(decoded) <= 1


def test_whole_record_save_cannot_bypass_the_index(tmp_path: Path) -> None:
    """The inherited unconditional writer is refused, so create is the only claim publisher."""
    created = _created(1, subject="s", key="k", request="r")
    with pytest.raises(RepositoryError, match="only through create and commit"):
        SnapshotJournalRepository(storage_root=tmp_path).save(
            OperationJournalRecord(snapshot=created, history=created.events)
        )
    assert not (tmp_path / "operation-journals" / f"{created.operation_id}.json").exists()


def test_contended_creates_leave_one_record_per_claim_and_an_exact_index(tmp_path: Path) -> None:
    """Concurrent creates across subjects, and a replay racing its subject's lease, stay exact."""
    count = 24
    snapshots = [_created(index, subject=f"s-{index}", key=f"k-{index}", request=str(index)) for index in range(count)]
    leases = [_lease(index, subject=f"s-{index}") for index in range(count)]
    for lease in leases:
        _acquire(tmp_path, lease)
    start = threading.Barrier(8)

    def create(index: int) -> str:
        if index < 8:
            start.wait()
        return SnapshotJournalRepository(storage_root=tmp_path).create(snapshots[index], lease=leases[index])

    with ThreadPoolExecutor(max_workers=8) as pool:
        created = list(pool.map(create, range(count)))

    assert created == [snapshot.operation_id for snapshot in snapshots]
    assert _index_entries(tmp_path) == _derived_entries(tmp_path)
    for snapshot in snapshots:
        claim = snapshot.idempotency_claim
        assert claim is not None
        assert _indexed_outcome(tmp_path, claim) == (("operation", snapshot.operation_id), [snapshot.operation_id])

    # Same claim, second operation id, its subject's lease still held by the
    # first: the lease refuses it before the claim could be published twice.
    rival = _created(500, subject="s-0", key="k-0", request="0")
    rival_lease = _lease(500, subject="s-0")
    with pytest.raises(RepositoryError, match="lease"):
        asyncio.run(OperationJournalRepository(storage_root=tmp_path).create(rival, lease=rival_lease))
    assert _index_entries(tmp_path) == _derived_entries(tmp_path)


@pytest.mark.parametrize("indexed_before", (False, True))
def test_one_key_bound_to_two_records_is_refused_like_the_full_scan(tmp_path: Path, indexed_before: bool) -> None:
    """A journal holding the same exact claim twice still refuses, before and after indexing."""
    if indexed_before:
        _create(tmp_path, _created(9, subject="t", key="k", request="r"), _lease(9, subject="t"))
    for index in (1, 2):
        _write_record(tmp_path, _created(index, subject="s", key="k", request="r"))
    if indexed_before:
        # A second writer outside create is out of contract; a rebuild is what reconciles it.
        (SnapshotJournalRepository(storage_root=tmp_path).claim_index_root / "complete").unlink()
    claim = _claim(3, subject="s", key="k", request="r")

    outcome, decoded = _indexed_outcome(tmp_path, claim)

    assert outcome == _full_scan_outcome(tmp_path, claim)
    assert outcome == ("refused", "operation idempotency key is bound to multiple operations")
    repeated, repeated_decoded = _indexed_outcome(tmp_path, claim)
    assert repeated == outcome
    assert sorted(repeated_decoded) == sorted((_operation_id(1), _operation_id(2)))
    assert len(decoded) >= len(repeated_decoded)


class _Draws:
    """A reproducible stream of choices, keyed by seed, for generated journals."""

    def __init__(self, seed: int) -> None:
        self._seed = seed
        self._counter = 0

    def below(self, bound: int) -> int:
        self._counter += 1
        digest = sha256(f"{self._seed}:{self._counter}".encode()).digest()
        return int.from_bytes(digest[:8], "big") % bound

    def choice[T](self, options: list[T]) -> T:
        return options[self.below(len(options))]


@pytest.mark.parametrize("seed", range(12))
def test_random_journals_resolve_identically_to_the_full_scan(tmp_path: Path, seed: int) -> None:
    """Arbitrary persisted journals, including duplicate and conflicting claims, agree on every query."""
    draws = _Draws(seed)
    subjects = [f"s-{index}" for index in range(4)]
    keys = [f"k-{index}" for index in range(4)]
    requests = [f"r-{index}" for index in range(3)]
    records = draws.below(31)
    for index in range(records):
        key = None if draws.below(4) == 0 else draws.choice(keys)
        _write_record(
            tmp_path,
            _created(index, subject=draws.choice(subjects), key=key, request=draws.choice(requests)),
        )
    index_root = SnapshotJournalRepository(storage_root=tmp_path).claim_index_root
    queries = [
        _claim(
            1000 + query,
            subject=draws.choice(subjects),
            key=draws.choice([*keys, "fresh"]),
            request=draws.choice(requests),
        )
        for query in range(16)
    ]
    for position, claim in enumerate(queries):
        if position == 6:
            # A witness lost mid-life sends the next lookup back through a rebuild.
            (index_root / "complete").unlink(missing_ok=True)
        if position == 10:
            # A later claim-free record needs no entry and changes no outcome.
            _write_record(tmp_path, _created(2000, subject=draws.choice(subjects), key=None, request="r-0"))
        outcome, _decoded = _indexed_outcome(tmp_path, claim)
        assert outcome == _full_scan_outcome(tmp_path, claim), (seed, position)
    assert _index_entries(tmp_path) == _derived_entries(tmp_path)
    derived = _derived_entries(tmp_path)
    for claim in queries:
        outcome, decoded = _indexed_outcome(tmp_path, claim)
        assert outcome == _full_scan_outcome(tmp_path, claim)
        # Bounded work: only the records sharing the key digest are ever read.
        assert set(decoded) <= set(derived.get(claim.key_digest, ())), seed
