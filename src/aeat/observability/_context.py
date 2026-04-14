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
import uuid
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from contextvars import ContextVar, Token
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict

from aeat.config import PROJECT_ROOT, Settings
from aeat.observability._fingerprint import (
    compute_corpus_sha256,
    compute_db_sha256,
    read_cert_fingerprint,
)
from aeat.observability._models import (
    ArgumentRecord,
    RunEventKind,
    RunEventPayload,
    RunOutcome,
    RunTrace,
    StepBoundaryPayload,
)
from aeat.observability._sink import JsonlRunSink
from aeat.observability._store import runs_dir, save_trace

_DEFAULT_INITIAL_STEP = "step-0"
_EVENTS_FILENAME = "events.jsonl"


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
    """Construct the :class:`RunContextInfo` for an outermost enter."""
    settings = Settings()
    started_at = datetime.now(UTC)
    return RunContextInfo(
        run_id=run_id or _mint_run_id(),
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
    from aeat.observability._recorder import record_event

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
                record_event(
                    RunEventKind.STEP_END,
                    payload=_step_payload(nested_step, label=entrypoint),
                    module=__name__,
                )
            except BaseException:
                record_event(
                    RunEventKind.STEP_END,
                    payload=_step_payload(nested_step, label=entrypoint),
                    module=__name__,
                )
                raise
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
    sink = JsonlRunSink(target / _EVENTS_FILENAME)
    root_logger = logging.getLogger()
    root_logger.addHandler(sink)

    run_token: Token[RunContextInfo | None] = RUN_CONTEXT_VAR.set(info)
    step_token: Token[str | None] = STEP_CONTEXT_VAR.set(info.initial_step_id)
    outcome = RunOutcome.OK
    try:
        record_event(
            RunEventKind.STEP_START,
            payload=_step_payload(info.initial_step_id, label=entrypoint),
            module=__name__,
        )
        try:
            yield info
        except BaseException:
            outcome = RunOutcome.FAILED
            raise
        finally:
            record_event(
                RunEventKind.STEP_END,
                payload=_step_payload(info.initial_step_id, label=entrypoint),
                module=__name__,
            )
    finally:
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
            )
            save_trace(trace)
        finally:
            STEP_CONTEXT_VAR.reset(step_token)
            RUN_CONTEXT_VAR.reset(run_token)
            root_logger.removeHandler(sink)
            sink.close()


__all__ = [
    "RUN_CONTEXT_VAR",
    "STEP_CONTEXT_VAR",
    "RunContextInfo",
    "current_run_context",
    "run_context",
]
