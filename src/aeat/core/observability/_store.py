"""Filesystem persistence for run traces and JSONL event logs.

One subdirectory per ``run_id`` under
:attr:`aeat.core.config.Settings.aeat_runs_dir`, containing
``trace.json`` and ``events.jsonl``. Both files round-trip through the
strict pydantic models in :mod:`aeat.core.observability._models`.

Run traces are DIAGNOSTIC class. The redaction rule set returned by
:func:`aeat.core.redaction.default_rules_for_class` for
:class:`~aeat.core.classification.SensitivityClass.DIAGNOSTIC` walks
every string leaf — NIFs SHA-256-prefixed, URLs reduced to host-only,
bearer-shaped tokens fingerprinted, opaque bearers fingerprinted —
before serialisation. The core redaction helper is imported lazily so
commands that never persist traces avoid resolving the rule registry on
import.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Never

from pydantic import ValidationError

from ..config import Settings, load_settings
from ..logging import get_logger
from ._errors import RunTracePersistenceError, RunTraceValidationError
from ._models import RunEvent, RunTrace
from ._redaction_rules import diagnostic_rules

_logger = get_logger(__name__)


_TRACE_FILENAME = "trace.json"
_EVENTS_FILENAME = "events.jsonl"

# Run ids are minted by :func:`aeat.core.observability._context._mint_run_id`
# as ``uuid4().hex[:16]``. Validate every run_id reaching the filesystem
# layer against the same shape so a crafted id (e.g. ``..`` or
# ``/etc/passwd``) cannot cause ``runs_dir / run_id`` to escape the
# configured runs directory.
_RUN_ID_PATTERN = re.compile(r"^[0-9a-f]{16}$")


def _raise_persistence_error(operation: str, target: Path, exc: OSError) -> Never:
    """Raise a registered observability persistence error from ``exc``."""
    raise RunTracePersistenceError(operation=operation, path=target) from exc


def _validate_run_id(run_id: str) -> str:
    """Return ``run_id`` if it matches the canonical shape, else raise.

    The canonical shape is 16 lowercase hex characters — the form
    minted by
    :func:`aeat.core.observability._context._mint_run_id`. Validating
    every id reaching this layer prevents path-traversal escapes
    through ``runs_dir / run_id``.

    Args:
        run_id: Candidate run identifier.

    Returns:
        The same ``run_id`` when it matches the canonical shape.

    Raises:
        RunTraceValidationError: When ``run_id`` is not a 16-character
            lowercase hex string.
    """
    if not _RUN_ID_PATTERN.fullmatch(run_id):
        raise RunTraceValidationError(
            f"invalid run_id {run_id!r}: expected 16 lowercase hex characters",
        )
    return run_id


def runs_dir(settings: Settings | None = None) -> Path:
    """Return the configured runs directory, creating it when absent.

    Args:
        settings: Optional :class:`aeat.core.config.Settings` override
            (used by tests). When ``None``, the active settings are
            loaded via :func:`aeat.core.config.load_settings`.

    Returns:
        Absolute path to the per-process runs root.
    """
    cfg = settings or load_settings()
    target = cfg.aeat_runs_dir
    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        _raise_persistence_error("runs_dir", target, exc)
    return target


def _run_dir(run_id: str, *, settings: Settings | None = None) -> Path:
    """Return the per-run directory, creating it when absent.

    Rejects ``run_id`` values that do not match the canonical minted
    shape so ``runs_dir / run_id`` cannot traverse out of the
    configured runs directory.

    Args:
        run_id: 16-char lowercase hex run identifier.
        settings: Optional :class:`aeat.core.config.Settings` override.

    Returns:
        Absolute path to the per-run subdirectory (created if absent).
    """
    _validate_run_id(run_id)
    target = runs_dir(settings) / run_id
    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        _raise_persistence_error("_run_dir", target, exc)
    return target


def save_trace(trace: RunTrace, *, settings: Settings | None = None) -> Path:
    """Persist a :class:`RunTrace` to ``<runs_dir>/<run_id>/trace.json``.

    Every string leaf passes through
    :func:`aeat.core.redaction.redact_structured` at DIAGNOSTIC class
    before serialisation so the on-disk record never carries a
    plaintext NIF, bearer token, or sensitive URL path even if a caller
    fed one into ``arguments``.

    Args:
        trace: The :class:`RunTrace` to persist.
        settings: Optional :class:`aeat.core.config.Settings` override.

    Returns:
        Absolute path of the written ``trace.json`` file.
    """
    from ..redaction import redact_structured

    target = _run_dir(trace.run_id, settings=settings) / _TRACE_FILENAME
    redacted = redact_structured(trace.model_dump(mode="json"), rules=diagnostic_rules())
    try:
        target.write_text(json.dumps(redacted, indent=2, sort_keys=True), encoding="utf-8")
    except OSError as exc:
        _raise_persistence_error("save_trace", target, exc)
    _logger.info(
        "save_trace: persisted run trace for run_id=%s outcome=%s at %s",
        trace.run_id,
        trace.outcome.value,
        target,
    )
    return target


def load_trace(run_id: str, *, settings: Settings | None = None) -> RunTrace:
    """Load and strictly validate a persisted :class:`RunTrace`.

    Read-only lookups do not create the per-run directory — a missing
    ``trace.json`` raises :exc:`RunTraceValidationError` without
    polluting the runs directory with an empty entry.

    Args:
        run_id: 16-char lowercase hex run identifier.
        settings: Optional :class:`aeat.core.config.Settings` override.

    Returns:
        The validated :class:`RunTrace`.

    Raises:
        RunTraceValidationError: When ``run_id`` has an invalid shape,
            when the file is missing, or when its contents fail strict
            validation.
    """
    _validate_run_id(run_id)
    target = runs_dir(settings) / run_id / _TRACE_FILENAME
    try:
        exists = target.exists()
    except OSError as exc:
        _raise_persistence_error("load_trace.exists", target, exc)
    if not exists:
        raise RunTraceValidationError(f"trace.json not found for run {run_id!r} at {target}")
    try:
        raw = target.read_text(encoding="utf-8")
    except OSError as exc:
        _raise_persistence_error("load_trace", target, exc)
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
    r"""Append a single :class:`RunEvent` line to the per-run ``events.jsonl``.

    ``newline=""`` pins the on-disk line terminator to ``\\n`` on every
    platform — mirroring
    :class:`aeat.core.observability._sink.JsonlRunSink` — so
    ``events.jsonl`` is byte-stable across Windows and POSIX writers.
    Every string leaf in the event is redacted at DIAGNOSTIC class
    before serialisation so the on-disk record stays free of plaintext
    NIFs / tokens / sensitive URLs.

    Args:
        run_id: Owning run identifier.
        event: The :class:`RunEvent` to append.
        settings: Optional :class:`aeat.core.config.Settings` override.

    Returns:
        Absolute path of the appended ``events.jsonl`` file.
    """
    from ..redaction import redact_structured

    target = _run_dir(run_id, settings=settings) / _EVENTS_FILENAME
    redacted = redact_structured(event.model_dump(mode="json"), rules=diagnostic_rules())
    line = json.dumps(redacted, sort_keys=True, separators=(",", ":")) + "\n"
    try:
        with target.open("a", encoding="utf-8", newline="") as handle:
            handle.write(line)
            handle.flush()
    except OSError as exc:
        _raise_persistence_error("save_events_append", target, exc)
    return target


def iter_events(
    run_id: str,
    *,
    settings: Settings | None = None,
) -> Iterator[RunEvent]:
    """Return an iterator of :class:`RunEvent` records from the per-run ``events.jsonl``.

    Streams records so callers processing a long-running run's event
    log can avoid holding the entire file in memory. The ``run_id`` is
    validated *eagerly* — before the iterator starts — so a bad id
    surfaces at the call site instead of on first iteration.

    Read-only: does not create a run directory when absent. A missing
    file yields no records.

    Args:
        run_id: 16-char lowercase hex run identifier.
        settings: Optional :class:`aeat.core.config.Settings` override.

    Returns:
        An iterator of :class:`RunEvent` records in append order.
    """
    _validate_run_id(run_id)
    target = runs_dir(settings) / run_id / _EVENTS_FILENAME

    def _stream() -> Iterator[RunEvent]:
        try:
            exists = target.exists()
        except OSError as exc:
            _raise_persistence_error("iter_events.exists", target, exc)
        if not exists:
            return
        try:
            with target.open("r", encoding="utf-8") as handle:
                for lineno, raw in enumerate(handle, start=1):
                    stripped = raw.strip()
                    if not stripped:
                        continue
                    try:
                        yield RunEvent.model_validate_json(stripped)
                    except ValidationError as exc:
                        raise RunTraceValidationError(
                            f"events.jsonl line {lineno} for run {run_id!r} failed strict validation: {exc}",
                        ) from exc
        except OSError as exc:
            _raise_persistence_error("iter_events", target, exc)

    return _stream()


def load_events(
    run_id: str,
    *,
    settings: Settings | None = None,
) -> tuple[RunEvent, ...]:
    """Load and strictly validate every JSONL event for a run.

    Thin wrapper over :func:`iter_events` that drains the iterator
    into a tuple. Prefer :func:`iter_events` for long-running traces
    where the whole log may exceed available memory.

    Read-only: does not create a run directory when absent.

    Args:
        run_id: 16-char lowercase hex run identifier.
        settings: Optional :class:`aeat.core.config.Settings` override.

    Returns:
        Tuple of every recorded :class:`RunEvent` in append order.
    """
    return tuple(iter_events(run_id, settings=settings))


def iter_runs(*, settings: Settings | None = None) -> Iterator[tuple[str, RunTrace]]:
    """Yield ``(run_id, RunTrace)`` pairs sorted by ``started_at`` descending.

    Directories without a valid ``trace.json`` — or whose name does not
    match the canonical ``run_id`` shape — are skipped silently. This
    lets crashed runs (no on-exit finaliser call) coexist with healthy
    ones rather than poisoning ``aeat run list``, and blocks any
    non-run artefacts that may have been dropped into the runs
    directory by hand.

    Args:
        settings: Optional :class:`aeat.core.config.Settings` override.

    Yields:
        ``(run_id, trace)`` pairs in newest-first order, where each
        trace is a :class:`RunTrace` loaded from the run directory.
    """
    base = runs_dir(settings)
    pairs: list[tuple[str, RunTrace]] = []
    try:
        entries = tuple(base.iterdir())
    except OSError as exc:
        _raise_persistence_error("iter_runs", base, exc)
    for entry in entries:
        try:
            is_dir = entry.is_dir()
        except OSError:
            _logger.warning("iter_runs: skipping unreadable entry %s", entry, exc_info=True)
            continue
        if not is_dir:
            _logger.debug("iter_runs: skipping non-directory entry %s", entry)
            continue
        if not _RUN_ID_PATTERN.fullmatch(entry.name):
            _logger.debug("iter_runs: skipping non-run directory %s", entry.name)
            continue
        trace_path = entry / _TRACE_FILENAME
        if not trace_path.exists():
            _logger.debug("iter_runs: skipping run directory %s without trace.json", entry.name)
            continue
        try:
            trace = RunTrace.model_validate_json(trace_path.read_text(encoding="utf-8"))
        except OSError:
            _logger.warning(
                "iter_runs: skipping run directory %s — trace.json could not be read",
                entry.name,
                exc_info=True,
            )
            continue
        except ValidationError:
            _logger.warning(
                "iter_runs: skipping run directory %s — trace.json failed strict validation",
                entry.name,
                exc_info=True,
            )
            continue
        pairs.append((entry.name, trace))
    pairs.sort(key=lambda item: item[1].started_at, reverse=True)
    yield from pairs


__all__ = [
    "iter_events",
    "iter_runs",
    "load_events",
    "load_trace",
    "runs_dir",
    "save_events_append",
    "save_trace",
]
