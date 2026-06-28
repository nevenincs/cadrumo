"""Encrypted persistence for workflow state and workflow runs.

Workflow state is stored as an :class:`Envelope`-wrapped record in the
secure-object backend. The load path deserialises the envelope and
validates it; callers receive a typed :class:`WorkflowState` or a
diagnostic error class rather than a raw payload.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from enum import StrEnum
from pathlib import Path

from pydantic import ValidationError

from ...adapters.persistence.storage import (
    WORKFLOW_RUN_NAMESPACE as WORKFLOW_RUN_STORAGE_NAMESPACE,
)
from ...adapters.persistence.storage import (
    WORKFLOW_STATE_NAMESPACE as WORKFLOW_STATE_STORAGE_NAMESPACE,
)
from ...adapters.persistence.storage.envelope import Envelope
from ...adapters.persistence.storage.errors import (
    ClassificationError,
    EnvelopeVersionError,
    SecretStoreError,
    StorageError,
)
from ...adapters.persistence.storage.runtime_repository import (
    secure_object_repository_for_active_bucket,
    secure_object_repository_for_cold_bootstrap_state,
)
from ...adapters.persistence.storage.sql import SecureObjectRepository
from ...core.config import Settings, StorageRouteKind, classify_storage_route, load_settings
from ...core.logging import get_logger
from ._errors import WorkflowError
from ._events import (
    WorkflowStateResetFingerprint,
    emit_workflow_state_reset,
)
from ._models import WorkflowResult, WorkflowState, utc_now

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


def _clear_output_language_cache() -> None:
    try:
        from ...core.i18n._render import clear_output_language_cache
    except Exception:  # pragma: no cover - cache invalidation must never block persistence
        _logger.debug("workflow persistence could not import i18n cache invalidator", exc_info=True)
        return
    clear_output_language_cache()


class WorkflowStateRepository:
    """Encrypted SQL object repository for :class:`WorkflowState`."""

    def __init__(
        self,
        *,
        objects: SecureObjectRepository | None = None,
        emit_reset: Callable[..., object] = emit_workflow_state_reset,
    ) -> None:
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
        record = self._objects.load(
            _STATE_NAMESPACE,
            _STATE_OBJECT_KEY,
            expected_class=_STATE_SENSITIVITY,
            max_supported_version=_STATE_VERSION,
        )
        if record is None:
            return WorkflowState()
        raw_payload = record.payload.decode("utf-8")
        try:
            envelope = Envelope[WorkflowState].model_validate_json(raw_payload)
        except ValidationError as exc:
            raise WorkflowError(
                translated_message="application.workflow.errors.state_unreadable",
                context={"detail": str(exc)},
            ) from exc
        if envelope.classification is not _STATE_SENSITIVITY:
            raise ClassificationError(
                f"workflow state has classification {envelope.classification}; consumer expected {_STATE_SENSITIVITY}",
            )
        if envelope.schema_version > _STATE_VERSION:
            raise EnvelopeVersionError(
                f"workflow state is at version {envelope.schema_version}; consumer supports up to {_STATE_VERSION}",
            )
        return envelope.payload

    def save(self, state: WorkflowState) -> None:
        """Persist state in the encrypted database object store."""
        write = self.to_secure_object_write(state)
        self._objects.save_many((write,))
        _clear_output_language_cache()
        _logger.debug("persisted workflow state to secure backend")

    def to_secure_object_write(self, state: WorkflowState):
        """Return the secure-object upsert for ``state`` without committing it.

        Lets callers co-transactionally persist the workflow state and a
        sibling secure-object payload (typically an updated
        bucket-event-history catalogue) via a single
        :meth:`SecureObjectRepository.save_many` call.
        """
        from ...adapters.persistence.storage.sql.secure_objects import SecureObjectWrite

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
        and may run on a cold root where ``aeat_database_url`` does
        not resolve (no active profile). In that case there is no
        state envelope to reset; the fingerprint records empty
        metadata rather than crashing on the absent database
        (disaster ADR Ruling 6).
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
        actor: str = "aeat.application.workflow",
        source: str = "aeat config repair reset-progress",
        reason_class: str | None = None,
    ) -> WorkflowStateResetFingerprint:
        """Delete the workflow-state envelope and emit a reset event.

        The mutation is scoped to namespace ``aeat.workflow`` / key
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
        """Load, transform, save, and return the updated :class:`WorkflowState`."""
        state = self.load()
        updated = fn(state)
        self.save(updated)
        return updated


class WorkflowRunRepository:
    """Encrypted SQL object repository for :class:`WorkflowResult` runs."""

    def __init__(self, *, objects: SecureObjectRepository | None = None) -> None:
        self._objects = objects if objects is not None else secure_object_repository_for_active_bucket()

    def save(self, result: WorkflowResult, *, runs_dir: Path | None = None) -> Path:
        """Persist one workflow result in the secure object backend."""
        run_id = _validate_run_id(result.run_id)
        marker_dir = runs_dir or Settings().aeat_workflow_runs_dir
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

        Returns the :class:`WorkflowResult` for ``run_id``.
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
        envelope = Envelope[WorkflowResult].model_validate_json(record.payload.decode("utf-8"))
        if envelope.classification is not _RUN_SENSITIVITY:
            raise ClassificationError(
                f"workflow run has classification {envelope.classification}; consumer expected {_RUN_SENSITIVITY}",
            )
        if envelope.schema_version > _RUN_VERSION:
            raise EnvelopeVersionError(
                f"workflow run is at version {envelope.schema_version}; consumer supports up to {_RUN_VERSION}",
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
            envelope = Envelope[WorkflowResult].model_validate_json(record.payload.decode("utf-8"))
            result = envelope.payload
            if since is not None and result.started_at.date() < since:
                continue
            runs.append(result)
        runs.sort(key=lambda item: item.started_at, reverse=True)
        return tuple(runs)


def workflow_state_repository() -> WorkflowStateRepository:
    """Return the :class:`WorkflowStateRepository` bound to the active-bucket database.

    When an active profile bucket is present, the repository is backed by
    the bucket's own encrypted database resolved through
    :func:`~aeat.adapters.persistence.storage.runtime_repository.secure_object_repository_for_active_bucket`
    so the URL is derived from the live bucket path rather than the
    settings-override snapshot captured at test-fixture construction
    time. A cold root with no active bucket pointer is the bootstrap
    exception: it receives an explicit bare :class:`SecureObjectRepository`
    so bootstrap-exempt recovery reads can still observe an absent state.
    """
    from ...core import resolve_active_bucket_id

    bucket_id = resolve_active_bucket_id()
    if bucket_id is None:
        if classify_storage_route(load_settings()).kind is StorageRouteKind.EXPLICIT_DATABASE_URL:
            return WorkflowStateRepository(objects=secure_object_repository_for_active_bucket())
        return WorkflowStateRepository(objects=secure_object_repository_for_cold_bootstrap_state())
    return WorkflowStateRepository(objects=secure_object_repository_for_active_bucket())


def reset_workflow_state(
    *,
    actor: str = "aeat.application.workflow",
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
