"""Secure persistence for :class:`aeat.application.workflow.WorkflowResult`.

Workflow runs contain casilla values, filing identifiers, and run
diagnostics. Runs are stored as encrypted byte objects in the primary
SQL backend at AUDIT sensitivity; no plaintext workflow JSON or
envelope file lands on disk.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

from pydantic import ValidationError

from ...adapters.persistence.storage import Envelope, SensitivityClass, safe_repository_id
from ...adapters.persistence.storage.errors import ClassificationError, EnvelopeVersionError
from ...adapters.persistence.storage.sql import SecureObjectRepository
from ...core.errors import AeatError
from ...core.logging import get_logger
from ._errors import WorkflowError
from ._models import WorkflowResult

_logger = get_logger(__name__)

_WORKFLOW_RUN_VERSION = 1
_WORKFLOW_NAMESPACE = "aeat.application.workflow.runs"


def _object_path_for(run_id: str) -> Path:
    """Return a logical object marker for ``run_id``."""

    safe_repository_id(run_id, context="workflow run id")
    return Path("db://secure_objects") / _WORKFLOW_NAMESPACE / run_id


def save_run(result: WorkflowResult, *, runs_dir: Path) -> Path:
    """Persist ``result`` as an encrypted database object.

    ``runs_dir`` is accepted by callers that still carry environment
    settings, but the persistence location is the secure SQL backend.
    """

    del runs_dir
    try:
        safe_repository_id(result.run_id, context="workflow run id")
    except ValueError as exc:
        raise WorkflowError(str(exc)) from exc
    envelope = Envelope[WorkflowResult](
        schema_version=_WORKFLOW_RUN_VERSION,
        written_at=datetime.now(UTC),
        classification=SensitivityClass.AUDIT,
        payload=result,
    )
    SecureObjectRepository().save(
        namespace=_WORKFLOW_NAMESPACE,
        object_key=result.run_id,
        classification=SensitivityClass.AUDIT,
        schema_version=_WORKFLOW_RUN_VERSION,
        written_at=envelope.written_at,
        payload=envelope.model_dump_json().encode("utf-8"),
    )
    _logger.info("workflow: persisted run %s to secure database", result.run_id)
    return _object_path_for(result.run_id)


def load_run(run_id: str, *, runs_dir: Path) -> WorkflowResult:
    """Load and return the :class:`WorkflowResult` for ``run_id``."""

    del runs_dir
    try:
        safe_repository_id(run_id, context="workflow run id")
    except ValueError as exc:
        raise WorkflowError(str(exc)) from exc
    record = SecureObjectRepository().load(
        _WORKFLOW_NAMESPACE,
        run_id,
        expected_class=SensitivityClass.AUDIT,
        max_supported_version=_WORKFLOW_RUN_VERSION,
    )
    if record is None:
        raise WorkflowError(f"no persisted workflow run with id {run_id!r}")
    envelope = Envelope[WorkflowResult].model_validate_json(record.payload.decode("utf-8"))
    if envelope.classification is not SensitivityClass.AUDIT:
        raise ClassificationError(
            f"workflow run {run_id} has classification {envelope.classification}; "
            f"consumer expected {SensitivityClass.AUDIT}",
        )
    if envelope.schema_version > _WORKFLOW_RUN_VERSION:
        raise EnvelopeVersionError(
            f"workflow run {run_id} is at version {envelope.schema_version}; "
            f"consumer supports up to {_WORKFLOW_RUN_VERSION}",
        )
    return envelope.payload


def list_runs(
    *,
    runs_dir: Path,
    since: date | None = None,
) -> tuple[WorkflowResult, ...]:
    """Return every persisted :class:`WorkflowResult` in the secure backend."""

    del runs_dir
    objects = SecureObjectRepository()
    results: list[WorkflowResult] = []
    for record in objects.list_records(
        _WORKFLOW_NAMESPACE,
        expected_class=SensitivityClass.AUDIT,
        max_supported_version=_WORKFLOW_RUN_VERSION,
    ):
        try:
            envelope = Envelope[WorkflowResult].model_validate_json(record.payload.decode("utf-8"))
        except (ValueError, ValidationError, AeatError):  # pragma: no cover - defensive
            _logger.warning("workflow: skipping unreadable run %s", record.object_key.hex(), exc_info=True)
            continue
        result = envelope.payload
        if since is not None and result.started_at.date() < since:
            continue
        results.append(result)
    results.sort(key=_started_at_key, reverse=True)
    return tuple(results)


def _started_at_key(result: WorkflowResult) -> datetime:
    """Sort key helper. Factored for deterministic tie-breaking."""

    return result.started_at
