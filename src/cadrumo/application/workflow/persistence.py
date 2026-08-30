"""Encrypted persistence for workflow state and workflow runs.

Workflow state is stored as an
:class:`~adapters.persistence.storage.Envelope`-wrapped record in the
secure-object backend. The load path deserialises the envelope and validates
it; callers receive a typed :class:`WorkflowState` or a diagnostic error class
rather than a raw payload.

The envelope carries the :class:`SensitivityClass` this store writes under, so
the classification travels with the record rather than being re-decided at each
write site.

See Also:
    :class:`~application.workflow.WorkflowState`
        Typed encrypted state payload persisted by
        :class:`WorkflowStateRepository`.
    :class:`~application.workflow.WorkflowStateResetFingerprint`
        Row-level, plaintext-free reset audit summary emitted before deletion.
    :func:`application.workflow.events.emit_workflow_state_reset`
        Writes the append-only ``workflow_state.reset`` bucket event before the
        state row is removed.
    :class:`~adapters.persistence.profile.buckets.BucketEventHistoryRepository`
        Stores the emitted reset event in the bucket event history.
    :class:`~application.workflow.WorkflowResult`
        Terminal workflow run record persisted separately by
        :class:`WorkflowRunRepository`.
"""

from __future__ import annotations

import contextvars
from collections.abc import Callable, Generator, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from ...core import SecureObjectWrite
from ...core.classification import SensitivityClass
from ...core.config import Settings, StorageRouteKind, classify_storage_route, load_settings
from ...core.logging import get_logger
from ...core.time import now as utc_now
from ...domain.buckets.event import BucketEvent
from .errors import WorkflowError
from .events import (
    WorkflowStateResetFingerprint,
    emit_workflow_state_reset,
)
from .run_models import WorkflowResult
from .state_models import WorkflowState

_logger = get_logger(__name__)


class WorkflowEnvelopeReasonClass(StrEnum):
    """Classification of the workflow-state envelope's readability.

    Carried in :attr:`~._events.WorkflowStateResetFingerprint.reason_class`
    to distinguish a healthy envelope (``READABLE``), a row that cannot
    be decrypted (``UNREADABLE``), and an absent row (``ABSENT``).
    """

    READABLE = "readable"
    UNREADABLE = "unreadable"
    ABSENT = "absent"


_UPDATE_RETRY_LIMIT = 4


class WorkflowSecureObjectRecordPort(Protocol):
    """Decrypted secure-object fields required by workflow persistence."""

    @property
    def object_key(self) -> bytes:
        """Opaque stored digest of the natural object key."""
        ...

    @property
    def payload(self) -> bytes:
        """Decrypted inner-envelope bytes."""
        ...

    @property
    def revision_id(self) -> str:
        """Current compare-and-swap revision token."""
        ...


class WorkflowSecureObjectMetadataPort(Protocol):
    """Decryption-free state-row metadata used by reset fingerprints."""

    @property
    def schema_version(self) -> int:
        """Persisted outer schema version."""
        ...

    @property
    def written_at(self) -> datetime:
        """UTC instant the row was written."""
        ...

    @property
    def byte_length(self) -> int:
        """Stored encrypted payload length."""
        ...


class WorkflowSecureObjectStorePort(Protocol):
    """Encrypted-object operations consumed by the concrete workflow adapter."""

    def load(
        self,
        namespace: str,
        object_key: str,
        *,
        expected_class: SensitivityClass,
        max_supported_version: int,
    ) -> WorkflowSecureObjectRecordPort | None:
        """Load one decrypted row under its registered contract."""
        ...

    def save_many(self, writes: tuple[SecureObjectWrite, ...]) -> None:
        """Commit prepared writes in one storage transaction."""
        ...

    def peek_metadata(self, namespace: str, object_key: str) -> WorkflowSecureObjectMetadataPort | None:
        """Read row metadata without decrypting the payload."""
        ...

    def delete(self, namespace: str, object_key: str) -> bool:
        """Delete one addressed row when present."""
        ...

    def save(
        self,
        *,
        namespace: str,
        object_key: str,
        classification: SensitivityClass,
        schema_version: int,
        written_at: datetime,
        payload: bytes,
    ) -> None:
        """Persist one encrypted payload."""
        ...

    def list_records(
        self,
        namespace: str,
        *,
        expected_class: SensitivityClass,
        max_supported_version: int,
    ) -> Iterator[WorkflowSecureObjectRecordPort]:
        """Iterate every readable row under one namespace."""
        ...


@dataclass(frozen=True, slots=True)
class WorkflowStateStorageProbe:
    """Storage-owned reset observation without adapter-specific DTOs or errors."""

    metadata: WorkflowSecureObjectMetadataPort | None
    state: WorkflowState | None
    envelope_readable: bool


class WorkflowPersistencePort(Protocol):
    """Concrete encrypted persistence capability composed by an executable host."""

    def active_store(self) -> WorkflowSecureObjectStorePort:
        """Return a secure-object store bound to the active bucket session."""
        ...

    def cold_bootstrap_store(self) -> WorkflowSecureObjectStorePort:
        """Return the recovery-only store used when no bucket is active."""
        ...

    def load_state(self, store: WorkflowSecureObjectStorePort) -> tuple[WorkflowState, str]:
        """Decode state and return the exact storage revision read."""
        ...

    def prepare_state_write(
        self,
        state: WorkflowState,
        *,
        expected_revision_id: str | None,
    ) -> SecureObjectWrite:
        """Encode one state write without committing it."""
        ...

    def save_writes(self, store: WorkflowSecureObjectStorePort, writes: tuple[SecureObjectWrite, ...]) -> None:
        """Commit state and sibling writes atomically."""
        ...

    def probe_state(self, store: WorkflowSecureObjectStorePort) -> WorkflowStateStorageProbe:
        """Return reset metadata plus any readable state payload."""
        ...

    def delete_state(self, store: WorkflowSecureObjectStorePort) -> None:
        """Delete only the workflow-state row."""
        ...

    def is_revision_conflict(self, error: BaseException) -> bool:
        """Recognise the concrete optimistic-concurrency refusal."""
        ...

    def prepare_bucket_event_write(
        self,
        store: WorkflowSecureObjectStorePort,
        events: tuple[BucketEvent, ...],
    ) -> SecureObjectWrite:
        """Prepare the history-catalogue write for ``events``."""
        ...

    def save_run(self, store: WorkflowSecureObjectStorePort, result: WorkflowResult) -> None:
        """Encode and persist one workflow run."""
        ...

    def load_run(self, store: WorkflowSecureObjectStorePort, run_id: str) -> WorkflowResult:
        """Load one run and verify its stored identity."""
        ...

    def list_runs(self, store: WorkflowSecureObjectStorePort) -> tuple[WorkflowResult, ...]:
        """Load every run after verifying stored identities."""
        ...


_BOUND_WORKFLOW_PERSISTENCE_PORT: contextvars.ContextVar[WorkflowPersistencePort] = contextvars.ContextVar(
    "cadrumo_workflow_persistence_port",
)


@contextmanager
def bind_workflow_persistence_port(port: WorkflowPersistencePort) -> Generator[WorkflowPersistencePort]:
    """Bind one outward-composed workflow persistence adapter for this host lifetime."""
    token = _BOUND_WORKFLOW_PERSISTENCE_PORT.set(port)
    try:
        yield port
    finally:
        _BOUND_WORKFLOW_PERSISTENCE_PORT.reset(token)


def workflow_persistence_port() -> WorkflowPersistencePort:
    """Resolve the explicitly composed workflow persistence adapter."""
    try:
        return _BOUND_WORKFLOW_PERSISTENCE_PORT.get()
    except LookupError as error:
        raise RuntimeError("workflow persistence infrastructure has not been composed") from error


_OPERATION_INSTANT: contextvars.ContextVar[datetime | None] = contextvars.ContextVar(
    "cadrumo_workflow_operation_instant",
    default=None,
)
"""The instant the in-flight CAS update began, stable across its retries.

Set by :meth:`WorkflowStateRepository.update_with_writes` around its retry
loop and read through :func:`current_operation_instant`.
"""


def current_operation_instant() -> datetime | None:
    """The instant the enclosing retryable update began, if inside one.

    A CAS update re-runs its callback from fresh state after a revision
    conflict, so anything the callback derives from the wall clock differs
    between attempts. That matters for bucket events: their id is derived
    from ``occurred_at``, and content-addressing is what makes a re-emission
    collapse onto one catalogue entry. A freshly read clock defeats it, and
    one logical edit lands two immutable audit rows.

    Reading the operation's instant instead keeps a retried write producing
    the same event, which is what the event repository asks of callers that
    need a retry to collapse. Outside an update this returns ``None`` and the
    caller reads the clock as usual.

    This is not the replay seam: :func:`~cadrumo.core.time.frozen_clock` is
    default-off and refuses to activate in production, and it freezes every
    clock read in scope. This names one instant, for the one derivation that
    must survive a retry.
    """
    return _OPERATION_INSTANT.get()


@contextmanager
def workflow_operation_instant_scope(instant: datetime) -> Generator[None]:
    """Publish one stable instant for every attempt of a logical state update."""
    token = _OPERATION_INSTANT.set(instant)
    try:
        yield
    finally:
        _OPERATION_INSTANT.reset(token)


class WorkflowStateRepository:
    """Encrypted secure-object repository for :class:`WorkflowState`."""

    def __init__(
        self,
        *,
        objects: WorkflowSecureObjectStorePort | None = None,
        persistence: WorkflowPersistencePort | None = None,
        emit_reset: Callable[..., object] = emit_workflow_state_reset,
    ) -> None:
        """Bind the active-bucket store and the reset-event emitter."""
        self._persistence = persistence if persistence is not None else workflow_persistence_port()
        self._objects = objects if objects is not None else self._persistence.active_store()
        # Injectable so the emit-first ordering contract in
        # reset_workflow_state can be exercised with a real failing
        # emitter — no module monkeypatching. Mirrors the injectable
        # ``objects`` seam on WorkflowRunRepository.
        self._emit_reset = emit_reset

    def load(self) -> WorkflowState:
        """Load state or return an empty payload when absent.

        Returns the persisted :class:`WorkflowState`, or an empty default
        when no state has been saved yet.
        """
        state, _revision_id = self._load_revisioned()
        return state

    def _load_revisioned(self) -> tuple[WorkflowState, str]:
        """Load state together with the exact secure-object revision read."""
        return self._persistence.load_state(self._objects)

    def save(self, state: WorkflowState) -> None:
        """Persist state in the encrypted database object store."""
        write = self.to_secure_object_write(state)
        self._persistence.save_writes(self._objects, (write,))
        _logger.debug("persisted workflow state to secure backend")

    def to_secure_object_write(
        self,
        state: WorkflowState,
        *,
        expected_revision_id: str | None = None,
    ) -> SecureObjectWrite:
        """Return the secure-object upsert for ``state`` without committing it.

        Lets callers co-transactionally persist the workflow state and a
        sibling secure-object payload (typically an updated
        bucket-event-history catalogue) via a single
        :meth:`~adapters.persistence.storage.SecureObjectRepository.save_many`
        call.
        """
        return self._persistence.prepare_state_write(
            state,
            expected_revision_id=expected_revision_id,
        )

    def fingerprint_state(
        self,
        *,
        reason_class: str | None = None,
    ) -> WorkflowStateResetFingerprint:
        """Return a :class:`WorkflowStateResetFingerprint` of the persisted state envelope.

        Reads row-level metadata only; never decrypts the payload for
        the fingerprint fields. The state envelope is loaded once to
        derive ``recovered_bucket_id`` and to classify the envelope's
        readability — a healthy, decryptable envelope is reported with
        ``reason_class="readable"``, an absent envelope with
        ``"absent"``, and an envelope row that cannot be decoded with
        ``"unreadable"``. A freshly-created storage root that has only
        just persisted a healthy state must therefore report
        ``readable``, never ``unreadable``.

        ``reason_class`` may be supplied to override the derived
        classification when the caller already knows the trigger that
        forced the reset (e.g. a downstream handler that caught the
        concrete failure). When ``None`` the classification is derived
        from the envelope itself.

        The ``repair reset-progress`` recovery verb is bootstrap-exempt
        and may run on a cold root where ``cadrumo_database_url`` does
        not resolve (no active profile). In that case there is no
        state envelope to reset; the fingerprint records empty
        metadata rather than crashing on the absent database.
        """
        probe = self._persistence.probe_state(self._objects)
        recovered_bucket_id = None if probe.state is None else probe.state.active_profile_bucket_id()
        if probe.metadata is None:
            return WorkflowStateResetFingerprint(
                schema_version=None,
                written_at=None,
                byte_length=None,
                reason_class=reason_class or WorkflowEnvelopeReasonClass.ABSENT,
                recovered_bucket_id=recovered_bucket_id,
            )
        derived_reason = (
            WorkflowEnvelopeReasonClass.READABLE if probe.envelope_readable else WorkflowEnvelopeReasonClass.UNREADABLE
        )
        return WorkflowStateResetFingerprint(
            schema_version=probe.metadata.schema_version,
            written_at=probe.metadata.written_at,
            byte_length=probe.metadata.byte_length,
            reason_class=reason_class or derived_reason,
            recovered_bucket_id=recovered_bucket_id,
        )

    def reset_workflow_state(
        self,
        *,
        actor: str = "cadrumo.application.workflow",
        source: str = "aeat config repair reset-progress",
        reason_class: str | None = None,
    ) -> WorkflowStateResetFingerprint:
        """Delete the workflow-state envelope and emit a reset event.

        The mutation is scoped to namespace ``cadrumo.workflow`` / key
        ``state``; no other namespace or row is touched. The
        ``workflow_state.reset`` bucket event is appended BEFORE the
        secure-object row is deleted so the worst-case failure mode
        leaves an audit entry with the data still present (an
        idempotent recoverable state) rather than the data discarded
        without a trail. The fingerprint never carries plaintext
        envelope content.

        Returns a :class:`WorkflowStateResetFingerprint` with a hash of
        the deleted state for audit traceability.
        """
        fingerprint = self.fingerprint_state(reason_class=reason_class)
        self._emit_reset(fingerprint=fingerprint, actor=actor, source=source)
        self._persistence.delete_state(self._objects)
        _logger.info("workflow state envelope reset; recovery route fired by operator")
        return fingerprint

    def update(self, fn: Callable[[WorkflowState], WorkflowState]) -> WorkflowState:
        """Revision-safely load, transform, save, and return workflow state."""
        return self.update_with_writes(lambda state: (fn(state), ()))

    def update_with_writes(
        self,
        fn: Callable[[WorkflowState], tuple[WorkflowState, tuple[SecureObjectWrite, ...]]],
    ) -> WorkflowState:
        """CAS-update workflow state with optional sibling secure-object writes.

        The callback is re-run from a fresh state after a revision conflict, so
        it must only derive values and prepare writes. All returned writes are
        committed with the workflow-state write in one SQL unit of work.

        One instant is minted before the first attempt and published for the
        whole loop through :func:`current_operation_instant`, so a derivation
        that would otherwise read the clock afresh on each attempt keeps its
        value. Bucket-event ids are derived from that instant, and holding it
        steady is what lets a retried emission collapse onto one catalogue
        entry instead of landing a second audit row for one logical change.
        """
        with workflow_operation_instant_scope(utc_now()):
            return self._update_with_writes_attempts(fn)

    def _update_with_writes_attempts(
        self,
        fn: Callable[[WorkflowState], tuple[WorkflowState, tuple[SecureObjectWrite, ...]]],
    ) -> WorkflowState:
        """Run the bounded CAS retry loop for :meth:`update_with_writes`."""
        for attempt in range(_UPDATE_RETRY_LIMIT):
            state, revision_id = self._load_revisioned()
            updated, sibling_writes = fn(state)
            if updated == state and not sibling_writes:
                return state
            state_write = self.to_secure_object_write(
                updated,
                expected_revision_id=revision_id,
            )
            try:
                self._persistence.save_writes(self._objects, (state_write, *sibling_writes))
            except Exception as error:
                if not self._persistence.is_revision_conflict(error) or attempt + 1 == _UPDATE_RETRY_LIMIT:
                    raise
                continue
            _logger.debug("persisted revision-aware workflow state update")
            return updated
        raise AssertionError("bounded workflow-state update retry loop exhausted")

    def update_with_bucket_events(
        self,
        fn: Callable[[WorkflowState], tuple[WorkflowState, tuple[BucketEvent, ...]]],
    ) -> WorkflowState:
        """CAS-update workflow state and append bucket events atomically."""

        def prepare(state: WorkflowState) -> tuple[WorkflowState, tuple[SecureObjectWrite, ...]]:
            updated, events = fn(state)
            if not events:
                return updated, ()
            return updated, (self._persistence.prepare_bucket_event_write(self._objects, events),)

        return self.update_with_writes(prepare)


class WorkflowRunRepository:
    """Encrypted secure-object repository for :class:`WorkflowResult` runs."""

    def __init__(
        self,
        *,
        objects: WorkflowSecureObjectStorePort | None = None,
        persistence: WorkflowPersistencePort | None = None,
    ) -> None:
        """Bind the active-bucket secure-object store for workflow runs."""
        self._persistence = persistence if persistence is not None else workflow_persistence_port()
        self._objects = objects if objects is not None else self._persistence.active_store()

    def save(self, result: WorkflowResult, *, runs_dir: Path | None = None) -> Path:
        """Persist one workflow result in the secure object backend."""
        run_id = _validate_run_id(result.run_id)
        marker_dir = runs_dir or Settings().cadrumo_workflow_runs_dir
        self._persistence.save_run(self._objects, result)
        return marker_dir / run_id

    def load(self, run_id: str) -> WorkflowResult:
        """Load one persisted :class:`WorkflowResult` from the secure backend.

        ``save`` files each run under its own ``run_id``, so the secure-object
        key IS the run's durable identity -- nothing else in the row asserts
        it. The decrypted payload's ``run_id`` is therefore compared with the
        requested key: a valid run B re-encrypted under A's key would otherwise
        be returned here, and resume reads it to decide what to continue.

        Returns the :class:`WorkflowResult` for ``run_id``.

        Raises:
            WorkflowError: When no run is stored under ``run_id``, or when the
                stored payload names a different run than the key it sits under.
        """
        safe_run_id = _validate_run_id(run_id)
        return self._persistence.load_run(self._objects, safe_run_id)

    def list(self, *, since: date | None = None) -> tuple[WorkflowResult, ...]:
        """List persisted workflow runs newest-first, optionally filtered by date.

        Each element is a :class:`WorkflowResult`.
        """
        runs = [
            result
            for result in self._persistence.list_runs(self._objects)
            if since is None or result.started_at.date() >= since
        ]
        runs.sort(key=lambda item: item.started_at, reverse=True)
        return tuple(runs)


def workflow_state_repository() -> WorkflowStateRepository:
    """Return the :class:`WorkflowStateRepository` bound to the active-bucket database.

    When an active profile bucket is present, the repository is backed by
    the bucket's own encrypted database resolved through
    :func:`~adapters.persistence.storage.secure_object_repository_for_active_bucket`
    so the URL is derived from the live bucket path rather than the
    settings-override snapshot captured at test-fixture construction
    time. A cold root with no active bucket pointer is the bootstrap
    exception: it receives an explicit bare
    :class:`~adapters.persistence.storage.SecureObjectRepository` so
    bootstrap-exempt recovery reads can still observe an absent state.
    """
    from ...core.bucket_pointer import resolve_active_bucket_id

    persistence = workflow_persistence_port()
    bucket_id = resolve_active_bucket_id()
    if bucket_id is None:
        if classify_storage_route(load_settings()).kind is StorageRouteKind.EXPLICIT_DATABASE_URL:
            return WorkflowStateRepository(objects=persistence.active_store(), persistence=persistence)
        return WorkflowStateRepository(objects=persistence.cold_bootstrap_store(), persistence=persistence)
    return WorkflowStateRepository(objects=persistence.active_store(), persistence=persistence)


def reset_workflow_state(
    *,
    actor: str = "cadrumo.application.workflow",
    source: str = "aeat config repair reset-progress",
    reason_class: str | None = None,
) -> WorkflowStateResetFingerprint:
    """Module-level helper around :meth:`WorkflowStateRepository.reset_workflow_state`.

    Returns a :class:`WorkflowStateResetFingerprint` with a hash of the
    deleted state for audit traceability.
    """
    return workflow_state_repository().reset_workflow_state(
        actor=actor,
        source=source,
        reason_class=reason_class,
    )


def fingerprint_workflow_state(*, reason_class: str | None = None) -> WorkflowStateResetFingerprint:
    """Return a :class:`WorkflowStateResetFingerprint` via :meth:`WorkflowStateRepository.fingerprint_state`."""
    return workflow_state_repository().fingerprint_state(reason_class=reason_class)


def _validate_run_id(run_id: str) -> str:
    if "/" in run_id or "\\" in run_id:
        raise WorkflowError(
            translated_message="application.workflow.errors.run_id_invalid_separators",
        )
    trimmed = run_id.strip()
    if not trimmed:
        raise WorkflowError(
            translated_message="application.workflow.errors.run_id_invalid_blank",
        )
    return trimmed


def save_run(result: WorkflowResult, *, runs_dir: Path | None = None) -> Path:
    """Persist one workflow result in the secure object backend.

    ``runs_dir`` remains part of the API as a logical marker path for callers
    and tests, but no plaintext run file is written there.
    """
    return WorkflowRunRepository().save(result, runs_dir=runs_dir)


def load_run(run_id: str) -> WorkflowResult:
    """Load and return one :class:`WorkflowResult` from the secure backend."""
    return WorkflowRunRepository().load(run_id)


def list_runs(*, since: date | None = None) -> tuple[WorkflowResult, ...]:
    """List persisted :class:`WorkflowResult` runs newest-first, optionally filtered by date."""
    return WorkflowRunRepository().list(since=since)


__all__ = [
    "WorkflowEnvelopeReasonClass",
    "WorkflowPersistencePort",
    "WorkflowRunRepository",
    "WorkflowSecureObjectMetadataPort",
    "WorkflowSecureObjectRecordPort",
    "WorkflowSecureObjectStorePort",
    "WorkflowStateRepository",
    "WorkflowStateStorageProbe",
    "bind_workflow_persistence_port",
    "current_operation_instant",
    "fingerprint_workflow_state",
    "list_runs",
    "load_run",
    "reset_workflow_state",
    "save_run",
    "workflow_operation_instant_scope",
    "workflow_persistence_port",
    "workflow_state_repository",
]
