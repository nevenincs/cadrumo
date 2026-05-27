"""Encrypted persistence for workflow state and workflow runs."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from pathlib import Path

from pydantic import ValidationError

from ...adapters.persistence.storage.envelope._envelope import Envelope
from ...adapters.persistence.storage.errors import (
    ClassificationError,
    EnvelopeVersionError,
    SecretStoreError,
    StorageError,
)
from ...adapters.persistence.storage.sql import SecureObjectRepository
from ...core.classification import SensitivityClass
from ...core.config import Settings
from ...core.i18n import tr
from ...core.logging import get_logger
from ._errors import WorkflowError
from ._events import (
    WorkflowStateResetFingerprint,
    emit_workflow_state_reset,
)
from ._models import WorkflowResult, WorkflowState, utc_now

_logger = get_logger(__name__)

_STATE_VERSION = 1
_STATE_NAMESPACE = "aeat.workflow"
_STATE_OBJECT_KEY = "state"
_RUN_VERSION = 1
_RUN_NAMESPACE = "aeat.application.workflow.runs"


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
        self._objects = objects if objects is not None else SecureObjectRepository()
        # Injectable so the emit-first ordering contract in
        # reset_workflow_state can be exercised with a real failing
        # emitter — no module monkeypatching. Mirrors the injectable
        # ``objects`` seam on WorkflowRunRepository.
        self._emit_reset = emit_reset

    def load(self) -> WorkflowState:
        """Load state or return an empty payload when absent."""

        record = self._objects.load(
            _STATE_NAMESPACE,
            _STATE_OBJECT_KEY,
            expected_class=SensitivityClass.FINANCIAL,
            max_supported_version=_STATE_VERSION,
        )
        if record is None:
            return WorkflowState()
        raw_payload = record.payload.decode("utf-8")
        try:
            envelope = Envelope[WorkflowState].model_validate_json(raw_payload)
        except ValidationError as exc:
            raise WorkflowError(
                tr("application.workflow.errors.state_unreadable"),
            ) from exc
        if envelope.classification is not SensitivityClass.FINANCIAL:
            raise ClassificationError(
                f"workflow state has classification {envelope.classification}; "
                f"consumer expected {SensitivityClass.FINANCIAL}",
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
            raise WorkflowError(f"workflow state refused invalid payload: {exc}") from exc
        envelope = Envelope[WorkflowState](
            schema_version=_STATE_VERSION,
            written_at=utc_now(),
            classification=SensitivityClass.FINANCIAL,
            payload=payload,
        )
        return SecureObjectWrite(
            namespace=_STATE_NAMESPACE,
            object_key=_STATE_OBJECT_KEY,
            classification=SensitivityClass.FINANCIAL,
            schema_version=_STATE_VERSION,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json().encode("utf-8"),
        )

    def fingerprint_state(
        self,
        *,
        reason_class: str | None = None,
    ) -> WorkflowStateResetFingerprint:
        """Return a row-level fingerprint of the persisted state envelope.

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

        The ``repair reset-state`` recovery verb is bootstrap-exempt
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
                reason_class=reason_class or "absent",
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
            # bootstrap-exempt ``repair reset-state`` case where no
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
                reason_class=reason_class or "absent",
                recovered_bucket_id=recovered_bucket_id,
            )
        derived_reason = "readable" if envelope_readable else "unreadable"
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
        source: str = "aeat config repair reset-state",
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
        """

        fingerprint = self.fingerprint_state(reason_class=reason_class)
        self._emit_reset(fingerprint=fingerprint, actor=actor, source=source)
        self._objects.delete(_STATE_NAMESPACE, _STATE_OBJECT_KEY)
        _clear_output_language_cache()
        _logger.info("workflow state envelope reset; recovery route fired by operator")
        return fingerprint

    def update(self, fn: Callable[[WorkflowState], WorkflowState]) -> WorkflowState:
        """Load, transform, save, and return the updated state."""

        state = self.load()
        updated = fn(state)
        self.save(updated)
        return updated


class WorkflowRunRepository:
    """Encrypted SQL object repository for :class:`WorkflowResult` runs."""

    def __init__(self, *, objects: SecureObjectRepository | None = None) -> None:
        self._objects = objects or SecureObjectRepository()

    def save(self, result: WorkflowResult, *, runs_dir: Path | None = None) -> Path:
        """Persist one workflow result in the secure object backend."""

        run_id = _validate_run_id(result.run_id)
        marker_dir = runs_dir or Settings().aeat_workflow_runs_dir
        envelope = Envelope[WorkflowResult](
            schema_version=_RUN_VERSION,
            written_at=utc_now(),
            classification=SensitivityClass.FINANCIAL,
            payload=result,
        )
        self._objects.save(
            namespace=_RUN_NAMESPACE,
            object_key=run_id,
            classification=SensitivityClass.FINANCIAL,
            schema_version=_RUN_VERSION,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json().encode("utf-8"),
        )
        return marker_dir / run_id

    def load(self, run_id: str) -> WorkflowResult:
        """Load one persisted workflow result from the secure backend."""

        safe_run_id = _validate_run_id(run_id)
        record = self._objects.load(
            _RUN_NAMESPACE,
            safe_run_id,
            expected_class=SensitivityClass.FINANCIAL,
            max_supported_version=_RUN_VERSION,
        )
        if record is None:
            raise WorkflowError(f"workflow run not found: {safe_run_id}")
        envelope = Envelope[WorkflowResult].model_validate_json(record.payload.decode("utf-8"))
        if envelope.classification is not SensitivityClass.FINANCIAL:
            raise ClassificationError(
                f"workflow run has classification {envelope.classification}; "
                f"consumer expected {SensitivityClass.FINANCIAL}",
            )
        if envelope.schema_version > _RUN_VERSION:
            raise EnvelopeVersionError(
                f"workflow run is at version {envelope.schema_version}; consumer supports up to {_RUN_VERSION}",
            )
        return envelope.payload

    def list(self, *, since: date | None = None) -> tuple[WorkflowResult, ...]:
        """List persisted workflow runs newest-first, optionally filtered by date."""

        records = self._objects.list_records(
            _RUN_NAMESPACE,
            expected_class=SensitivityClass.FINANCIAL,
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
    """Return the repository bound to the active-bucket database.

    When an active profile bucket is present the repository is backed by
    the bucket's own encrypted database, resolved through
    :func:`~aeat.adapters.persistence.storage.runtime_repository.secure_object_repository_for_active_bucket`
    so the URL is derived from the live bucket path rather than the
    settings-override snapshot captured at test-fixture construction
    time. When no bucket is active the bare :class:`SecureObjectRepository`
    default is used (it will open the fallback database, consistent with
    the pre-active-profile bootstrap stage).
    """

    from ...adapters.persistence.storage.runtime_repository import (
        secure_object_repository_for_active_bucket,
    )
    from ...core._bucket_pointer_io import resolve_active_bucket_id

    bucket_id = resolve_active_bucket_id()
    if bucket_id is None:
        return WorkflowStateRepository()
    try:
        objects = secure_object_repository_for_active_bucket()
    except Exception:
        # If the bucket repository cannot be opened (e.g. session not yet
        # established during bootstrap), fall back to the bare repository
        # so callers that only need an absent-state result still succeed.
        _logger.debug(
            "workflow_state_repository: bucket repo unavailable, falling back to default",
            exc_info=True,
        )
        return WorkflowStateRepository()
    return WorkflowStateRepository(objects=objects)


def reset_workflow_state(
    *,
    actor: str = "aeat.application.workflow",
    source: str = "aeat config repair reset-state",
    reason_class: str | None = None,
) -> WorkflowStateResetFingerprint:
    """Module-level helper around :meth:`WorkflowStateRepository.reset_workflow_state`."""

    return workflow_state_repository().reset_workflow_state(
        actor=actor,
        source=source,
        reason_class=reason_class,
    )


def fingerprint_workflow_state(*, reason_class: str | None = None) -> WorkflowStateResetFingerprint:
    """Module-level helper around :meth:`WorkflowStateRepository.fingerprint_state`."""

    return workflow_state_repository().fingerprint_state(reason_class=reason_class)


def _validate_run_id(run_id: str) -> str:
    if "/" in run_id or "\\" in run_id:
        raise WorkflowError("run_id must not contain path separators")
    trimmed = run_id.strip()
    if not trimmed:
        raise WorkflowError("run_id must not be blank")
    return trimmed


def save_run(result: WorkflowResult, *, runs_dir: Path | None = None) -> Path:
    """Persist one workflow result in the secure object backend.

    ``runs_dir`` remains part of the API as a logical marker path for callers
    and tests, but no plaintext run file is written there.
    """

    return WorkflowRunRepository().save(result, runs_dir=runs_dir)


def load_run(run_id: str) -> WorkflowResult:
    """Load one persisted workflow result from the secure backend."""

    return WorkflowRunRepository().load(run_id)


def list_runs(*, since: date | None = None) -> tuple[WorkflowResult, ...]:
    """List persisted workflow runs newest-first, optionally filtered by date."""

    return WorkflowRunRepository().list(since=since)
