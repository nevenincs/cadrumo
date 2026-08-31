"""Filesystem persistence for run traces and JSONL event logs.

One subdirectory per ``run_id`` under
:attr:`core.config.Settings.cadrumo_runs_dir`, containing
``trace.json`` and ``events.jsonl``. Both files round-trip through the
strict pydantic models in :mod:`core.observability.models`.

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
import threading
from collections.abc import Iterator, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Never

from pydantic import ValidationError

from ..atomic_write import atomic_write_text
from ..config import Settings, load_settings
from ..directory_scan import scan_directory
from ..logging import get_logger
from ..paths import directory_byte_total, select_filesystem_retention_survivors
from ..storage_taxonomy import StorageCategory
from ..storage_taxonomy_locations import storage_path
from ..time.clock import now
from .errors import RunTracePersistenceError, RunTraceValidationError
from .models import RUN_ID_PATTERN, RunEvent, RunTrace
from .redaction_rules import diagnostic_rules

_logger = get_logger(__name__)


TRACE_FILENAME = "trace.json"
EVENTS_FILENAME = "events.jsonl"
ENVELOPE_FILENAME = "envelope.json"
"""Per-run artifact leaf names, owned by this module (see the ``run_trace`` /
``run_events`` / ``run_envelope`` entries in
:data:`~cadrumo.adapters.persistence.storage.STORAGE_PATH_DEFINITIONS`, each
declared ``owner="cadrumo.core.observability"`` and interpolating these
constants into their grammar rather than re-typing the names)."""

# Both the public direct append path and JsonlRunSink write the same per-run
# JSONL artefacts.  One process-wide lock keeps their independent file handles
# from interleaving or losing lines under concurrent worker activity.
_EVENTS_APPEND_LOCK = threading.Lock()


# Run ids are minted by :func:`core.observability.context._mint_run_id`
# as ``uuid4().hex[:16]``. Validate every run_id reaching the filesystem
# layer against the same shape so a crafted id (e.g. ``..`` or
# ``/etc/passwd``) cannot cause ``runs_dir / run_id`` to escape the
# configured runs directory.
def _raise_persistence_error(operation: str, target: Path, exc: OSError) -> Never:
    """Raise a registered observability persistence error from ``exc``."""
    raise RunTracePersistenceError(operation=operation, path=target) from exc


def _validate_run_id(run_id: str) -> str:
    """Return ``run_id`` if it matches the canonical shape, else raise.

    The canonical shape is 16 lowercase hex characters — the form
    minted by
    :func:`core.observability.context._mint_run_id`. Validating
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
    if re.fullmatch(RUN_ID_PATTERN, run_id) is None:
        raise RunTraceValidationError(
            f"invalid run_id {run_id!r}: expected 16 lowercase hex characters",
        )
    return run_id


def _require_trace_identity(trace: RunTrace, *, expected_run_id: str) -> RunTrace:
    """Return ``trace`` only when its embedded and filesystem identities agree."""
    if trace.run_id != expected_run_id:
        raise RunTraceValidationError(
            f"trace.json for run {expected_run_id!r} contains embedded run_id {trace.run_id!r}",
        )
    return trace


def runs_dir(settings: Settings | None = None) -> Path:
    """Return the configured runs directory. Resolution only; never creates it.

    Resolved through :func:`~core.storage_path` for
    ``StorageCategory.RUNS`` rather than by reading ``cadrumo_runs_dir``
    directly here. Both answer the same today, because the settings field is
    what the accessor consults first -- but only one of them stays correct if
    the member's resolution ever gains a case.

    A pure path resolver. Materialisation is a write-side concern: the one
    production writer (:func:`_run_dir`) creates the full ``<runs_dir>/<run_id>``
    chain itself via ``mkdir(parents=True)`` when it stages a run for writing,
    which brings this root into existence as a side effect of that single
    ``mkdir`` call -- it does not depend on this function creating anything.
    A read must never materialise a directory for what it failed to find, so
    every read-only caller (:func:`load_trace`, :func:`load_envelope_document`,
    :func:`iter_events`, :func:`iter_runs`, :func:`prune_run_traces`) treats an
    absent root exactly like an empty one rather than relying on this resolver
    to conjure it first.

    Args:
        settings: Optional :class:`core.config.Settings` override
            (used by tests). When ``None``, the active settings are
            loaded via :func:`core.config.load_settings`.

    Returns:
        Absolute path to the per-process runs root. Not guaranteed to exist.
    """
    return storage_path(StorageCategory.RUNS, settings=settings)


def _run_dir(run_id: str, *, settings: Settings | None = None) -> Path:
    """Return the per-run directory, creating it (and the runs root) when absent.

    The one production write path that materialises anything under the runs
    root: ``mkdir(parents=True)`` creates the per-run subdirectory and, as
    part of the same call, any missing ancestor -- including the runs root
    itself -- in one step. Rejects ``run_id`` values that do not match the
    canonical minted shape so ``runs_dir / run_id`` cannot traverse out of the
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
    from ..redaction.rules import redact_structured

    target = _run_dir(trace.run_id, settings=settings) / TRACE_FILENAME
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

    Read-only: does not create the per-run directory, nor the runs root
    itself. A missing ``trace.json`` raises :exc:`RunTraceValidationError`
    without polluting the runs directory with an empty entry.

    Args:
        run_id: 16-char lowercase hex run identifier.
        settings: Optional :class:`core.config.Settings` override.

    Returns:
        The validated :class:`RunTrace`.

    Raises:
        RunTraceValidationError: When ``run_id`` has an invalid shape,
            when the file is missing, when its contents fail strict
            validation, or when its embedded identity names another run.
    """
    _validate_run_id(run_id)
    target = runs_dir(settings) / run_id / TRACE_FILENAME
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
        trace = RunTrace.model_validate_json(raw)
    except ValidationError as exc:
        raise RunTraceValidationError(
            f"trace.json for run {run_id!r} failed strict validation: {exc}",
        ) from exc
    return _require_trace_identity(trace, expected_run_id=run_id)


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
    target = _run_dir(run_id, settings=settings) / ENVELOPE_FILENAME
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

    Read-only: does not create the per-run directory, nor the runs root
    itself. Returns the raw mapping; type it with
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
    target = runs_dir(settings) / run_id / ENVELOPE_FILENAME
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
    if not isinstance(parsed, Mapping):
        raise RunTraceValidationError(
            f"envelope.json for run {run_id!r} must be a JSON object, got {type(parsed).__name__}",
        )
    document: dict[str, object] = {}
    for key, value in parsed.items():
        if not isinstance(key, str):
            raise RunTraceValidationError(
                f"envelope.json for run {run_id!r} contains a non-string object key",
            )
        document[key] = value
    return document


def save_events_append(
    run_id: str,
    event: RunEvent,
    *,
    settings: Settings | None = None,
) -> Path:
    r"""Append a single :class:`RunEvent` line to the per-run ``events.jsonl``.

    ``newline=""`` pins the on-disk line terminator to ``\\n`` on every
    platform — mirroring
    :class:`core.observability.sink.JsonlRunSink` — so
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
    from ..redaction.rules import redact_structured

    target = _run_dir(run_id, settings=settings) / EVENTS_FILENAME
    redacted = redact_structured(event.model_dump(mode="json"), rules=diagnostic_rules())
    line = json.dumps(redacted, sort_keys=True, separators=(",", ":")) + "\n"
    try:
        with _EVENTS_APPEND_LOCK, target.open("a", encoding="utf-8", newline="") as handle:
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

    Read-only: does not create a run directory when absent, nor the runs
    root itself. A missing file yields no records.

    Args:
        run_id: 16-char lowercase hex run identifier.
        settings: Optional :class:`core.config.Settings` override.

    Returns:
        An iterator of :class:`RunEvent` records in append order.
    """
    _validate_run_id(run_id)
    target = runs_dir(settings) / run_id / EVENTS_FILENAME

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

    Directories without a valid ``trace.json``, whose name does not match the
    canonical ``run_id`` shape, or whose embedded trace identity does not
    match their directory are skipped. This lets crashed runs (no on-exit
    finaliser call) coexist with healthy ones rather than poisoning a run
    listing, and blocks any non-run artefacts that may have been dropped into
    the runs directory by hand.

    Read-only: does not create the runs directory. No run has ever been saved
    on a fresh install or an isolated test root, so an absent runs directory
    is treated exactly like an empty one -- yielding nothing -- rather than
    raising.

    Args:
        settings: Optional :class:`core.config.Settings` override.

    Yields:
        ``(run_id, trace)`` pairs in newest-first order, where each
        trace is a :class:`RunTrace` loaded from the run directory.
    """
    base = runs_dir(settings)
    pairs: list[tuple[str, RunTrace]] = []
    if not base.is_dir():
        return
    try:
        entries = scan_directory(base, require_root=True)
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
        if re.fullmatch(RUN_ID_PATTERN, entry.name) is None:
            _logger.debug("iter_runs: skipping non-run directory %s", entry.name)
            continue
        trace_path = entry / TRACE_FILENAME
        if not trace_path.exists():
            _logger.debug("iter_runs: skipping run directory %s without trace.json", entry.name)
            continue
        try:
            trace = RunTrace.model_validate_json(trace_path.read_text(encoding="utf-8"))
            trace = _require_trace_identity(trace, expected_run_id=entry.name)
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
        except RunTraceValidationError as exc:
            _logger.warning("iter_runs: skipping run directory %s — %s", entry.name, exc)
            continue
        pairs.append((entry.name, trace))
    pairs.sort(key=lambda item: item[1].started_at, reverse=True)
    yield from pairs


def _run_dir_total_bytes(entry: Path) -> int:
    """Return the total file size (bytes) under one run directory.

    Delegates to the shared :func:`~cadrumo.core.paths.directory_byte_total`
    walker in tolerant mode: a file that cannot be stat'd counts as zero so
    the size pass never crashes the prune it feeds.
    """
    total_bytes, _file_count = directory_byte_total(entry, tolerate_errors=True)
    return total_bytes


def prune_run_traces(
    *,
    retention_days: int | None = None,
    max_total_bytes: int | None = None,
    settings: Settings | None = None,
) -> int:
    """Delete run directories beyond the retention window or the size ceiling.

    Gives the run-trace store a declared retention lifecycle instead of one
    subdirectory accumulating per run forever. Two independent bounds apply
    in order, each delegating its survivor decision to the shared
    :func:`~cadrumo.core.paths.select_filesystem_retention_survivors`
    selector while this function keeps its own ``rmtree`` side effect and
    its own newest-directory-never-size-pruned rule:

    1. **Age** — run directories whose modification time (last write) is older
       than ``retention_days`` are removed, so crashed runs that never produced
       a valid ``trace.json`` are pruned too rather than accumulating
       unreadable.
    2. **Total size** — if the surviving run directories still exceed
       ``max_total_bytes`` on disk, the oldest directories are removed until
       the store fits under the ceiling. The newest run directory is always
       kept (``protect_newest=1``), so the trace whose save triggered the
       prune survives even when it alone exceeds the ceiling.

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
        entries = scan_directory(base, require_root=True)
    except OSError:
        _logger.debug("prune_run_traces: runs directory not enumerable at %s", base, exc_info=True)
        return 0

    candidates: list[tuple[Path, float]] = []
    for entry in entries:
        try:
            if not entry.is_dir() or re.fullmatch(RUN_ID_PATTERN, entry.name) is None:
                continue
            candidates.append((entry, entry.stat().st_mtime))
        except OSError:
            _logger.debug("prune_run_traces: could not stat run directory %s", entry, exc_info=True)
    # Pre-sort by path, descending: the selector's stable, timestamp-only sort
    # then preserves this order for any mtime tie (two run directories saved
    # within the same filesystem timestamp tick), reproducing the prior
    # ``(mtime, Path)`` tuple sort's implicit path tie-break for "which
    # directory counts as newest".
    candidates.sort(key=lambda pair: pair[0], reverse=True)

    age_survivors, age_removed = select_filesystem_retention_survivors(
        candidates,
        timestamp=lambda pair: datetime.fromtimestamp(pair[1], tz=UTC),
        cutoff=cutoff,
    )
    removed_by_age = _rmtree_pairs(age_removed)

    _size_survivors, size_removed = select_filesystem_retention_survivors(
        age_survivors,
        timestamp=lambda pair: pair[1],
        max_total_bytes=effective_max_total_bytes,
        size_fn=lambda pair: _run_dir_total_bytes(pair[0]),
        protect_newest=1,
    )
    removed_by_size = _rmtree_pairs(size_removed)
    return removed_by_age + removed_by_size


def _rmtree_pairs(pairs: list[tuple[Path, float]]) -> int:
    """Best-effort ``rmtree`` over ``(directory, mtime)`` pairs; return the removed count."""
    removed = 0
    for entry, _mtime in pairs:
        try:
            shutil.rmtree(entry)
            removed += 1
        except OSError:
            _logger.debug("prune_run_traces: could not prune run directory %s", entry, exc_info=True)
    return removed


__all__ = [
    "ENVELOPE_FILENAME",
    "EVENTS_FILENAME",
    "TRACE_FILENAME",
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
