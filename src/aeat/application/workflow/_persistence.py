"""Files-only persistence for :class:`aeat.application.workflow.WorkflowResult`.

Each run is persisted as an ``Envelope[WorkflowResult]`` ciphertext
envelope at :attr:`aeat.adapters.persistence.storage.SensitivityClass.AUDIT`
via :func:`aeat.adapters.persistence.storage.save_encrypted_envelope`.
The on-disk file carries no plaintext NIFs, casilla values, or filing
identifiers.

Storage imports are deferred inside each function body so the workflow
package's import chain doesn't pull Alembic plugin discovery into CLI
commands that never persist a run.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

from pydantic import ValidationError

from ...core.errors import AeatError
from ...core.logging import get_logger
from ...core.paths import resolve_record_json_path
from ._errors import WorkflowError
from ._models import WorkflowResult

_logger = get_logger(__name__)

_WORKFLOW_RUN_VERSION = 1
_WORKFLOW_RUN_ENVELOPE_SUFFIX = ".envelope.json"
_WORKFLOW_HKDF_CONTEXT = b"aeat.application.workflow.run.v1"


def _envelope_path_for(runs_dir: Path, run_id: str) -> Path:
    """Return the canonical envelope path for ``run_id``.

    Path-traversal-shaped ids are rejected via
    :func:`resolve_record_json_path` before composition.
    """
    resolve_record_json_path(runs_dir, run_id, context="workflow run id")
    return runs_dir / f"{run_id}{_WORKFLOW_RUN_ENVELOPE_SUFFIX}"


def save_run(result: WorkflowResult, *, runs_dir: Path) -> Path:
    """Persist ``result`` as a ciphertext envelope under ``runs_dir``.

    Args:
        result: The :class:`WorkflowResult` to persist.
        runs_dir: Target directory. Created if missing.

    Returns:
        The path of the envelope file written.
    """
    from ...adapters.persistence.storage import (
        Envelope,
        SensitivityClass,
        exclusive_file_lock,
        save_encrypted_envelope,
    )
    from ...adapters.persistence.storage.crypto._encrypted_columns import _resolve_master_key_provider

    runs_dir.mkdir(parents=True, exist_ok=True)
    try:
        target = _envelope_path_for(runs_dir, result.run_id)
    except ValueError as exc:
        raise WorkflowError(str(exc)) from exc
    envelope = Envelope[WorkflowResult](
        schema_version=_WORKFLOW_RUN_VERSION,
        written_at=datetime.now(UTC),
        classification=SensitivityClass.AUDIT,
        payload=result,
    )
    # Acquire the writer-canonical sidecar lock so concurrent
    # ``aeat security rotate-master-key`` cannot race the run write.
    # The lock target matches what
    # ``RotationPlanEntry.lock_path_for`` resolves to for a multi-
    # file consumer with ``envelope_suffix=".envelope.json"`` (strip
    # the suffix, append ``.lock``); the thus
    # engages OS-level serialisation between rotation and writer.
    lock_target = target.with_name(
        target.name[: -len(_WORKFLOW_RUN_ENVELOPE_SUFFIX)] + ".lock",
    )
    try:
        with exclusive_file_lock(lock_target):
            save_encrypted_envelope(
                envelope,
                target,
                master_key_provider=_resolve_master_key_provider(),
                hkdf_context=_WORKFLOW_HKDF_CONTEXT,
            )
    except OSError:
        _logger.error("workflow: failed to persist run %s to %s", result.run_id, target, exc_info=True)
        raise
    _logger.info("workflow: persisted run %s to %s", result.run_id, target)
    return target


def load_run(run_id: str, *, runs_dir: Path) -> WorkflowResult:
    """Load and return the :class:`WorkflowResult` for ``run_id``.

    Args:
        run_id: The stable run identifier.
        runs_dir: Directory containing persisted runs.

    Returns:
        The reconstructed :class:`WorkflowResult`.

    Raises:
        WorkflowError: If no run with ``run_id`` exists in ``runs_dir``.
    """
    from ...adapters.persistence.storage import (
        Envelope,
        SensitivityClass,
        load_encrypted_envelope,
    )
    from ...adapters.persistence.storage.crypto._encrypted_columns import _resolve_master_key_provider

    try:
        envelope_path = _envelope_path_for(runs_dir, run_id)
    except ValueError as exc:
        raise WorkflowError(str(exc)) from exc
    if not envelope_path.exists():
        raise WorkflowError(f"no persisted workflow run with id {run_id!r}")
    envelope = load_encrypted_envelope(
        envelope_path,
        Envelope[WorkflowResult],
        expected_class=SensitivityClass.AUDIT,
        master_key_provider=_resolve_master_key_provider(),
        hkdf_context=_WORKFLOW_HKDF_CONTEXT,
        max_supported_version=_WORKFLOW_RUN_VERSION,
    )
    return envelope.payload


def list_runs(
    *,
    runs_dir: Path,
    since: date | None = None,
) -> tuple[WorkflowResult, ...]:
    """Return every persisted :class:`WorkflowResult` in ``runs_dir``.

    Args:
        runs_dir: Directory to enumerate. Missing directories yield
            an empty tuple.
        since: Optional lower-bound ``date``.

    Returns:
        A tuple of results sorted by ``started_at`` descending.
    """
    from ...adapters.persistence.storage import (
        Envelope,
        SensitivityClass,
        load_encrypted_envelope,
    )
    from ...adapters.persistence.storage.crypto._encrypted_columns import _resolve_master_key_provider

    if not runs_dir.exists():
        return ()
    results: list[WorkflowResult] = []
    for path in sorted(runs_dir.glob(f"*{_WORKFLOW_RUN_ENVELOPE_SUFFIX}")):
        try:
            envelope = load_encrypted_envelope(
                path,
                Envelope[WorkflowResult],
                expected_class=SensitivityClass.AUDIT,
                master_key_provider=_resolve_master_key_provider(),
                hkdf_context=_WORKFLOW_HKDF_CONTEXT,
                max_supported_version=_WORKFLOW_RUN_VERSION,
            )
        except (OSError, ValueError, ValidationError, AeatError):  # pragma: no cover - defensive
            _logger.warning("workflow: skipping unreadable run %s", path, exc_info=True)
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
