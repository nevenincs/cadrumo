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
from collections.abc import Callable
from datetime import date, datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ...adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ...adapters.persistence.storage import (
    WORKFLOW_RUN_NAMESPACE as WORKFLOW_RUN_STORAGE_NAMESPACE,
)
from ...adapters.persistence.storage import (
    WORKFLOW_STATE_NAMESPACE as WORKFLOW_STATE_STORAGE_NAMESPACE,
)
from ...adapters.persistence.storage import (
    ClassificationError,
    Envelope,
    EnvelopeVersionError,
    SecretStoreError,
    SecureObjectRepository,
    SecureObjectRevisionConflictError,
    SecureObjectWrite,
    SensitivityClass,
    StorageError,
    inner_envelope_classification_is_expected,
    inner_envelope_version_is_current,
    secure_object_repository_for_active_bucket,
    secure_object_repository_for_cold_bootstrap_state,
)
from ...adapters.persistence.storage.crypto import secure_object_key_digest
from ...core import ABSENT_SECURE_OBJECT_REVISION_ID
from ...core.config import Settings, StorageRouteKind, classify_storage_route, load_settings
from ...core.logging import get_logger
from ...domain.buckets import BucketEvent, append_bucket_event
from .errors import WorkflowError
from .events import (
    WorkflowStateResetFingerprint,
    emit_workflow_state_reset,
)
from .run_models import WorkflowResult
from .state_models import WorkflowState, utc_now

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


_STATE_VERSION = WORKFLOW_STATE_STORAGE_NAMESPACE.schema_version
_STATE_NAMESPACE = WORKFLOW_STATE_STORAGE_NAMESPACE.namespace
_STATE_OBJECT_KEY = WORKFLOW_STATE_STORAGE_NAMESPACE.require_default_object_key()
_STATE_SENSITIVITY = WORKFLOW_STATE_STORAGE_NAMESPACE.sensitivity
_RUN_VERSION = WORKFLOW_RUN_STORAGE_NAMESPACE.schema_version
_RUN_NAMESPACE = WORKFLOW_RUN_STORAGE_NAMESPACE.namespace
_RUN_SENSITIVITY = WORKFLOW_RUN_STORAGE_NAMESPACE.sensitivity
_UPDATE_RETRY_LIMIT = 4


class _WorkflowRunEnvelopeHeader(BaseModel):
    """Version and classification inspected before the typed run payload."""

    model_config = ConfigDict(strict=True, frozen=True)

    schema_version: int = Field(ge=1)
    classification: SensitivityClass


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


def _clear_output_language_cache() -> None:
    try:
        from ...core.i18n import clear_output_language_cache
    except Exception:  # pragma: no cover - cache invalidation must never block persistence
        _logger.debug("workflow persistence could not import i18n cache invalidator", exc_info=True)
        return
    clear_output_language_cache()


class WorkflowStateRepository:
    """Encrypted secure-object repository for :class:`WorkflowState`."""

    def __init__(
        self,
        *,
        objects: SecureObjectRepository | None = None,
        emit_reset: Callable[..., object] = emit_workflow_state_reset,
    ) -> None:
        """Bind the active-bucket store and the reset-event emitter."""
        self._objects = objects if objects is not None else secure_object_repository_for_active_bucket()
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
        record = self._objects.load(
            _STATE_NAMESPACE,
            _STATE_OBJECT_KEY,
            expected_class=_STATE_SENSITIVITY,
            max_supported_version=_STATE_VERSION,
        )
        if record is None:
            return WorkflowState(), ABSENT_SECURE_OBJECT_REVISION_ID
        raw_payload = record.payload.decode("utf-8")
        try:
            envelope = Envelope[WorkflowState].model_validate_json(raw_payload)
        except ValidationError as exc:
            raise WorkflowError(
                translated_message="application.workflow.errors.state_unreadable",
                context={"detail": str(exc)},
            ) from exc
        if not inner_envelope_classification_is_expected(envelope.classification, _STATE_SENSITIVITY):
            raise ClassificationError(
                f"workflow state has classification {envelope.classification}; consumer expected {_STATE_SENSITIVITY}",
            )
        if not inner_envelope_version_is_current(envelope.schema_version, _STATE_VERSION):
            raise EnvelopeVersionError(
                f"workflow state is at version {envelope.schema_version}; consumer supports up to {_STATE_VERSION}",
            )
        return envelope.payload, record.revision_id

    def save(self, state: WorkflowState) -> None:
        """Persist state in the encrypted database object store."""
        write = self.to_secure_object_write(state)
        self._objects.save_many((write,))
        _clear_output_language_cache()
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
        try:
            payload = WorkflowState.model_validate({**state.__dict__, "updated_at": utc_now()})
        except ValueError as exc:
            raise WorkflowError(
                translated_message="application.workflow.errors.state_write_invalid_payload",
                context={"detail": str(exc)},
            ) from exc
        envelope = Envelope[WorkflowState](
            schema_version=_STATE_VERSION,
            written_at=utc_now(),
            classification=_STATE_SENSITIVITY,
            payload=payload,
        )
        return SecureObjectWrite(
            namespace=_STATE_NAMESPACE,
            object_key=_STATE_OBJECT_KEY,
            classification=_STATE_SENSITIVITY,
            schema_version=_STATE_VERSION,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json().encode("utf-8"),
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
        try:
            metadata = self._objects.peek_metadata(_STATE_NAMESPACE, _STATE_OBJECT_KEY)
        except StorageError:
            return WorkflowStateResetFingerprint(
                schema_version=None,
                written_at=None,
                byte_length=None,
                reason_class=reason_class or WorkflowEnvelopeReasonClass.ABSENT,
                recovered_bucket_id=None,
            )
        recovered_bucket_id: str | None = None
        envelope_readable = True
        try:
            state = self.load()
        except (
            WorkflowError,
            ClassificationError,
            EnvelopeVersionError,
            ValidationError,
            SecretStoreError,
        ):
            # The fingerprint path is the recovery route for an unreadable
            # envelope; surfacing the envelope failure here would defeat
            # the purpose. ``SecretStoreError`` covers the
            # bootstrap-exempt ``repair reset-progress`` case where no
            # active session is bound (``NoActiveBucketSessionError``)
            # or the session has expired (``SessionExpiredError``) —
            # the recovery verb must still delete the row by key.
            # Fall back to row-level metadata only.
            state = None
            envelope_readable = False
        if state is not None:
            recovered_bucket_id = state.active_profile_bucket_id()
        if metadata is None:
            return WorkflowStateResetFingerprint(
                schema_version=None,
                written_at=None,
                byte_length=None,
                reason_class=reason_class or WorkflowEnvelopeReasonClass.ABSENT,
                recovered_bucket_id=recovered_bucket_id,
            )
        derived_reason = (
            WorkflowEnvelopeReasonClass.READABLE if envelope_readable else WorkflowEnvelopeReasonClass.UNREADABLE
        )
        return WorkflowStateResetFingerprint(
            schema_version=metadata.schema_version,
            written_at=metadata.written_at,
            byte_length=metadata.byte_length,
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
        self._objects.delete(_STATE_NAMESPACE, _STATE_OBJECT_KEY)
        _clear_output_language_cache()
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
        token = _OPERATION_INSTANT.set(utc_now())
        try:
            return self._update_with_writes_attempts(fn)
        finally:
            _OPERATION_INSTANT.reset(token)

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
                self._objects.save_many((state_write, *sibling_writes))
            except SecureObjectRevisionConflictError:
                if attempt + 1 == _UPDATE_RETRY_LIMIT:
                    raise
                continue
            _clear_output_language_cache()
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
            repository = BucketEventHistoryRepository(objects=self._objects)
            catalogue, revision_id = repository.load_revisioned()
            for event in events:
                catalogue = append_bucket_event(catalogue, event)
            return updated, (
                repository.to_secure_object_write(
                    catalogue,
                    expected_revision_id=revision_id,
                ),
            )

        return self.update_with_writes(prepare)


class WorkflowRunRepository:
    """Encrypted secure-object repository for :class:`WorkflowResult` runs."""

    def __init__(self, *, objects: SecureObjectRepository | None = None) -> None:
        """Bind the active-bucket secure-object store for workflow runs."""
        self._objects = objects if objects is not None else secure_object_repository_for_active_bucket()

    def save(self, result: WorkflowResult, *, runs_dir: Path | None = None) -> Path:
        """Persist one workflow result in the secure object backend."""
        run_id = _validate_run_id(result.run_id)
        marker_dir = runs_dir or Settings().cadrumo_workflow_runs_dir
        envelope = Envelope[WorkflowResult](
            schema_version=_RUN_VERSION,
            written_at=utc_now(),
            classification=_RUN_SENSITIVITY,
            payload=result,
        )
        self._objects.save(
            namespace=_RUN_NAMESPACE,
            object_key=run_id,
            classification=_RUN_SENSITIVITY,
            schema_version=_RUN_VERSION,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json().encode("utf-8"),
        )
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
        record = self._objects.load(
            _RUN_NAMESPACE,
            safe_run_id,
            expected_class=_RUN_SENSITIVITY,
            max_supported_version=_RUN_VERSION,
        )
        if record is None:
            raise WorkflowError(
                translated_message="application.workflow.errors.run_not_found",
                context={"run_id": safe_run_id},
            )
        envelope = _validate_workflow_run_envelope(record.payload)
        if envelope.payload.run_id != safe_run_id:
            raise WorkflowError(
                translated_message="application.workflow.errors.run_identity_mismatch",
                context={"run_id": safe_run_id},
            )
        return envelope.payload

    def list(self, *, since: date | None = None) -> tuple[WorkflowResult, ...]:
        """List persisted workflow runs newest-first, optionally filtered by date.

        Each element is a :class:`WorkflowResult`.
        """
        records = self._objects.list_records(
            _RUN_NAMESPACE,
            expected_class=_RUN_SENSITIVITY,
            max_supported_version=_RUN_VERSION,
        )
        runs: list[WorkflowResult] = []
        for record in records:
            envelope = _validate_workflow_run_envelope(record.payload)
            result = envelope.payload
            # Enumeration has no requested key to compare against, so the
            # payload's own id is checked against the row's stored key digest --
            # the same digest the write path derived from ``run_id``.
            if secure_object_key_digest(result.run_id) != record.object_key:
                raise WorkflowError(
                    translated_message="application.workflow.errors.run_identity_mismatch",
                    context={"run_id": result.run_id},
                )
            if since is not None and result.started_at.date() < since:
                continue
            runs.append(result)
        runs.sort(key=lambda item: item.started_at, reverse=True)
        return tuple(runs)


def _validate_workflow_run_envelope(payload: bytes) -> Envelope[WorkflowResult]:
    """Validate one workflow-run envelope against the exact current contract.

    The repository is pre-release, so a workflow-run schema change advances the
    current format and refuses earlier app-written payloads. There is no legacy
    upgrader or tolerant read branch.
    """
    raw_payload = payload.decode("utf-8")
    header = _WorkflowRunEnvelopeHeader.model_validate_json(raw_payload)
    if not inner_envelope_classification_is_expected(header.classification, _RUN_SENSITIVITY):
        raise ClassificationError(
            f"workflow run has classification {header.classification}; consumer expected {_RUN_SENSITIVITY}",
        )
    if not inner_envelope_version_is_current(header.schema_version, _RUN_VERSION):
        raise EnvelopeVersionError(
            f"workflow run is at version {header.schema_version}; consumer requires {_RUN_VERSION}",
        )
    return Envelope[WorkflowResult].model_validate_json(raw_payload)


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

    bucket_id = resolve_active_bucket_id()
    if bucket_id is None:
        if classify_storage_route(load_settings()).kind is StorageRouteKind.EXPLICIT_DATABASE_URL:
            return WorkflowStateRepository(objects=secure_object_repository_for_active_bucket())
        return WorkflowStateRepository(objects=secure_object_repository_for_cold_bootstrap_state())
    return WorkflowStateRepository(objects=secure_object_repository_for_active_bucket())


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
