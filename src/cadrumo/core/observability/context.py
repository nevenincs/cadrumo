"""Contextvars-backed run context with nesting support and JSONL sink wiring.

Entering :func:`run_context` at the outermost CLI entry point mints a
fresh ``run_id``, fingerprints the corpus / db / cert state, attaches a
:class:`cadrumo.core.observability.sink.JsonlRunSink` to the root logger
for the duration of the block, emits a
:attr:`cadrumo.core.observability.models.RunEventKind.STEP_START` event,
and persists the final
:class:`cadrumo.core.observability.models.RunTrace` on exit. Nesting is
idempotent: an inner enter reuses the outer ``run_id`` and only pushes
a new step identifier.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Generator, Sequence
from contextlib import contextmanager
from contextvars import ContextVar, Token
from datetime import datetime

from pydantic import BaseModel

from ..config import load_settings
from ..identity.digest import ContentDigest, ContentDigestOrAbsent
from ..logging import attach_run_sink, detach_run_sink, get_logger
from ..models import STRICT_FROZEN_CONFIG
from ..time.clock import now
from .capture import CAPTURE_SINK
from .fingerprint import (
    compute_corpus_sha256,
    compute_data_root_sha256,
    read_cert_fingerprint,
)
from .models import (
    ArgumentRecord,
    RunEventKind,
    RunEventPayload,
    RunOutcome,
    RunTrace,
    StepBoundaryPayload,
)
from .sink import JsonlRunSink
from .store import EVENTS_FILENAME, run_dir, save_envelope, save_trace, validate_run_id

_log = get_logger(__name__)

_DEFAULT_INITIAL_STEP = "step-0"


class RunContextInfo(BaseModel):
    """Immutable bag of run-level metadata exposed to call sites.

    Yielded by :func:`run_context` so callers can stamp recorded events
    with the active ``run_id`` or surface it in user-facing output.

    Attributes:
        run_id: 16-char lowercase hex identifier for this run.
        entrypoint: Stable string identifying the CLI entry point
            (e.g. ``"program workflow run"``).
        started_at: Wall-clock UTC timestamp captured at run-context
            enter.
        arguments: Tuple of :class:`ArgumentRecord` capturing CLI flags and
            positional values for diagnostic correlation.
        corpus_sha256: Fingerprint of the effective :class:`Settings`
            configuration at enter time.
        db_sha256: Fingerprint of the canonical application data root
            (``Settings.cadrumo_local_storage_root``) at enter time,
            excluding regenerable cache subdirectories.
        cert_fingerprint: SHA-256 of the configured PKCS#12 certificate,
            or ``""`` when no cert path is configured.
        initial_step_id: Step identifier emitted with the first
            ``STEP_START`` boundary event.
    """

    model_config = STRICT_FROZEN_CONFIG

    run_id: str
    entrypoint: str
    started_at: datetime
    arguments: tuple[ArgumentRecord, ...]
    corpus_sha256: ContentDigest
    db_sha256: ContentDigest
    cert_fingerprint: ContentDigestOrAbsent
    initial_step_id: str


RUN_CONTEXT_VAR: ContextVar[RunContextInfo | None] = ContextVar(
    "_aeat_run_ctx",
    default=None,
)
"""Active :class:`RunContextInfo` for the current task / thread, or ``None``."""

STEP_CONTEXT_VAR: ContextVar[str | None] = ContextVar(
    "_aeat_step_ctx",
    default=None,
)
"""Active step identifier within the current run context, or ``None``."""


def _mint_run_id() -> str:
    """Return a fresh 16-character lowercase hex run identifier."""
    return uuid.uuid4().hex[:16]


def _build_initial_context(
    *,
    entrypoint: str,
    arguments: Sequence[ArgumentRecord],
    run_id: str | None,
    step_id: str | None,
) -> RunContextInfo:
    """Construct the :class:`RunContextInfo` for an outermost enter.

    A caller-supplied ``run_id`` is validated against the canonical
    shape (16 lowercase hex) by
    :func:`cadrumo.core.observability.store.validate_run_id` before
    anything touches the filesystem — this prevents a malicious or
    buggy caller from escaping the configured runs directory through
    inputs like ``"../etc"``.
    """
    effective_run_id = validate_run_id(run_id) if run_id is not None else _mint_run_id()
    # `load_settings()` honours `override_settings`; bare `Settings()`
    # bypasses the context-var so test-side corpus-sha overrides never
    # propagate to the run-context fingerprint.
    settings = load_settings()
    started_at = now()
    return RunContextInfo(
        run_id=effective_run_id,
        entrypoint=entrypoint,
        started_at=started_at,
        arguments=tuple(arguments),
        corpus_sha256=compute_corpus_sha256(settings),
        db_sha256=compute_data_root_sha256(settings),
        cert_fingerprint=read_cert_fingerprint(),
        initial_step_id=step_id or _DEFAULT_INITIAL_STEP,
    )


def _step_payload(step_id: str, label: str) -> RunEventPayload:
    """Build a :class:`RunEventPayload` carrying a :class:`StepBoundaryPayload`."""
    return RunEventPayload(step=StepBoundaryPayload(step_id=step_id, label=label))


def _emit_nested_step_end(
    record_event: Callable[..., object],
    *,
    outer: RunContextInfo,
    nested_step: str,
    entrypoint: str,
) -> None:
    """Best-effort close for a nested step, without masking its body."""
    try:
        record_event(
            RunEventKind.STEP_END,
            payload=_step_payload(nested_step, label=entrypoint),
            module=__name__,
        )
    except Exception:
        # A recorder/sink failure here must never mask the yielded body's
        # outcome. Broad catch because the recorder swallows any sink-level
        # disk / serialisation error and re-raises an opaque type (logged with
        # traceback above).
        _log.warning(
            "failed to record nested STEP_END (run=%s step=%s)",
            outer.run_id,
            nested_step,
            exc_info=True,
        )


@contextmanager
def _nested_run_context(
    outer: RunContextInfo,
    *,
    entrypoint: str,
    step_id: str | None,
    record_event: Callable[..., object],
) -> Generator[RunContextInfo]:
    """Push and pop one nested step while reusing the outer run metadata."""
    nested_step = step_id or f"{outer.initial_step_id}.{_mint_run_id()[:8]}"
    step_token = STEP_CONTEXT_VAR.set(nested_step)
    try:
        record_event(
            RunEventKind.STEP_START,
            payload=_step_payload(nested_step, label=entrypoint),
            module=__name__,
        )
        try:
            yield outer
        finally:
            _emit_nested_step_end(
                record_event,
                outer=outer,
                nested_step=nested_step,
                entrypoint=entrypoint,
            )
    finally:
        STEP_CONTEXT_VAR.reset(step_token)


@contextmanager
def _outer_step_context(
    info: RunContextInfo,
    *,
    record_event: Callable[..., object],
    outcome: list[RunOutcome],
) -> Generator[None]:
    """Emit outer step boundaries and retain a pessimistic outcome default."""
    record_event(
        RunEventKind.STEP_START,
        payload=_step_payload(info.initial_step_id, label=info.entrypoint),
        module=__name__,
    )
    try:
        yield
        outcome[0] = RunOutcome.OK
    finally:
        try:
            record_event(
                RunEventKind.STEP_END,
                payload=_step_payload(info.initial_step_id, label=info.entrypoint),
                module=__name__,
            )
        except Exception:
            # A failed STEP_END emit must not mask the yielded exception (if
            # any) nor the outcome already captured.
            _log.warning("failed to record STEP_END for run %s", info.run_id, exc_info=True)


def _persist_outer_trace(info: RunContextInfo, outcome: RunOutcome) -> Exception | None:
    """Persist the final trace and return a failure for post-cleanup handling."""
    try:
        trace = RunTrace(
            run_id=info.run_id,
            started_at=info.started_at,
            finished_at=now(),
            entrypoint=info.entrypoint,
            arguments=info.arguments,
            corpus_sha256=info.corpus_sha256,
            db_sha256=info.db_sha256,
            cert_fingerprint=info.cert_fingerprint,
            outcome=outcome,
        )
        save_trace(trace)
    except Exception as exc:
        _log.warning("failed to persist RunTrace for run %s", info.run_id, exc_info=True)
        return exc
    return None


def _persist_outer_envelope(
    info: RunContextInfo,
    *,
    owns_capture: bool,
    envelope_sink: list[dict[str, object]],
) -> None:
    """Best-effort persist the last envelope owned by the outer context."""
    if not owns_capture or not envelope_sink:
        return
    try:
        save_envelope(info.run_id, dict(envelope_sink[-1]))
    except Exception:
        # An envelope-persist failure must never mask the run outcome. Only
        # the owning context persists; a reused sink belongs to the outer scope.
        _log.warning("failed to persist result envelope for run %s", info.run_id, exc_info=True)


def _detach_outer_sink(sink: JsonlRunSink, *, run_id: str) -> None:
    """Detach a run sink without allowing teardown logging to escape."""
    try:
        detach_run_sink(sink)
    except Exception:
        _log.warning("failed to detach sink for run %s", run_id, exc_info=True)


def _reset_outer_context(
    *,
    step_token: Token[str | None],
    run_token: Token[RunContextInfo | None],
    capture_token: Token[list[dict[str, object]] | None] | None,
) -> None:
    """Restore context variables after the sink is detached."""
    STEP_CONTEXT_VAR.reset(step_token)
    RUN_CONTEXT_VAR.reset(run_token)
    if capture_token is not None:
        CAPTURE_SINK.reset(capture_token)


def _close_outer_sink(sink: JsonlRunSink, *, run_id: str) -> None:
    """Close a run sink without masking its completed run."""
    try:
        sink.close()
    except Exception:
        # Sink teardown is infallible-by-policy: a close failure cannot be
        # allowed to mask the run's real outcome.
        _log.warning("failed to close sink for run %s", run_id, exc_info=True)


def _finalize_outer_context(
    info: RunContextInfo,
    *,
    sink: JsonlRunSink,
    owns_capture: bool,
    envelope_sink: list[dict[str, object]],
    capture_token: Token[list[dict[str, object]] | None] | None,
    run_token: Token[RunContextInfo | None],
    step_token: Token[str | None],
    outcome: RunOutcome,
) -> None:
    """Persist outer artifacts, release resources, then surface clean-run errors."""
    persistence_error = _persist_outer_trace(info, outcome)
    _persist_outer_envelope(info, owns_capture=owns_capture, envelope_sink=envelope_sink)
    _detach_outer_sink(sink, run_id=info.run_id)
    _reset_outer_context(
        step_token=step_token,
        run_token=run_token,
        capture_token=capture_token,
    )
    _close_outer_sink(sink, run_id=info.run_id)
    if persistence_error is not None and outcome is RunOutcome.OK:
        raise persistence_error


@contextmanager
def _outer_run_context(info: RunContextInfo, record_event: Callable[..., object]) -> Generator[RunContextInfo]:
    """Own the outer sink, context variables, boundary events, and teardown."""
    target = run_dir(info.run_id)
    sink = JsonlRunSink(target / EVENTS_FILENAME, run_id=info.run_id)

    # Arm result-envelope capture for the run so the emitted ``SchemaEnvelope``
    # is persisted as run evidence. Nesting-aware: an outer capture scope owns
    # its sink and persistence.
    pre_existing_capture = CAPTURE_SINK.get()
    owns_capture = pre_existing_capture is None
    envelope_sink: list[dict[str, object]] = [] if owns_capture else pre_existing_capture
    capture_token = CAPTURE_SINK.set(envelope_sink) if owns_capture else None

    # Bind contextvars before attaching the sink. This keeps records emitted by
    # another thread during attachment from carrying a stale run id.
    run_token = RUN_CONTEXT_VAR.set(info)
    step_token = STEP_CONTEXT_VAR.set(info.initial_step_id)
    attach_run_sink(sink)
    outcome = [RunOutcome.FAILED]
    try:
        with _outer_step_context(record_event=record_event, info=info, outcome=outcome):
            yield info
    finally:
        _finalize_outer_context(
            info,
            sink=sink,
            owns_capture=owns_capture,
            envelope_sink=envelope_sink,
            capture_token=capture_token,
            run_token=run_token,
            step_token=step_token,
            outcome=outcome[0],
        )


@contextmanager
def run_context(
    *,
    entrypoint: str,
    arguments: Sequence[ArgumentRecord] = (),
    run_id: str | None = None,
    step_id: str | None = None,
) -> Generator[RunContextInfo]:
    """Enter a run context, emitting ``STEP_START`` / ``STEP_END`` boundary events.

    The outermost enter mints a ``run_id``, fingerprints the corpus /
    db / cert state, attaches a
    :class:`cadrumo.core.observability.sink.JsonlRunSink` to the root
    logger, emits a ``STEP_START`` event, and on exit emits a
    ``STEP_END`` plus persists the finalised
    :class:`cadrumo.core.observability.models.RunTrace` (even on
    exception, with :attr:`RunOutcome.FAILED`).

    Inner enters reuse the outer ``run_id`` and only push a new
    ``step_id``, so callers can wrap higher-level commands without
    every callee knowing whether a run is already active.

    Args:
        entrypoint: Stable string identifying the CLI entry point
            (e.g. ``"cadrumo workflow run"``).
        arguments: Sequence of :class:`ArgumentRecord` capturing the
            CLI flags and values for diagnostics.
        run_id: Optional caller-supplied ``run_id`` for correlation.
        step_id: Optional initial step identifier; defaults to
            ``"step-0"`` for the outermost enter and a derived nested
            id for inner enters.

    Yields:
        The active :class:`RunContextInfo` for the block.

    Raises:
        Exception: The error captured during the ``save_trace`` call, re-raised
            when trace persistence fails and the yielded body completed
            successfully (outcome ``OK``).
    """
    # Local imports break the recorder ↔ context cycle.
    from .recorder import record_event

    outer = RUN_CONTEXT_VAR.get(None)
    if outer is not None:
        with _nested_run_context(
            outer,
            entrypoint=entrypoint,
            step_id=step_id,
            record_event=record_event,
        ):
            yield outer
        return

    info = _build_initial_context(
        entrypoint=entrypoint,
        arguments=arguments,
        run_id=run_id,
        step_id=step_id,
    )
    with _outer_run_context(info, record_event):
        yield info


__all__ = [
    "RUN_CONTEXT_VAR",
    "STEP_CONTEXT_VAR",
    "RunContextInfo",
    "run_context",
]
