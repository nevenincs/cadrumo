"""Filesystem persistence for run traces and JSONL event logs.

One subdirectory per ``run_id`` under
:attr:`core.config.Settings.cadrumo_runs_dir`, containing
``trace.json`` and ``events.jsonl``. Both files round-trip through the
strict pydantic models in :mod:`core.observability._models`.

Run traces are DIAGNOSTIC class. The redaction rule set returned by
:func:`core.redaction.default_rules_for_class` for
:class:`~core.classification.SensitivityClass.DIAGNOSTIC` walks
every string leaf — NIFs SHA-256-prefixed, URLs reduced to host-only,
bearer-shaped tokens fingerprinted, opaque bearers fingerprinted —
before serialisation. The core redaction helper is imported lazily so
commands that never persist traces avoid resolving the rule registry on
import.
"""

from __future__ import annotations

import json
import re
import shutil
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Never

from pydantic import ValidationError

from ..atomic_write import atomic_write_text
from ..config import Settings, load_settings
from ..logging import get_logger
from ..time import now
from ._errors import RunTracePersistenceError, RunTraceValidationError
from ._models import RunEvent, RunTrace
from ._redaction_rules import diagnostic_rules

_logger = get_logger(__name__)


_TRACE_FILENAME = "trace.json"
_EVENTS_FILENAME = "events.jsonl"
_ENVELOPE_FILENAME = "envelope.json"

# Run ids are minted by :func:`core.observability._context._mint_run_id`
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
    :func:`core.observability._context._mint_run_id`. Validating
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
        settings: Optional :class:`core.config.Settings` override
            (used by tests). When ``None``, the active settings are
            loaded via :func:`core.config.load_settings`.

    Returns:
        Absolute path to the per-process runs root.
    """
    cfg = settings or load_settings()
    target = cfg.cadrumo_runs_dir
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
        settings: Optional :class:`core.config.Settings` override.

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
    :func:`core.redaction.redact_structured` at DIAGNOSTIC class
    before serialisation so the on-disk record never carries a
    plaintext NIF, bearer token, or sensitive URL path even if a caller
    fed one into ``arguments``.

    Args:
        trace: The :class:`RunTrace` to persist.
        settings: Optional :class:`core.config.Settings` override.

    Returns:
        Absolute path of the written ``trace.json`` file.
    """
    from ..redaction import redact_structured

    target = _run_dir(trace.run_id, settings=settings) / _TRACE_FILENAME
    redacted = redact_structured(trace.model_dump(mode="json"), rules=diagnostic_rules())
    try:
        atomic_write_text(target, json.dumps(redacted, indent=2, sort_keys=True), encoding="utf-8")
    except OSError as exc:
        _raise_persistence_error("save_trace", target, exc)
    _logger.info(
        "save_trace: persisted run trace for run_id=%s outcome=%s at %s",
        trace.run_id,
        trace.outcome.value,
        target,
    )
    # Enforce the run-trace retention lifecycle here: a trace save happens once
    # at run finalisation, so pruning on this path bounds the runs directory
    # without a separate scheduler. Best-effort - a prune failure must never
    # fail the save that just succeeded.
    try:
        prune_run_traces(settings=settings)
    except OSError:
        _logger.debug("save_trace: post-save run-trace retention prune failed", exc_info=True)
    return target


def load_trace(run_id: str, *, settings: Settings | None = None) -> RunTrace:
    """Load and strictly validate a persisted :class:`RunTrace`.

    Read-only lookups do not create the per-run directory — a missing
    ``trace.json`` raises :exc:`RunTraceValidationError` without
    polluting the runs directory with an empty entry.

    Args:
        run_id: 16-char lowercase hex run identifier.
        settings: Optional :class:`core.config.Settings` override.

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


def save_envelope(
    run_id: str,
    document: dict[str, object],
    *,
    settings: Settings | None = None,
) -> Path:
    """Persist an emitted envelope document to ``<runs_dir>/<run_id>/envelope.json``.

    The document is the verbatim, already-CLI-redacted
    :class:`~core.json_contract.SchemaEnvelope` mapping captured by
    :func:`core.observability.capture_envelopes` during the run. It
    is stored key-sorted so the on-disk artifact is byte-stable, and it
    is the golden expectation a later :func:`replay_run` asserts against.
    Re-validation into a typed envelope happens on load via
    :func:`core.observability.validate_captured_envelope`; this
    writer stays free of any JSON-contract dependency.

    Args:
        run_id: 16-char lowercase hex run identifier.
        document: The emitted envelope mapping to persist.
        settings: Optional :class:`core.config.Settings` override.

    Returns:
        Absolute path of the written ``envelope.json`` file.
    """
    target = _run_dir(run_id, settings=settings) / _ENVELOPE_FILENAME
    try:
        atomic_write_text(
            target,
            json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    except OSError as exc:
        _raise_persistence_error("save_envelope", target, exc)
    return target


def load_envelope_document(
    run_id: str,
    *,
    settings: Settings | None = None,
) -> dict[str, object]:
    """Load the persisted emitted-envelope document for a run.

    Read-only: does not create the per-run directory. Returns the raw
    mapping; type it with
    :func:`core.observability.validate_captured_envelope`.

    Args:
        run_id: 16-char lowercase hex run identifier.
        settings: Optional :class:`core.config.Settings` override.

    Returns:
        The persisted envelope mapping.

    Raises:
        RunTraceValidationError: When ``run_id`` has an invalid shape,
            the file is missing, or its contents are not a JSON object.
    """
    _validate_run_id(run_id)
    target = runs_dir(settings) / run_id / _ENVELOPE_FILENAME
    try:
        exists = target.exists()
    except OSError as exc:
        _raise_persistence_error("load_envelope_document.exists", target, exc)
    if not exists:
        raise RunTraceValidationError(
            f"envelope.json not found for run {run_id!r} at {target}",
        )
    try:
        raw = target.read_text(encoding="utf-8")
    except OSError as exc:
        _raise_persistence_error("load_envelope_document", target, exc)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RunTraceValidationError(
            f"envelope.json for run {run_id!r} is not valid JSON: {exc}",
        ) from exc
    if not isinstance(parsed, dict):
        raise RunTraceValidationError(
            f"envelope.json for run {run_id!r} must be a JSON object, got {type(parsed).__name__}",
        )
    return parsed


def save_events_append(
    run_id: str,
    event: RunEvent,
    *,
    settings: Settings | None = None,
) -> Path:
    r"""Append a single :class:`RunEvent` line to the per-run ``events.jsonl``.

    ``newline=""`` pins the on-disk line terminator to ``\\n`` on every
    platform — mirroring
    :class:`core.observability._sink.JsonlRunSink` — so
    ``events.jsonl`` is byte-stable across Windows and POSIX writers.
    Every string leaf in the event is redacted at DIAGNOSTIC class
    before serialisation so the on-disk record stays free of plaintext
    NIFs / tokens / sensitive URLs.

    Args:
        run_id: Owning run identifier.
        event: The :class:`RunEvent` to append.
        settings: Optional :class:`core.config.Settings` override.

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
        settings: Optional :class:`core.config.Settings` override.

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
        settings: Optional :class:`core.config.Settings` override.

    Returns:
        Tuple of every recorded :class:`RunEvent` in append order.
    """
    return tuple(iter_events(run_id, settings=settings))


def iter_runs(*, settings: Settings | None = None) -> Iterator[tuple[str, RunTrace]]:
    """Yield ``(run_id, RunTrace)`` pairs sorted by ``started_at`` descending.

    Directories without a valid ``trace.json`` — or whose name does not
    match the canonical ``run_id`` shape — are skipped silently. This
    lets crashed runs (no on-exit finaliser call) coexist with healthy
    ones rather than poisoning a run listing, and blocks any
    non-run artefacts that may have been dropped into the runs
    directory by hand.

    Args:
        settings: Optional :class:`core.config.Settings` override.

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


def _run_dir_total_bytes(entry: Path) -> int:
    """Return the total file size (bytes) under one run directory.

    Best-effort: a file that cannot be stat'd counts as zero so the size
    pass never crashes the prune it feeds.
    """
    total = 0
    try:
        for candidate in entry.rglob("*"):
            try:
                if candidate.is_file():
                    total += candidate.stat().st_size
            except OSError:
                _logger.debug("prune_run_traces: could not stat %s", candidate, exc_info=True)
    except OSError:
        _logger.debug("prune_run_traces: could not walk run directory %s", entry, exc_info=True)
    return total


def prune_run_traces(
    *,
    retention_days: int | None = None,
    max_total_bytes: int | None = None,
    settings: Settings | None = None,
) -> int:
    """Delete run directories beyond the retention window or the size ceiling.

    Gives the run-trace store a declared retention lifecycle instead of one
    subdirectory accumulating per run forever. Two independent bounds apply
    in order:

    1. **Age** — run directories whose modification time (last write) is older
       than ``retention_days`` are removed, so crashed runs that never produced
       a valid ``trace.json`` are pruned too rather than accumulating
       unreadable.
    2. **Total size** — if the surviving run directories still exceed
       ``max_total_bytes`` on disk, the oldest directories are removed until
       the store fits under the ceiling. The newest run directory is always
       kept, so the trace whose save triggered the prune survives even when it
       alone exceeds the ceiling.

    ``retention_days`` defaults to the centralized
    :attr:`~core.config.Settings.cadrumo_runs_retention_days` and
    ``max_total_bytes`` to
    :attr:`~core.config.Settings.cadrumo_runs_max_total_bytes`. Entirely
    best-effort: a directory that cannot be enumerated, stat'd, or removed is
    logged and skipped, never raised -- pruning must not crash the caller.

    Args:
        retention_days: Age cutoff in days; run directories whose mtime is
            strictly older are removed. Defaults to the centralized setting.
        max_total_bytes: Total on-disk size ceiling for the run-trace store.
            Defaults to the centralized setting.
        settings: Optional :class:`core.config.Settings` override.

    Returns:
        Number of run directories removed.
    """
    cfg = settings or load_settings()
    effective_retention_days = retention_days if retention_days is not None else cfg.cadrumo_runs_retention_days
    effective_max_total_bytes = max_total_bytes if max_total_bytes is not None else cfg.cadrumo_runs_max_total_bytes
    cutoff = now() - timedelta(days=effective_retention_days)
    base = runs_dir(cfg)
    try:
        entries = tuple(base.iterdir())
    except OSError:
        _logger.debug("prune_run_traces: runs directory not enumerable at %s", base, exc_info=True)
        return 0
    removed_by_age, survivors = _prune_run_dirs_by_age(entries, cutoff=cutoff)
    removed_by_size = _prune_run_dirs_by_size(survivors, max_total_bytes=effective_max_total_bytes)
    return removed_by_age + removed_by_size


def _prune_run_dirs_by_age(
    entries: tuple[Path, ...],
    *,
    cutoff: datetime,
) -> tuple[int, list[tuple[float, Path]]]:
    """Remove run directories older than ``cutoff``; return (removed, survivors).

    Survivors carry their mtime for the subsequent size-bound pass. Best-effort:
    a directory that cannot be stat'd or removed is logged and skipped.
    """
    removed = 0
    survivors: list[tuple[float, Path]] = []
    for entry in entries:
        try:
            if not entry.is_dir() or not _RUN_ID_PATTERN.fullmatch(entry.name):
                continue
            mtime = entry.stat().st_mtime
            modified = datetime.fromtimestamp(mtime, tz=UTC)
            if modified >= cutoff:
                survivors.append((mtime, entry))
                continue
            shutil.rmtree(entry)
            removed += 1
        except OSError:
            _logger.debug("prune_run_traces: could not prune run directory %s", entry, exc_info=True)
    return removed, survivors


def _prune_run_dirs_by_size(
    survivors: list[tuple[float, Path]],
    *,
    max_total_bytes: int,
) -> int:
    """Remove oldest survivors until the store fits under ``max_total_bytes``.

    The newest run directory is never size-pruned, so the trace whose save
    triggered the prune survives even when it alone exceeds the ceiling.
    """
    survivors.sort()  # oldest mtime first
    sized = [(entry, _run_dir_total_bytes(entry)) for _, entry in survivors]
    total_bytes = sum(size for _, size in sized)
    removed = 0
    for entry, size in sized[:-1]:  # the newest directory is never size-pruned
        if total_bytes <= max_total_bytes:
            break
        try:
            shutil.rmtree(entry)
        except OSError:
            _logger.debug("prune_run_traces: could not prune run directory %s", entry, exc_info=True)
            continue
        removed += 1
        total_bytes -= size
    return removed


__all__ = [
    "iter_events",
    "iter_runs",
    "load_envelope_document",
    "load_events",
    "load_trace",
    "prune_run_traces",
    "runs_dir",
    "save_envelope",
    "save_events_append",
    "save_trace",
]
