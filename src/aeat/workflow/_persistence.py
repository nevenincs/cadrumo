"""Files-only persistence for :class:`aeat.workflow.WorkflowResult`.

v1 of the workflow engine persists each run as a single JSON file
under ``settings.aeat_workflow_runs_dir``. The storage layer (#10)
will take over in a follow-up; until then, the JSON file shape is
authoritative and is defined by the strict pydantic
:class:`WorkflowResult` model.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from .._paths import resolve_record_json_path
from ..logging import get_logger
from ._errors import WorkflowError
from ._models import WorkflowResult

_logger = get_logger(__name__)


def save_run(result: WorkflowResult, *, runs_dir: Path) -> Path:
    """Write ``result`` as pretty JSON under ``runs_dir``.

    Args:
        result: The :class:`WorkflowResult` to persist.
        runs_dir: Target directory. Created if missing.

    Returns:
        The path of the file written.
    """
    runs_dir.mkdir(parents=True, exist_ok=True)
    try:
        target = resolve_record_json_path(runs_dir, result.run_id, context="workflow run id")
    except ValueError as exc:
        raise WorkflowError(str(exc)) from exc
    target.write_text(result.model_dump_json(indent=2), encoding="utf-8")
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
    try:
        target = resolve_record_json_path(runs_dir, run_id, context="workflow run id")
    except ValueError as exc:
        raise WorkflowError(str(exc)) from exc
    if not target.exists():
        raise WorkflowError(f"no persisted workflow run with id {run_id!r}")
    return WorkflowResult.model_validate_json(target.read_text(encoding="utf-8"))


def list_runs(
    *,
    runs_dir: Path,
    since: date | None = None,
) -> tuple[WorkflowResult, ...]:
    """Return every persisted :class:`WorkflowResult` in ``runs_dir``.

    Args:
        runs_dir: Directory to enumerate. Missing directories yield
            an empty tuple.
        since: Optional lower-bound ``date``. Only runs whose
            ``started_at.date()`` is on or after ``since`` are
            returned.

    Returns:
        A tuple of results sorted by ``started_at`` descending.
        Corrupt records are skipped with a warning log — a malformed
        file must never break the list command for healthy records.
    """
    if not runs_dir.exists():
        return ()
    results: list[WorkflowResult] = []
    for path in sorted(runs_dir.glob("*.json")):
        try:
            result = WorkflowResult.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover - defensive
            _logger.warning("workflow: skipping unreadable run %s: %s", path, exc)
            continue
        if since is not None and result.started_at.date() < since:
            continue
        results.append(result)
    results.sort(key=_started_at_key, reverse=True)
    return tuple(results)


def _started_at_key(result: WorkflowResult) -> datetime:
    """Sort key helper. Factored for deterministic tie-breaking."""
    return result.started_at
