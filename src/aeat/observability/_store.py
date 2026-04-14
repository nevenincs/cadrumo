"""Filesystem persistence for run traces and JSONL event logs.

One subdirectory per ``run_id`` under :attr:`Settings.aeat_runs_dir`,
containing ``trace.json`` and ``events.jsonl``. Both files round-trip
through the strict pydantic models in :mod:`aeat.observability._models`.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from pydantic import ValidationError

from aeat.config import Settings, load_settings
from aeat.observability._errors import RunTraceValidationError
from aeat.observability._models import RunEvent, RunTrace

_TRACE_FILENAME = "trace.json"
_EVENTS_FILENAME = "events.jsonl"


def runs_dir(settings: Settings | None = None) -> Path:
    """Return the configured runs directory, creating it if absent.

    Args:
        settings: Optional :class:`Settings` override (used by tests).
    """
    cfg = settings or load_settings()
    target = cfg.aeat_runs_dir
    target.mkdir(parents=True, exist_ok=True)
    return target


def _run_dir(run_id: str, *, settings: Settings | None = None) -> Path:
    """Return the per-run directory, creating it if absent."""
    target = runs_dir(settings) / run_id
    target.mkdir(parents=True, exist_ok=True)
    return target


def save_trace(trace: RunTrace, *, settings: Settings | None = None) -> Path:
    """Persist a :class:`RunTrace` to ``<runs_dir>/<run_id>/trace.json``."""
    target = _run_dir(trace.run_id, settings=settings) / _TRACE_FILENAME
    target.write_text(trace.model_dump_json(indent=2), encoding="utf-8")
    return target


def load_trace(run_id: str, *, settings: Settings | None = None) -> RunTrace:
    """Load and strictly validate a persisted :class:`RunTrace`."""
    target = _run_dir(run_id, settings=settings) / _TRACE_FILENAME
    if not target.exists():
        raise RunTraceValidationError(f"trace.json not found for run {run_id!r} at {target}")
    raw = target.read_text(encoding="utf-8")
    try:
        return RunTrace.model_validate_json(raw)
    except ValidationError as exc:
        raise RunTraceValidationError(
            f"trace.json for run {run_id!r} failed strict validation: {exc}",
        ) from exc


def save_events_append(
    run_id: str,
    event: RunEvent,
    *,
    settings: Settings | None = None,
) -> Path:
    """Append a single :class:`RunEvent` line to the per-run ``events.jsonl``."""
    target = _run_dir(run_id, settings=settings) / _EVENTS_FILENAME
    line = event.model_dump_json() + "\n"
    with target.open("a", encoding="utf-8") as handle:
        handle.write(line)
        handle.flush()
    return target


def load_events(
    run_id: str,
    *,
    settings: Settings | None = None,
) -> tuple[RunEvent, ...]:
    """Load and strictly validate every JSONL event for a run.

    Raises:
        RunTraceValidationError: If the file is missing or any line
            fails strict validation.
    """
    target = _run_dir(run_id, settings=settings) / _EVENTS_FILENAME
    if not target.exists():
        return ()
    events: list[RunEvent] = []
    with target.open("r", encoding="utf-8") as handle:
        for lineno, raw in enumerate(handle, start=1):
            stripped = raw.strip()
            if not stripped:
                continue
            try:
                events.append(RunEvent.model_validate_json(stripped))
            except ValidationError as exc:
                raise RunTraceValidationError(
                    f"events.jsonl line {lineno} for run {run_id!r} failed strict validation: {exc}",
                ) from exc
    return tuple(events)


def iter_runs(*, settings: Settings | None = None) -> Iterator[tuple[str, RunTrace]]:
    """Yield ``(run_id, RunTrace)`` pairs sorted by ``started_at`` descending.

    Directories without a valid ``trace.json`` are skipped silently —
    this lets crashed runs (no on-exit finalizer call) coexist with
    healthy ones rather than poisoning ``aeat run list``.
    """
    base = runs_dir(settings)
    pairs: list[tuple[str, RunTrace]] = []
    for entry in base.iterdir():
        if not entry.is_dir():
            continue
        trace_path = entry / _TRACE_FILENAME
        if not trace_path.exists():
            continue
        try:
            trace = RunTrace.model_validate_json(trace_path.read_text(encoding="utf-8"))
        except ValidationError:
            continue
        pairs.append((entry.name, trace))
    pairs.sort(key=lambda item: item[1].started_at, reverse=True)
    yield from pairs


__all__ = [
    "iter_runs",
    "load_events",
    "load_trace",
    "runs_dir",
    "save_events_append",
    "save_trace",
]
