"""Atomic filesystem implementation of the credential-free operation journal."""

from __future__ import annotations

import asyncio
import os
import re
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Final, Literal, override

from pydantic import BaseModel, ValidationError, field_validator

from ....application.journal_repository import JournalBusyError, JournalRepositoryBase
from ....application.operations.event_replay import OperationEventCursor
from ....application.operations.models import OperationId, OperationRevision
from ....application.operations.persistence.idempotency import OperationIdempotencyClaim
from ....application.operations.persistence.journal import (
    OperationEventStream,
    OperationInventoryLimit,
    OperationJournal,
    OperationObservationCursorAheadError,
    OperationObservationMaterialization,
    OperationObservationReader,
    OperationObservationUnknownOperationError,
    OperationPersistedSnapshot,
    OperationProgressFoldInput,
    OperationRecoveryInventoryDelta,
    OperationRecoveryInventoryDeltaReader,
    OperationRecoveryInventoryDisposition,
    OperationRecoveryInventoryEntry,
    OperationRecoveryInventoryPage,
)
from ....application.operations.persistence.leases import OperationOwnerLease
from ....application.operations.persistence.replay import (
    OperationReplayLimit,
    OperationReplayPage,
    OperationReplayStatus,
)
from ....core.atomic_write import DurableWriteBatch, atomic_write_hardened_bytes
from ....core.directory_scan import (
    scan_directory,
)
from ....core.external_constants import UTF_8_ENCODING
from ....core.hex import HEX_PATTERN_64
from ....core.identity.digest import ContentDigest
from ....core.link_safety import is_link_like
from ....core.locks import exclusive_file_lock
from ....core.logging import get_logger
from ....core.models import STRICT_FROZEN_CONFIG
from ....core.operations import OperationLifecycle
from ....core.storage_taxonomy import StorageCategory
from ....core.storage_taxonomy_locations import storage_location
from ..storage.errors import RepositoryError
from ..storage.master_key.login_handover_journal import handover_journal_path
from .financial_journal_purge import FinancialEditJournalPurgeRefusedError, purge_legacy_financial_edit_journal
from .journal_validation import OperationJournalRecord, validate_advance, validate_lease
from .lease import OperationLeaseStorage

_log = get_logger(__name__)


def _unreadable_reason(error: RepositoryError) -> str:
    """Where and how a record failed validation, naming fields and error types but no value."""
    cause = error.__cause__
    if isinstance(cause, ValidationError):
        failures = (
            f"{'.'.join(str(part) for part in failure['loc'])}:{failure['type']}"
            for failure in cause.errors(include_url=False, include_input=False, include_context=False)
        )
        return ";".join(failures)[:512]
    return type(cause if cause is not None else error).__name__


class OperationReplayRequest(BaseModel):
    """Strict adapter-local replay inputs before filesystem access."""

    model_config = STRICT_FROZEN_CONFIG

    cursor: OperationEventCursor
    limit: OperationReplayLimit


class _OperationInventoryRequest(BaseModel):
    """Validate bounded inventory coordinates before touching the filesystem."""

    model_config = STRICT_FROZEN_CONFIG

    after: OperationId | None
    limit: OperationInventoryLimit


_HEX_64: Final = re.compile(HEX_PATTERN_64)
_CLAIM_INDEX_DIRNAME: Final = "idempotency-claims"
_CLAIM_INDEX_COMPLETE_FILENAME: Final = "complete"
_CLAIM_INDEX_DIRECTORY_MODE: Final = 0o700
_CLAIM_INDEX_FILE_MODE: Final = 0o600


class _ClaimIndexEntry(BaseModel):
    """Which journal records were created carrying one idempotency key digest.

    The entry is a derived lookup aid, never evidence: every named record is
    loaded and validated before its claim is believed, so an entry naming an
    absent record, a record whose claim was purged, or a record with another
    claim changes nothing.
    """

    model_config = STRICT_FROZEN_CONFIG

    schema_version: Literal[1]
    key_digest: ContentDigest
    operation_ids: tuple[OperationId, ...]

    @field_validator("operation_ids")
    @classmethod
    def _sorted_unique(cls, value: tuple[OperationId, ...]) -> tuple[OperationId, ...]:
        if tuple(sorted(set(value))) != value:
            raise ValueError("claim index operation ids must be sorted and unique")
        return value


class _ClaimIndexCompleteness(BaseModel):
    """Witness that every claim-bearing record in the journal root has an entry."""

    model_config = STRICT_FROZEN_CONFIG

    schema_version: Literal[1]


def replay_page_from_record(
    record: OperationJournalRecord,
    request: OperationReplayRequest,
) -> OperationReplayPage:
    """Build one bounded replay page from the exact record already read."""
    events = tuple(event for event in record.history if event.sequence > request.cursor)[: request.limit]
    if not events:
        return OperationReplayPage(
            status=OperationReplayStatus.CAUGHT_UP,
            requested_cursor=request.cursor,
            events=(),
            next_cursor=request.cursor,
        )
    return OperationReplayPage(
        status=OperationReplayStatus.PAGE,
        requested_cursor=request.cursor,
        events=events,
        next_cursor=events[-1].sequence,
    )


def observation_materialization_from_record(
    record: OperationJournalRecord,
    request: OperationReplayRequest,
) -> OperationObservationMaterialization:
    """Derive every observation fact from one immutable journal record."""
    anchor_cursor = record.snapshot.event_cursor
    if request.cursor > anchor_cursor:
        raise OperationObservationCursorAheadError(
            requested_cursor=request.cursor,
            anchor_cursor=anchor_cursor,
        )
    return OperationObservationMaterialization(
        snapshot=record.snapshot,
        anchor_cursor=anchor_cursor,
        replay=replay_page_from_record(record, request),
        progress_fold=OperationProgressFoldInput(events=record.history),
    )


class SnapshotJournalRepository(JournalRepositoryBase[OperationJournalRecord]):
    """Synchronous atomic substrate specialized to persisted operation snapshots."""

    def __init__(self, *, storage_root: Path) -> None:
        super().__init__(
            journal_dirname=storage_location(StorageCategory.OPERATION_JOURNAL).subpath,
            storage_root=storage_root,
            parse_operation=OperationJournalRecord.model_validate_json,
            error_type=RepositoryError,
            not_found_type=RepositoryError,
            corrupt_type=RepositoryError,
            subject="operation journal",
            id_subject="operation",
        )
        self._lease_storage = OperationLeaseStorage(storage_root=storage_root)
        self._profile_handover_path = handover_journal_path(storage_root)

    @override
    def load(self, operation_id: str) -> OperationJournalRecord:
        """Capture one generation, purge legacy operands exclusively, then validate."""
        record = self.read_existing(operation_id)
        if record is None:
            raise RepositoryError(operation_id)
        return record

    def read_existing(self, operation_id: str) -> OperationJournalRecord | None:
        """Report absence only at capture; later filesystem changes cannot hide corruption."""
        if not self._validate_existing_root():
            return None
        with exclusive_file_lock(self.lock_target):
            try:
                raw = self._read_payload(operation_id)
            except RepositoryError:
                if self.is_absent(operation_id):
                    return None
                raise
        replacement = purge_legacy_financial_edit_journal(raw, operation_id=operation_id)
        if replacement is not None:
            with exclusive_file_lock(self.lock_target):
                if self._read_payload(operation_id) == raw:
                    self._write_purged_payload_unlocked(operation_id, replacement)
                    raw = replacement
                else:
                    # Another writer may already have purged and advanced this
                    # record. Resolve that generation once under exclusion,
                    # rather than overwriting it or retrying without a bound.
                    raw = self._read_purged_payload_unlocked(operation_id)
        # Validation depends only on the captured text. A slow decoder must not
        # exclude writers, and corruption cannot be reclassified by a later deletion.
        return self._decode_payload(operation_id, raw)

    def _load_unlocked(self, operation_id: str) -> OperationJournalRecord:
        return self._decode_payload(operation_id, self._read_purged_payload_unlocked(operation_id))

    def _read_purged_payload_unlocked(self, operation_id: str) -> str:
        """Capture one complete generation; legacy repair remains a locked write."""
        raw = self._read_payload(operation_id)
        replacement = purge_legacy_financial_edit_journal(raw, operation_id=operation_id)
        if replacement is not None:
            self._write_purged_payload_unlocked(operation_id, replacement)
            raw = replacement
        return raw

    def _write_purged_payload_unlocked(self, operation_id: str, replacement: str) -> None:
        """Publish operand disposal only under journal exclusion, with a bounded refusal."""
        try:
            self._write_payload(self.path_for(operation_id), replacement)
        except (OSError, RepositoryError, JournalBusyError):
            raise FinancialEditJournalPurgeRefusedError from None

    def resolve_idempotency(self, claim: OperationIdempotencyClaim) -> str | None:
        """Resolve a durable retry key from a complete operation journal only."""
        self._ensure_root()
        with exclusive_file_lock(self.lock_target):
            return self._resolve_idempotency_unlocked(claim)

    def read_observation(
        self,
        operation_id: str,
        request: OperationReplayRequest,
    ) -> OperationObservationMaterialization | None:
        """Capture one locked generation, then decode and materialize that exact text."""
        record = self.read_existing(operation_id)
        if record is None:
            return None
        return observation_materialization_from_record(record, request)

    def is_absent(self, operation_id: str) -> bool:
        """Tell a missing record from a present but unreadable one."""
        path = self.path_for(operation_id)
        return not os.path.lexists(self.root) or not os.path.lexists(path)

    def inventory_page(self, request: _OperationInventoryRequest) -> OperationRecoveryInventoryPage:
        """Classify one ID-ordered page under the same exclusion as journal writes."""
        if not self._validate_existing_root():
            return OperationRecoveryInventoryPage(entries=(), next_cursor=request.after, has_more=False)
        with exclusive_file_lock(self.lock_target):
            try:
                paths = scan_directory(self.root, pattern="*.json", require_root=True)
            except OSError as exc:
                raise RepositoryError("cannot scan operation journal inventory") from exc
            operation_ids = self._inventory_operation_ids(paths)
            selected = tuple(
                operation_id for operation_id in operation_ids if request.after is None or operation_id > request.after
            )
            page_ids = selected[: request.limit]
            entries: list[OperationRecoveryInventoryEntry] = []
            for operation_id in page_ids:
                entries.append(self._recovery_inventory_entry(operation_id))
            return OperationRecoveryInventoryPage(
                entries=tuple(entries),
                next_cursor=page_ids[-1] if page_ids else request.after,
                has_more=len(selected) > request.limit,
            )

    def inventory_delta(self, known: frozenset[OperationId]) -> OperationRecoveryInventoryDelta:
        """Name every present record and classify the ones outside ``known``, in one exclusion.

        One directory scan replaces a page-by-page inventory for a caller that
        already classified most records: a record's definition is fixed when it
        is created, so only records it has not seen need to be read.
        """
        if not self._validate_existing_root():
            return OperationRecoveryInventoryDelta(present=frozenset(), entries=())
        with exclusive_file_lock(self.lock_target):
            try:
                paths = scan_directory(self.root, pattern="*.json", require_root=True)
            except OSError as exc:
                raise RepositoryError("cannot scan operation journal inventory") from exc
            present = self._inventory_operation_ids(paths)
            return OperationRecoveryInventoryDelta(
                present=frozenset(present),
                entries=tuple(
                    self._recovery_inventory_entry(operation_id)
                    for operation_id in sorted(present)
                    if operation_id not in known
                ),
            )

    def _inventory_operation_ids(self, paths: Iterable[Path]) -> list[OperationId]:
        """Validate inventory names while excluding canonical lease and handover rows."""
        operation_ids: list[OperationId] = []
        for path in paths:
            # This shared storage category also contains the login owner's
            # exact handover witness. Its defining owner validates it; it
            # is not a canonical operation invocation or recovery target.
            if path == self._profile_handover_path:
                continue
            if path.name.endswith(".lease.json"):
                scope_ref = path.name.removesuffix(".lease.json")
                try:
                    expected_lease_name = self._lease_storage.path_for(scope_ref).name
                except RepositoryError as exc:
                    raise RepositoryError("invalid operation journal inventory filename") from exc
                if path.name != expected_lease_name:
                    raise RepositoryError("invalid operation journal inventory filename")
                continue
            try:
                expected_name = self.path_for(path.stem).name
            except RepositoryError as exc:
                raise RepositoryError("invalid operation journal inventory filename") from exc
            if path.name != expected_name:
                raise RepositoryError("invalid operation journal inventory filename")
            operation_ids.append(path.stem)
        return operation_ids

    def _recovery_inventory_entry(self, operation_id: OperationId) -> OperationRecoveryInventoryEntry:
        """Classify one present journal row while refusing an inventory race."""
        try:
            record = self._load_unlocked(operation_id)
        except RepositoryError as error:
            if not self._validate_existing_root() or self.is_absent(operation_id):
                raise RepositoryError("operation journal inventory changed during read") from None
            _log.warning(
                "operation journal record unreadable operation=%s reason=%s",
                operation_id,
                _unreadable_reason(error),
            )
            return OperationRecoveryInventoryEntry(
                operation_id=operation_id,
                disposition=OperationRecoveryInventoryDisposition.REFUSED,
                definition_id=None,
            )
        return OperationRecoveryInventoryEntry(
            operation_id=operation_id,
            disposition=(
                OperationRecoveryInventoryDisposition.TERMINAL
                if record.snapshot.lifecycle is OperationLifecycle.TERMINAL
                else OperationRecoveryInventoryDisposition.NONTERMINAL
            ),
            definition_id=record.snapshot.identity.definition_id,
        )

    @property
    def claim_index_root(self) -> Path:
        """Return the directory of derived idempotency-claim lookup entries."""
        return self.root / _CLAIM_INDEX_DIRNAME

    @override
    def save(self, operation: OperationJournalRecord) -> None:
        """Refuse a whole-record write that would bypass create's claim index entry."""
        del operation
        raise RepositoryError("operation journal records are written only through create and commit")

    def _resolve_idempotency_unlocked(self, claim: OperationIdempotencyClaim) -> str | None:
        """Find one exact claim while the canonical journal lock is already held.

        Only the records the claim index names for this key digest are read.
        Each is loaded and validated in full, so the outcome is the one a scan
        of every record would reach: the index can only name extra records,
        which validation discards, and never omits one (see
        :meth:`_claim_index_candidates_unlocked`).
        """
        matched_operation_id: str | None = None
        for operation_id in self._claim_index_candidates_unlocked(claim.key_digest):
            if not os.path.lexists(self.path_for(operation_id)):
                # A create that published its entry but not its record, or a
                # record removed since: neither holds the claim.
                continue
            persisted_claim = self._load_unlocked(operation_id).snapshot.idempotency_claim
            if persisted_claim is None or persisted_claim.key_digest != claim.key_digest:
                continue
            if (
                persisted_claim.definition_id,
                persisted_claim.subject_ref,
                persisted_claim.key_digest,
                persisted_claim.request_reference,
            ) != (
                claim.definition_id,
                claim.subject_ref,
                claim.key_digest,
                claim.request_reference,
            ):
                raise RepositoryError("operation idempotency key is bound to a different request")
            if matched_operation_id is not None and matched_operation_id != persisted_claim.operation_id:
                raise RepositoryError("operation idempotency key is bound to multiple operations")
            matched_operation_id = persisted_claim.operation_id
        return matched_operation_id

    def _claim_index_candidates_unlocked(self, key_digest: str) -> tuple[OperationId, ...]:
        """Name every record that may carry ``key_digest``, a superset of those that do.

        Completeness rests on two writers, both under the journal lock: the
        rebuild derives every entry from a full scan of the records and only
        then publishes the completeness witness, and :meth:`create` publishes a
        claim's entry before the record that carries it. A record's claim is
        never changed by a commit and only ever cleared by the legacy purge, so
        an entry can go stale but no claim-bearing record can lack one. An
        absent or unreadable witness, or a malformed entry, sends the lookup
        back to the records through one rebuild.
        """
        if not self._claim_index_is_complete_unlocked():
            self._rebuild_claim_index_unlocked()
        try:
            return self._read_claim_index_entry_unlocked(key_digest)
        except RepositoryError:
            self._rebuild_claim_index_unlocked()
            return self._read_claim_index_entry_unlocked(key_digest)

    def _claim_index_entry_path(self, key_digest: str) -> Path:
        if _HEX_64.fullmatch(key_digest) is None:
            raise RepositoryError("operation idempotency key digest must be 64 lowercase hexadecimal characters")
        return self.claim_index_root / f"{key_digest}.json"

    def _claim_index_complete_path(self) -> Path:
        return self.claim_index_root / _CLAIM_INDEX_COMPLETE_FILENAME

    def _read_claim_index_text_unlocked(self, path: Path) -> str | None:
        """Read one index file, ``None`` when absent; links and unreadable files are refused."""
        if not os.path.lexists(path):
            return None
        if is_link_like(path) or is_link_like(self.claim_index_root):
            raise RepositoryError("operation idempotency claim index cannot be a link")
        try:
            return path.read_text(encoding=UTF_8_ENCODING)
        except OSError as exc:
            raise RepositoryError("cannot read operation idempotency claim index") from exc

    def _claim_index_is_complete_unlocked(self) -> bool:
        try:
            raw = self._read_claim_index_text_unlocked(self._claim_index_complete_path())
        except RepositoryError:
            return False
        if raw is None:
            return False
        try:
            _ClaimIndexCompleteness.model_validate_json(raw)
        except ValidationError:
            return False
        return True

    def _read_claim_index_entry_unlocked(self, key_digest: str) -> tuple[OperationId, ...]:
        raw = self._read_claim_index_text_unlocked(self._claim_index_entry_path(key_digest))
        if raw is None:
            return ()
        try:
            entry = _ClaimIndexEntry.model_validate_json(raw)
        except ValidationError as exc:
            raise RepositoryError("invalid operation idempotency claim index entry") from exc
        if entry.key_digest != key_digest:
            raise RepositoryError("operation idempotency claim index entry names another key")
        return entry.operation_ids

    def _ensure_claim_index_root_unlocked(self) -> None:
        index_root = self.claim_index_root
        if os.path.lexists(index_root) and is_link_like(index_root):
            raise RepositoryError("operation idempotency claim index cannot be a link")
        index_root.mkdir(exist_ok=True)
        if not index_root.is_dir():
            raise RepositoryError("operation idempotency claim index is not a directory")
        try:
            # Private directory mode; Semgrep's generic file-mode rule is inverted here.
            os.chmod(index_root, _CLAIM_INDEX_DIRECTORY_MODE)  # nosemgrep
        except OSError as exc:
            raise RepositoryError("cannot restrict operation idempotency claim index permissions") from exc

    def _write_claim_index_entry_unlocked(
        self,
        key_digest: str,
        operation_ids: Iterable[OperationId],
        *,
        rebuild_batch: DurableWriteBatch | None = None,
    ) -> None:
        entry = _ClaimIndexEntry(
            schema_version=1,
            key_digest=key_digest,
            operation_ids=tuple(sorted(set(operation_ids))),
        )
        path = self._claim_index_entry_path(key_digest)
        payload = entry.model_dump_json() + "\n"
        if rebuild_batch is None:
            self._write_payload(path, payload)
            return
        if self._read_claim_index_text_unlocked(path) == payload:
            return
        # A rebuilt entry is re-derived from the records it names, so its
        # durability sync is batched (see DurableWriteBatch): a torn entry is
        # refused as malformed and rebuilt again. A create's entry is not.
        atomic_write_hardened_bytes(
            path, payload.encode(UTF_8_ENCODING), mode=_CLAIM_INDEX_FILE_MODE, batch=rebuild_batch
        )
        try:
            os.chmod(path, _CLAIM_INDEX_FILE_MODE)
        except OSError as exc:
            raise RepositoryError("cannot restrict operation idempotency claim index permissions") from exc

    def _add_claim_index_entry_unlocked(self, key_digest: str, operation_id: OperationId) -> None:
        """Publish ``operation_id`` under ``key_digest`` before its record is written."""
        self._ensure_claim_index_root_unlocked()
        existing = self._read_claim_index_entry_unlocked(key_digest)
        if operation_id not in existing:
            self._write_claim_index_entry_unlocked(key_digest, (*existing, operation_id))

    def _rebuild_claim_index_unlocked(self) -> None:
        """Derive every entry from a full scan of the records, then witness completeness.

        The scan reads every record exactly as the unindexed lookup did, so a
        record that cannot be read refuses the rebuild and the witness stays
        unpublished: until every record is readable, each lookup repeats this
        scan and refuses the same way.
        """
        claimed: dict[str, set[OperationId]] = {}
        for path in scan_directory(self.root, pattern="*.json"):
            operation_id = path.stem
            if _HEX_64.fullmatch(operation_id) is None:
                continue
            persisted_claim = self._load_unlocked(operation_id).snapshot.idempotency_claim
            if persisted_claim is not None:
                claimed.setdefault(persisted_claim.key_digest, set()).add(persisted_claim.operation_id)
        self._ensure_claim_index_root_unlocked()
        complete_path = self._claim_index_complete_path()
        if os.path.lexists(complete_path):
            if is_link_like(complete_path):
                raise RepositoryError("operation idempotency claim index cannot be a link")
            complete_path.unlink()
        rebuild_batch = DurableWriteBatch()
        self._replace_claim_index_entries_unlocked(claimed, rebuild_batch)
        # Every entry's publication is synced before the witness that relies
        # on it, which is itself written with a full per-file sync.
        rebuild_batch.commit()
        self._write_payload(complete_path, _ClaimIndexCompleteness(schema_version=1).model_dump_json() + "\n")

    def _replace_claim_index_entries_unlocked(
        self,
        claimed: Mapping[str, set[OperationId]],
        rebuild_batch: DurableWriteBatch,
    ) -> None:
        """Make the entry files exactly the derived mapping, refusing foreign files."""
        for path in scan_directory(self.claim_index_root, require_root=True):
            if path.name == _CLAIM_INDEX_COMPLETE_FILENAME:
                continue
            key_digest = path.name.removesuffix(".json")
            if path.suffix != ".json" or _HEX_64.fullmatch(key_digest) is None:
                raise RepositoryError("invalid operation idempotency claim index filename")
            if is_link_like(path) or not path.is_file():
                raise RepositoryError("operation idempotency claim index entry is not a regular file")
            if key_digest not in claimed:
                path.unlink()
        for key_digest, operation_ids in claimed.items():
            self._write_claim_index_entry_unlocked(key_digest, operation_ids, rebuild_batch=rebuild_batch)

    def create(self, snapshot: OperationPersistedSnapshot, *, lease: OperationOwnerLease) -> str:
        """Create the initial snapshot and its retry claim in one journal write."""
        validate_lease(snapshot, lease)
        self._ensure_root()
        path = self.path_for(snapshot.operation_id)
        with exclusive_file_lock(self.lock_target):
            self._lease_storage.require_live_exact_unlocked(
                scope_ref=lease.scope_ref,
                operation_id=snapshot.operation_id,
                lease=lease,
                observed_at=snapshot.updated_at,
            )
            if snapshot.idempotency_claim is not None:
                existing = self._resolve_idempotency_unlocked(snapshot.idempotency_claim)
                if existing is not None:
                    return existing
            if os.path.lexists(path):
                raise RepositoryError("initial operation journal create already exists")
            self._validate_create(snapshot, expected_revision=0)
            record = OperationJournalRecord(snapshot=snapshot, history=snapshot.events)
            if snapshot.idempotency_claim is not None:
                # Entry first: a crash between the two writes leaves an entry
                # naming an absent record, which lookups skip, never a
                # claim-bearing record the index cannot find.
                self._add_claim_index_entry_unlocked(snapshot.idempotency_claim.key_digest, snapshot.operation_id)
            self._write(path, record)
        return snapshot.operation_id

    def commit(
        self,
        snapshot: OperationPersistedSnapshot,
        *,
        expected_revision: OperationRevision,
        lease: OperationOwnerLease,
    ) -> None:
        """Atomically advance an existing snapshot to one non-terminal successor."""
        if snapshot.lifecycle is OperationLifecycle.TERMINAL:
            raise RepositoryError("a terminal operation snapshot is committed only with its lease release")
        validate_lease(snapshot, lease)
        self._ensure_root()
        with exclusive_file_lock(self.lock_target):
            self._advance_unlocked(snapshot, expected_revision=expected_revision, lease=lease)

    def commit_settlement(
        self,
        snapshot: OperationPersistedSnapshot,
        *,
        expected_revision: OperationRevision,
        lease: OperationOwnerLease,
    ) -> None:
        """Write the terminal snapshot and clear its scope's lease inside one lock hold.

        Lease acquisition takes this same lock, so no submitter can observe the
        terminal record while the lease is still held. A process that dies
        between the two writes leaves a terminal record beside a lease its
        operation no longer uses; submission and reconciliation recover that.
        """
        if snapshot.lifecycle is not OperationLifecycle.TERMINAL:
            raise RepositoryError("operation settlement commit requires a terminal snapshot")
        validate_lease(snapshot, lease)
        self._ensure_root()
        with exclusive_file_lock(self.lock_target):
            self._advance_unlocked(snapshot, expected_revision=expected_revision, lease=lease)
            self._lease_storage.replace_unlocked(
                lease.scope_ref,
                snapshot.operation_id,
                None,
                observed_at=snapshot.updated_at,
            )

    def _advance_unlocked(
        self,
        snapshot: OperationPersistedSnapshot,
        *,
        expected_revision: OperationRevision,
        lease: OperationOwnerLease,
    ) -> None:
        """Validate the exact live lease and the transition, then write, while the lock is held."""
        self._lease_storage.require_live_exact_unlocked(
            scope_ref=lease.scope_ref,
            operation_id=snapshot.operation_id,
            lease=lease,
            observed_at=snapshot.updated_at,
        )
        path = self.path_for(snapshot.operation_id)
        if not os.path.lexists(path):
            raise RepositoryError("operation journal commit requires an existing snapshot created via create")
        current = self._load_unlocked(snapshot.operation_id)
        self._validate_advance(current.snapshot, snapshot, expected_revision)
        record = OperationJournalRecord(snapshot=snapshot, history=(*current.history, *snapshot.events))
        self._write(path, record)

    @staticmethod
    def _validate_create(snapshot: OperationPersistedSnapshot, expected_revision: OperationRevision) -> None:
        if expected_revision != 0 or snapshot.revision != 0:
            raise RepositoryError(
                "initial operation journal create requires expected revision and snapshot revision zero"
            )
        if not snapshot.events and snapshot.event_cursor != 0:
            raise RepositoryError("initial operation journal create requires empty history cursor zero")
        if snapshot.events and snapshot.events[0].sequence != 1:
            raise RepositoryError("initial operation journal create event history must begin at sequence one")

    @staticmethod
    def _validate_advance(
        current: OperationPersistedSnapshot,
        snapshot: OperationPersistedSnapshot,
        expected_revision: OperationRevision,
    ) -> None:
        validate_advance(current, snapshot, expected_revision)


class OperationJournalRepository(
    OperationJournal, OperationRecoveryInventoryDeltaReader, OperationEventStream, OperationObservationReader
):
    """Async operation-journal port over the atomic filesystem substrate.

    Every port call runs the synchronous substrate -- its lock wait and its
    file reads and writes -- on a worker thread, so a frontend's event loop
    stays responsive while a journal operation waits on contention or disk.
    The thread inherits the caller's context, so the settings and storage
    route in effect for the caller are the ones the substrate reads.
    """

    def __init__(self, *, storage_root: Path) -> None:
        """Bind the repository to the configured secure storage root."""
        self._repository = SnapshotJournalRepository(storage_root=storage_root)

    @override
    async def load(self, operation_id: str) -> OperationPersistedSnapshot:
        """Load the latest credential-free snapshot for one operation."""
        record = await asyncio.to_thread(self._repository.load, operation_id)
        return record.snapshot

    @override
    async def inventory_page(
        self, *, after: OperationId | None, limit: OperationInventoryLimit
    ) -> OperationRecoveryInventoryPage:
        """Read one bounded startup page without blocking the event loop."""
        request = _OperationInventoryRequest(after=after, limit=limit)
        return await asyncio.to_thread(self._repository.inventory_page, request)

    @override
    async def inventory_delta(self, *, known: frozenset[OperationId]) -> OperationRecoveryInventoryDelta:
        """List every record and classify the unknown ones without blocking the event loop."""
        return await asyncio.to_thread(self._repository.inventory_delta, known)

    @override
    async def resolve_idempotency(self, claim: OperationIdempotencyClaim) -> str | None:
        return await asyncio.to_thread(self._repository.resolve_idempotency, claim)

    @override
    async def create(self, snapshot: OperationPersistedSnapshot, *, lease: OperationOwnerLease) -> str:
        """Create a complete initial journal before making an idempotency replay visible."""
        return await asyncio.to_thread(self._repository.create, snapshot, lease=lease)

    @override
    async def read_after(
        self,
        operation_id: str,
        cursor: OperationEventCursor,
        *,
        limit: OperationReplayLimit,
    ) -> OperationReplayPage:
        """Return one bounded, exclusive page from retained event history."""
        request = OperationReplayRequest(cursor=cursor, limit=limit)
        return await asyncio.to_thread(self._read_after_blocking, operation_id, request)

    def _read_after_blocking(self, operation_id: str, request: OperationReplayRequest) -> OperationReplayPage:
        record = self._repository.read_existing(operation_id)
        if record is None:
            return OperationReplayPage(
                status=OperationReplayStatus.UNKNOWN_OPERATION,
                requested_cursor=request.cursor,
                events=(),
                next_cursor=request.cursor,
            )
        return replay_page_from_record(record, request)

    @override
    async def read_observation(
        self,
        operation_id: str,
        after_cursor: OperationEventCursor,
        *,
        limit: OperationReplayLimit,
    ) -> OperationObservationMaterialization:
        """Return snapshot, replay, and progress facts anchored to one locked record.

        The caller is typically a poll worker on an interface event loop, so
        the lock wait and the read both run on a worker thread; cancelling the
        awaiting task returns control at once while the bounded read finishes.
        """
        materialization = await asyncio.to_thread(
            self._repository.read_observation,
            operation_id,
            OperationReplayRequest(cursor=after_cursor, limit=limit),
        )
        if materialization is None:
            raise OperationObservationUnknownOperationError(operation_id)
        return materialization

    @override
    async def commit(
        self,
        snapshot: OperationPersistedSnapshot,
        *,
        expected_revision: OperationRevision,
        lease: OperationOwnerLease,
    ) -> None:
        """Atomically advance an existing snapshot through the typed substrate."""
        await asyncio.to_thread(self._repository.commit, snapshot, expected_revision=expected_revision, lease=lease)

    @override
    async def commit_settlement(
        self,
        snapshot: OperationPersistedSnapshot,
        *,
        expected_revision: OperationRevision,
        lease: OperationOwnerLease,
    ) -> None:
        """Commit the terminal snapshot and release its lease under one journal-root lock."""
        await asyncio.to_thread(
            self._repository.commit_settlement,
            snapshot,
            expected_revision=expected_revision,
            lease=lease,
        )

    def is_absent(self, operation_id: str) -> bool:
        """Distinguish an absent record from a present but unreadable record."""
        return self._repository.is_absent(operation_id)


__all__ = [
    "OperationJournalRepository",
    "OperationReplayRequest",
    "observation_materialization_from_record",
    "replay_page_from_record",
]
