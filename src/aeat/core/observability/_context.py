"""Contextvars-backed run context with nesting support and JSONL sink wiring.

Entering :func:`run_context` at the outermost CLI entry point mints a
fresh ``run_id``, fingerprints the corpus / db / cert state, attaches a
:class:`JsonlRunSink` to the root logger for the duration of the
block, emits a ``STEP_START`` event, and persists the final
:class:`RunTrace` on exit. Nesting is idempotent: an inner enter
reuses the outer ``run_id`` and only pushes a new step.

See [[2026-04-14-run-trace-adr]] decision D2.
"""

from __future__ import annotations

import logging
import os
import uuid
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from contextvars import ContextVar, Token
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict

from ..config import PROJECT_ROOT, Settings
from ..logging import get_logger
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
from ._store import _validate_run_id, runs_dir, save_trace

_log = get_logger(__name__)

_DEFAULT_INITIAL_STEP = "step-0"
_EVENTS_FILENAME = "events.jsonl"
# Env var set by :func:`aeat.core.observability.replay_run` for the
# duration of the re-entered CLI call. Kept in sync with
# :data:`aeat.core.observability._replay.REPLAY_ACTIVE_ENV_VAR` — spelled
# here to avoid a cycle with ``_replay`` at import time.
_REPLAY_ACTIVE_ENV_VAR = "AEAT_REPLAY_ACTIVE"


class RunContextInfo(BaseModel):
    """Immutable bag of run-level metadata exposed to call sites."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

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
STEP_CONTEXT_VAR: ContextVar[str | None] = ContextVar(
    "_aeat_step_ctx",
    default=None,
)


def current_run_context() -> RunContextInfo | None:
    """Return the active :class:`RunContextInfo` if one is bound, else ``None``."""
    return RUN_CONTEXT_VAR.get(None)


def _mint_run_id() -> str:
    """Mint a fresh 16-character hex identifier."""
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
    shape (16 lowercase hex) before anything touches the filesystem —
    this prevents a malicious or buggy caller from escaping the
    configured runs directory through e.g. ``"../etc"``.
    """
    settings = Settings()
    started_at = datetime.now(UTC)
    effective_run_id = _validate_run_id(run_id) if run_id is not None else _mint_run_id()
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
    """Build a :class:`RunEventPayload` carrying a step boundary."""
    return RunEventPayload(step=StepBoundaryPayload(step_id=step_id, label=label))


@contextmanager
def run_context(
    *,
    entrypoint: str,
    arguments: Sequence[ArgumentRecord] = (),
    run_id: str | None = None,
    step_id: str | None = None,
) -> Iterator[RunContextInfo]:
    """Enter a run context, emitting STEP_START / STEP_END boundary events.

    Outermost enter mints a ``run_id``, fingerprints the corpus / db /
    cert state, attaches a JSONL sink to the root logger, emits a
    ``STEP_START`` event, and on exit emits a ``STEP_END`` plus
    persists the finalised :class:`RunTrace` (even on exception, with
    ``outcome=FAILED``).

    Inner enters reuse the outer ``run_id`` and only push a new
    step_id, so callers can wrap higher-level commands without every
    callee knowing whether a run is already active.

    Args:
        entrypoint: Stable string identifying the CLI entry point
            (e.g. ``"aeat workflow run"``).
        arguments: Sequence of :class:`ArgumentRecord` capturing the
            CLI flags / values for replay.
        run_id: Optional caller-supplied ``run_id`` (used by replay).
        step_id: Optional initial step identifier.

    Yields:
        The active :class:`RunContextInfo` for the block.
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
                # STEP_END is always emitted exactly once here; the
                # prior ``step_end_emitted`` flag was never read in a
                # way that could differ from its write and has been
                # removed (audit nit N5).
                try:
                    record_event(
                        RunEventKind.STEP_END,
                        payload=_step_payload(nested_step, label=entrypoint),
                        module=__name__,
                    )
                except Exception as exc:
                    _log.warning(
                        "failed to record nested STEP_END (run=%s step=%s): %r",
                        outer.run_id,
                        nested_step,
                        exc,
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
    runs_root = runs_dir()
    target = runs_root / info.run_id
    target.mkdir(parents=True, exist_ok=True)
    sink = JsonlRunSink(target / _EVENTS_FILENAME, run_id=info.run_id)
    root_logger = logging.getLogger()

    # Set the contextvars BEFORE attaching the sink. Symmetric with
    # detach-before-reset on unwind. Without this ordering, log records
    # emitted by another thread on the root logger during the window
    # between addHandler and set() would land on this sink but carry the
    # previous context's run_id (or an empty one) — the sink's run_id
    # filter drops them, but the semantics are cleaner when the var is
    # bound first. See audit finding S1 (vaultspec-code-reviewer,
    # 2026-04-21).
    run_token: Token[RunContextInfo | None] = RUN_CONTEXT_VAR.set(info)
    step_token: Token[str | None] = STEP_CONTEXT_VAR.set(info.initial_step_id)
    root_logger.addHandler(sink)
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
            except Exception as exc:
                # A failed STEP_END emit must not mask the yielded
                # exception (if any) nor the outcome we already set.
                _log.warning("failed to record STEP_END for run %s: %r", info.run_id, exc)
    finally:
        # If we were re-entered by ``replay_run``, label the persisted
        # trace with the original run id so ``aeat run show`` can tell a
        # replay trace apart from a fresh one. Any non-16-hex value
        # (e.g. a legacy ``"1"`` sentinel from earlier code) is ignored
        # — only a legitimately-shaped run id is propagated.
        replay_of_env = os.environ.get(_REPLAY_ACTIVE_ENV_VAR)
        replay_of: str | None = None
        if replay_of_env and len(replay_of_env) == 16:
            try:
                int(replay_of_env, 16)
            except ValueError:
                replay_of = None
            else:
                replay_of = replay_of_env.lower()
        try:
            trace = RunTrace(
                run_id=info.run_id,
                started_at=info.started_at,
                finished_at=datetime.now(UTC),
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
            # Persisting the trace is best-effort — a disk-full at exit
            # must never shadow the real exception the caller is
            # propagating. Log and move on.
            _log.warning("failed to persist RunTrace for run %s: %r", info.run_id, exc)
        finally:
            # Detach the sink BEFORE resetting the contextvars so a
            # trailing log record from another thread can't land on
            # this sink with a stale run_id. Mirror of the attach
            # ordering above; see audit finding S1.
            try:
                root_logger.removeHandler(sink)
            except Exception as exc:  # pragma: no cover - logging lock is infallible in practice
                _log.warning("failed to detach sink for run %s: %r", info.run_id, exc)
            STEP_CONTEXT_VAR.reset(step_token)
            RUN_CONTEXT_VAR.reset(run_token)
            try:
                sink.close()
            except Exception as exc:
                _log.warning("failed to close sink for run %s: %r", info.run_id, exc)


__all__ = [
    "RUN_CONTEXT_VAR",
    "STEP_CONTEXT_VAR",
    "RunContextInfo",
    "current_run_context",
    "run_context",
]
