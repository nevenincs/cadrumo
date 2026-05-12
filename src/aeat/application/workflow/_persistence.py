"""Encrypted persistence for workflow state and workflow runs."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Self

from ...adapters.persistence.storage.envelope._envelope import Envelope
from ...adapters.persistence.storage.errors import ClassificationError, EnvelopeVersionError
from ...adapters.persistence.storage.sql import SecureObjectRepository
from ...core.classification import SensitivityClass
from ...core.config import Settings
from ...core.logging import get_logger
from ._errors import WorkflowError
from ._models import WorkflowResult, WorkflowState, utc_now

_logger = get_logger(__name__)

_STATE_VERSION = 1
_STATE_NAMESPACE = "aeat.workflow"
_STATE_OBJECT_KEY = "state"
_RUN_VERSION = 1
_RUN_NAMESPACE = "aeat.application.workflow.runs"


class WorkflowStateRepository:
    """Encrypted SQL object repository for :class:`WorkflowState`."""

    def __init__(self) -> None:
        self._objects = SecureObjectRepository()

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> Self:
        del settings
        return cls()

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
        envelope = Envelope[WorkflowState].model_validate_json(record.payload.decode("utf-8"))
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

        envelope = Envelope[WorkflowState](
            schema_version=_STATE_VERSION,
            written_at=utc_now(),
            classification=SensitivityClass.FINANCIAL,
            payload=state.model_copy(update={"updated_at": utc_now()}),
        )
        self._objects.save(
            namespace=_STATE_NAMESPACE,
            object_key=_STATE_OBJECT_KEY,
            classification=SensitivityClass.FINANCIAL,
            schema_version=_STATE_VERSION,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json().encode("utf-8"),
        )
        _logger.debug("persisted workflow state to secure backend")

    def update(self, fn: Callable[[WorkflowState], WorkflowState]) -> WorkflowState:
        """Load, transform, save, and return the updated state."""

        state = self.load()
        updated = fn(state)
        self.save(updated)
        return updated


def workflow_state_repository(settings: Settings | None = None) -> WorkflowStateRepository:
    """Return the repository bound to the configured run-state directory."""

    return WorkflowStateRepository.from_settings(settings)


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

    run_id = _validate_run_id(result.run_id)
    marker_dir = runs_dir or Settings().aeat_workflow_runs_dir
    envelope = Envelope[WorkflowResult](
        schema_version=_RUN_VERSION,
        written_at=utc_now(),
        classification=SensitivityClass.FINANCIAL,
        payload=result,
    )
    SecureObjectRepository().save(
        namespace=_RUN_NAMESPACE,
        object_key=run_id,
        classification=SensitivityClass.FINANCIAL,
        schema_version=_RUN_VERSION,
        written_at=envelope.written_at,
        payload=envelope.model_dump_json().encode("utf-8"),
    )
    return marker_dir / run_id


def load_run(run_id: str, *, runs_dir: Path | None = None) -> WorkflowResult:
    """Load one persisted workflow result from the secure backend."""

    del runs_dir
    safe_run_id = _validate_run_id(run_id)
    record = SecureObjectRepository().load(
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


def list_runs(*, runs_dir: Path | None = None, since: date | None = None) -> tuple[WorkflowResult, ...]:
    """List persisted workflow runs newest-first, optionally filtered by date."""

    del runs_dir
    records = SecureObjectRepository().list_records(
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
