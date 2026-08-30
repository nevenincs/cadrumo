"""Concrete encrypted persistence adapter for application workflow state and runs."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeGuard

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ...application.workflow.errors import WorkflowError
from ...application.workflow.persistence import (
    WorkflowPersistencePort,
    WorkflowSecureObjectStorePort,
    WorkflowStateStorageProbe,
)
from ...application.workflow.run_models import WorkflowResult
from ...application.workflow.state_models import WorkflowState
from ...core import ABSENT_SECURE_OBJECT_REVISION_ID, SecureObjectWrite
from ...core.classification import SensitivityClass
from ...core.logging import get_logger
from ...core.time import now as utc_now
from ...domain.buckets.event import BucketEvent
from ...domain.buckets.event_repository import append_bucket_event
from .profile.buckets import BucketEventHistoryRepository
from .storage import (
    WORKFLOW_RUN_NAMESPACE,
    WORKFLOW_STATE_NAMESPACE,
    ClassificationError,
    Envelope,
    EnvelopeVersionError,
    SecretStoreError,
    SecureObjectRepository,
    SecureObjectRevisionConflictError,
    StorageError,
    inner_envelope_classification_is_expected,
    inner_envelope_version_is_current,
    secure_object_repository_for_active_bucket,
    secure_object_repository_for_cold_bootstrap_state,
)
from .storage.crypto.encrypted_columns import secure_object_key_digest

_logger = get_logger(__name__)

_STATE_VERSION = WORKFLOW_STATE_NAMESPACE.schema_version
_STATE_NAMESPACE = WORKFLOW_STATE_NAMESPACE.namespace
_STATE_OBJECT_KEY = WORKFLOW_STATE_NAMESPACE.require_default_object_key()
_STATE_SENSITIVITY = WORKFLOW_STATE_NAMESPACE.sensitivity
_RUN_VERSION = WORKFLOW_RUN_NAMESPACE.schema_version
_RUN_NAMESPACE = WORKFLOW_RUN_NAMESPACE.namespace
_RUN_SENSITIVITY = WORKFLOW_RUN_NAMESPACE.sensitivity


class _WorkflowRunEnvelopeHeader(BaseModel):
    """Version and classification inspected before the typed run payload."""

    model_config = ConfigDict(strict=True, frozen=True)

    schema_version: int = Field(ge=1)
    classification: SensitivityClass


def _secure_objects(store: WorkflowSecureObjectStorePort) -> SecureObjectRepository:
    """Narrow the structural application handle to this adapter's concrete store."""
    if not isinstance(store, SecureObjectRepository):
        raise TypeError("workflow secure-object store is not owned by the persistence adapter")
    return store


def _clear_output_language_cache() -> None:
    try:
        from ...core.i18n import clear_output_language_cache
    except Exception:  # pragma: no cover - cache invalidation must never block persistence
        _logger.debug("workflow persistence could not import i18n cache invalidator", exc_info=True)
        return
    clear_output_language_cache()


def _validate_workflow_run_envelope(payload: bytes) -> Envelope[WorkflowResult]:
    """Validate one workflow-run envelope against the exact current contract."""
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


class _PersistenceWorkflow:
    """Implement workflow persistence through the canonical encrypted object store."""

    def __init__(
        self,
        *,
        active_store_factory: Callable[[], WorkflowSecureObjectStorePort],
        cold_bootstrap_store_factory: Callable[[], WorkflowSecureObjectStorePort],
    ) -> None:
        self._active_store_factory = active_store_factory
        self._cold_bootstrap_store_factory = cold_bootstrap_store_factory

    def active_store(self) -> WorkflowSecureObjectStorePort:
        return self._active_store_factory()

    def cold_bootstrap_store(self) -> WorkflowSecureObjectStorePort:
        return self._cold_bootstrap_store_factory()

    def load_state(self, store: WorkflowSecureObjectStorePort) -> tuple[WorkflowState, str]:
        record = store.load(
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

    def prepare_state_write(
        self,
        state: WorkflowState,
        *,
        expected_revision_id: str | None,
    ) -> SecureObjectWrite:
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

    def save_writes(self, store: WorkflowSecureObjectStorePort, writes: tuple[SecureObjectWrite, ...]) -> None:
        store.save_many(writes)
        _clear_output_language_cache()

    def probe_state(self, store: WorkflowSecureObjectStorePort) -> WorkflowStateStorageProbe:
        try:
            metadata = store.peek_metadata(_STATE_NAMESPACE, _STATE_OBJECT_KEY)
        except StorageError:
            return WorkflowStateStorageProbe(metadata=None, state=None, envelope_readable=True)
        try:
            state, _revision_id = self.load_state(store)
        except (
            WorkflowError,
            ClassificationError,
            EnvelopeVersionError,
            ValidationError,
            SecretStoreError,
        ):
            state = None
            envelope_readable = False
        else:
            envelope_readable = True
        return WorkflowStateStorageProbe(
            metadata=metadata,
            state=state,
            envelope_readable=envelope_readable,
        )

    def delete_state(self, store: WorkflowSecureObjectStorePort) -> None:
        store.delete(_STATE_NAMESPACE, _STATE_OBJECT_KEY)
        _clear_output_language_cache()

    def is_revision_conflict(self, error: BaseException) -> TypeGuard[SecureObjectRevisionConflictError]:
        return isinstance(error, SecureObjectRevisionConflictError)

    def prepare_bucket_event_write(
        self,
        store: WorkflowSecureObjectStorePort,
        events: tuple[BucketEvent, ...],
    ) -> SecureObjectWrite:
        repository = BucketEventHistoryRepository(objects=_secure_objects(store))
        catalogue, revision_id = repository.load_revisioned()
        for event in events:
            catalogue = append_bucket_event(catalogue, event)
        return repository.to_secure_object_write(
            catalogue,
            expected_revision_id=revision_id,
        )

    def save_run(self, store: WorkflowSecureObjectStorePort, result: WorkflowResult) -> None:
        envelope = Envelope[WorkflowResult](
            schema_version=_RUN_VERSION,
            written_at=utc_now(),
            classification=_RUN_SENSITIVITY,
            payload=result,
        )
        store.save(
            namespace=_RUN_NAMESPACE,
            object_key=result.run_id,
            classification=_RUN_SENSITIVITY,
            schema_version=_RUN_VERSION,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json().encode("utf-8"),
        )

    def load_run(self, store: WorkflowSecureObjectStorePort, run_id: str) -> WorkflowResult:
        record = store.load(
            _RUN_NAMESPACE,
            run_id,
            expected_class=_RUN_SENSITIVITY,
            max_supported_version=_RUN_VERSION,
        )
        if record is None:
            raise WorkflowError(
                translated_message="application.workflow.errors.run_not_found",
                context={"run_id": run_id},
            )
        envelope = _validate_workflow_run_envelope(record.payload)
        if envelope.payload.run_id != run_id:
            raise WorkflowError(
                translated_message="application.workflow.errors.run_identity_mismatch",
                context={"run_id": run_id},
            )
        return envelope.payload

    def list_runs(self, store: WorkflowSecureObjectStorePort) -> tuple[WorkflowResult, ...]:
        runs: list[WorkflowResult] = []
        for record in store.list_records(
            _RUN_NAMESPACE,
            expected_class=_RUN_SENSITIVITY,
            max_supported_version=_RUN_VERSION,
        ):
            envelope = _validate_workflow_run_envelope(record.payload)
            result = envelope.payload
            if secure_object_key_digest(result.run_id) != record.object_key:
                raise WorkflowError(
                    translated_message="application.workflow.errors.run_identity_mismatch",
                    context={"run_id": result.run_id},
                )
            runs.append(result)
        return tuple(runs)


def build_workflow_persistence_port() -> WorkflowPersistencePort:
    """Build the stateless concrete workflow persistence adapter."""
    return _PersistenceWorkflow(
        active_store_factory=secure_object_repository_for_active_bucket,
        cold_bootstrap_store_factory=secure_object_repository_for_cold_bootstrap_state,
    )


__all__ = ["build_workflow_persistence_port"]
