"""Contextvars-backed run context with nesting support and JSONL sink wiring.

Entering :func:`run_context` at the outermost CLI entry point mints a
fresh ``run_id``, fingerprints the corpus / db / cert state, attaches a
:class:`aeat.core.observability._sink.JsonlRunSink` to the root logger
for the duration of the block, emits a
:attr:`aeat.core.observability._models.RunEventKind.STEP_START` event,
and persists the final
:class:`aeat.core.observability._models.RunTrace` on exit. Nesting is
idempotent: an inner enter reuses the outer ``run_id`` and only pushes
a new step identifier.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime

from pydantic import BaseModel

from ...core import STRICT_FROZEN_CONFIG
from ..config import PROJECT_ROOT, load_settings
from ..logging import attach_run_sink, detach_run_sink, get_logger
from ..time._clock import now
from ._fingerprint import (
    compute_corpus_sha256,
    compute_db_sha256,
    read_cert_fingerprint,
)
from ._models import (
    ArgumentRecord,
    RunEventKind,
    RunEventPayload,
    RunOutcome,
    RunTrace,
    StepBoundaryPayload,
)
from ._sink import JsonlRunSink
from ._store import _run_dir, _validate_run_id, save_trace

_log = get_logger(__name__)

_DEFAULT_INITIAL_STEP = "step-0"
_EVENTS_FILENAME = "events.jsonl"


class RunContextInfo(BaseModel):
    """Immutable bag of run-level metadata exposed to call sites.

    Yielded by :func:`run_context` so callers can stamp recorded events
    with the active ``run_id`` or surface it in user-facing output.

    Attributes:
        run_id: 16-char lowercase hex identifier for this run.
        entrypoint: Stable string identifying the CLI entry point
            (e.g. ``"aeat workflow run"``).
        started_at: Wall-clock UTC timestamp captured at run-context
            enter.
        arguments: Tuple of :class:`ArgumentRecord` capturing the CLI
            flags / positional values for replay.
        corpus_sha256: Fingerprint of ``.vault/`` plus :class:`Settings`
            plus ``env/.env`` at enter time.
        db_sha256: Fingerprint of the local ``var/`` state tree at
            enter time, excluding cache subdirectories.
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
    corpus_sha256: str
    db_sha256: str
    cert_fingerprint: str
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


def current_run_context() -> RunContextInfo | None:
    """Return the :class:`RunContextInfo` bound to the current task, if any."""
    return RUN_CONTEXT_VAR.get(None)


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
    :func:`aeat.core.observability._store._validate_run_id` before
    anything touches the filesystem — this prevents a malicious or
    buggy caller from escaping the configured runs directory through
    inputs like ``"../etc"``.
    """
    effective_run_id = _validate_run_id(run_id) if run_id is not None else _mint_run_id()
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
        corpus_sha256=compute_corpus_sha256(PROJECT_ROOT / ".vault", settings),
        db_sha256=compute_db_sha256(PROJECT_ROOT / "var"),
        cert_fingerprint=read_cert_fingerprint(),
        initial_step_id=step_id or _DEFAULT_INITIAL_STEP,
    )


def _step_payload(step_id: str, label: str) -> RunEventPayload:
    """Build a :class:`RunEventPayload` carrying a :class:`StepBoundaryPayload`."""
    return RunEventPayload(step=StepBoundaryPayload(step_id=step_id, label=label))


def _resolve_replay_of() -> str | None:
    """Return the active replay source run id when it is a valid 16-hex token."""
    from ..config import load_settings

    try:
        replay_of_env = load_settings().aeat_replay_active or None
    except (KeyError, ValueError, AttributeError):
        _log.debug(
            "run_context: replay marker resolution failed; replay_of omitted",
            exc_info=True,
        )
        return None
    if not replay_of_env or len(replay_of_env) != 16:
        return None
    try:
        int(replay_of_env, 16)
    except ValueError:
        return None
    return replay_of_env.lower()


@contextmanager
def run_context(
    *,
    entrypoint: str,
    arguments: Sequence[ArgumentRecord] = (),
    run_id: str | None = None,
    step_id: str | None = None,
) -> Iterator[RunContextInfo]:
    """Enter a run context, emitting ``STEP_START`` / ``STEP_END`` boundary events.

    The outermost enter mints a ``run_id``, fingerprints the corpus /
    db / cert state, attaches a
    :class:`aeat.core.observability._sink.JsonlRunSink` to the root
    logger, emits a ``STEP_START`` event, and on exit emits a
    ``STEP_END`` plus persists the finalised
    :class:`aeat.core.observability._models.RunTrace` (even on
    exception, with :attr:`RunOutcome.FAILED`).

    Inner enters reuse the outer ``run_id`` and only push a new
    ``step_id``, so callers can wrap higher-level commands without
    every callee knowing whether a run is already active.

    Args:
        entrypoint: Stable string identifying the CLI entry point
            (e.g. ``"aeat workflow run"``).
        arguments: Sequence of :class:`ArgumentRecord` capturing the
            CLI flags / values for replay.
        run_id: Optional caller-supplied ``run_id`` (used by
            :func:`aeat.core.observability.replay_run`).
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
    from ._recorder import record_event

    outer = RUN_CONTEXT_VAR.get(None)
    if outer is not None:
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
                # STEP_END is always emitted exactly once here.
                try:
                    record_event(
                        RunEventKind.STEP_END,
                        payload=_step_payload(nested_step, label=entrypoint),
                        module=__name__,
                    )
                except Exception:
                    # Best-effort emit: a recorder/sink failure here must
                    # never mask the yielded body's outcome. Broad catch
                    # because the recorder swallows any sink-level disk /
                    # serialisation error and re-raises an opaque type
                    # (logged with traceback above).
                    _log.warning(
                        "failed to record nested STEP_END (run=%s step=%s)",
                        outer.run_id,
                        nested_step,
                        exc_info=True,
                    )
        finally:
            STEP_CONTEXT_VAR.reset(step_token)
        return

    info = _build_initial_context(
        entrypoint=entrypoint,
        arguments=arguments,
        run_id=run_id,
        step_id=step_id,
    )
    target = _run_dir(info.run_id)
    sink = JsonlRunSink(target / _EVENTS_FILENAME, run_id=info.run_id)

    # Set the contextvars BEFORE attaching the sink. Symmetric with
    # detach-before-reset on unwind. Without this ordering, log records
    # emitted by another thread on the root logger during the window
    # between addHandler and set() would land on this sink but carry the
    # previous context's run_id (or an empty one) — the sink's run_id
    # filter drops them, but the semantics are cleaner when the var is
    # bound first.
    run_token = RUN_CONTEXT_VAR.set(info)
    step_token = STEP_CONTEXT_VAR.set(info.initial_step_id)
    attach_run_sink(sink)
    # Pessimistic default: only flip to OK once the yielded body returns
    # cleanly. If STEP_START itself raises, or the yield is never reached,
    # outcome stays FAILED so the persisted trace does not lie.
    outcome = RunOutcome.FAILED
    try:
        record_event(
            RunEventKind.STEP_START,
            payload=_step_payload(info.initial_step_id, label=entrypoint),
            module=__name__,
        )
        try:
            yield info
            outcome = RunOutcome.OK
        finally:
            try:
                record_event(
                    RunEventKind.STEP_END,
                    payload=_step_payload(info.initial_step_id, label=entrypoint),
                    module=__name__,
                )
            except Exception:
                # A failed STEP_END emit must not mask the yielded
                # exception (if any) nor the outcome we already set.
                _log.warning("failed to record STEP_END for run %s", info.run_id, exc_info=True)
    finally:
        # If we were re-entered by ``replay_run``, label the persisted
        # trace with the original run id so ``aeat run show`` can tell a
        # replay trace apart from a fresh one. Only a legitimately-shaped
        # 16-hex run id is propagated; any other value is ignored.
        replay_of = _resolve_replay_of()
        persistence_error: Exception | None = None
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
                replay_of=replay_of,
            )
            save_trace(trace)
        except Exception as exc:
            persistence_error = exc
            _log.warning("failed to persist RunTrace for run %s", info.run_id, exc_info=True)
        finally:
            # Detach the sink BEFORE resetting the contextvars so a
            # trailing log record from another thread can't land on
            # this sink with a stale run_id. Mirror of the attach
            # ordering above.
            try:
                detach_run_sink(sink)
            except Exception:
                _log.warning("failed to detach sink for run %s", info.run_id, exc_info=True)
            STEP_CONTEXT_VAR.reset(step_token)
            RUN_CONTEXT_VAR.reset(run_token)
            try:
                sink.close()
            except Exception:
                # Sink teardown is infallible-by-policy: a close failure
                # cannot be allowed to mask the run's real outcome.
                # Broad catch because the file-handle close path can
                # surface OSError, ValueError, or RuntimeError depending
                # on platform and sink lifecycle state.
                _log.warning("failed to close sink for run %s", info.run_id, exc_info=True)
            if persistence_error is not None and outcome is RunOutcome.OK:
                raise persistence_error


__all__ = [
    "RUN_CONTEXT_VAR",
    "STEP_CONTEXT_VAR",
    "RunContextInfo",
    "current_run_context",
    "run_context",
]
