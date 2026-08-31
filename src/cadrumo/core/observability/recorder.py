"""The single :func:`record_event` emit primitive used by every call site.

Routes structured :class:`cadrumo.core.observability.models.RunEvent`
records through the standard :mod:`logging` machinery so any handler
attached to the root logger — notably the per-run
:class:`cadrumo.core.observability.sink.JsonlRunSink` — picks them up
automatically while a :func:`cadrumo.core.observability.run_context` is
active.
"""

from __future__ import annotations

import inspect

from ..logging import get_logger
from ..time.clock import now
from .context import RUN_CONTEXT_VAR, STEP_CONTEXT_VAR
from .errors import RunContextMissingError
from .models import RunEvent, RunEventKind, RunEventPayload

_logger = get_logger("cadrumo.core.observability")


def _caller_module() -> str:
    """Return the module name of the first frame outside this file.

    Falls back to ``"cadrumo.core.observability"`` if the walk reaches the
    interpreter without finding a caller (which should never happen
    in practice).
    """
    frame = inspect.currentframe()
    if frame is None:
        return "cadrumo.core.observability"
    candidate = frame.f_back
    while candidate is not None:
        module_name = candidate.f_globals.get("__name__", "")
        if isinstance(module_name, str) and module_name and module_name != __name__:
            return module_name
        candidate = candidate.f_back
    return "cadrumo.core.observability"


def record_event(
    kind: RunEventKind,
    *,
    payload: RunEventPayload,
    module: str | None = None,
) -> RunEvent:
    """Record a single :class:`RunEvent` against the active run context.

    Context propagation note: the active ``run_id`` is carried via
    :class:`contextvars.ContextVar`. These propagate across
    :func:`asyncio.create_task` and :func:`asyncio.run` automatically
    (PEP 567), but NOT across plain :class:`threading.Thread` targets
    nor :func:`asyncio.to_thread` / ``loop.run_in_executor`` workers
    unless the caller wraps the target with
    :func:`contextvars.copy_context`. A call to :func:`record_event`
    from a detached thread therefore raises
    :exc:`cadrumo.core.observability.RunContextMissingError`. Callers that
    need the event recorded in such a thread must either re-enter
    :func:`cadrumo.core.observability.run_context` inside the worker or
    copy the context explicitly.

    Args:
        kind: The event kind.
        payload: A :class:`RunEventPayload` with exactly one variant set.
        module: Optional explicit module string; defaults to the
            caller's ``__name__`` resolved by :func:`_caller_module`.

    Returns:
        The constructed :class:`RunEvent` (also forwarded to the JSONL
        sink via the ``run_event`` logging extra).

    Raises:
        RunContextMissingError: If no run context is active on the
            current contextvar.
    """
    ctx = RUN_CONTEXT_VAR.get(None)
    if ctx is None:
        raise RunContextMissingError(
            f"record_event({kind.value}) called outside an active run_context()",
        )
    step_id = STEP_CONTEXT_VAR.get(None) or ctx.initial_step_id
    event = RunEvent(
        run_id=ctx.run_id,
        step_id=step_id,
        kind=kind,
        payload=payload,
        timestamp=now(),
        module=module or _caller_module(),
    )
    # INFO level keeps the record flowing through both the JSONL sink
    # AND any caller that has tightened their own handler levels.
    # Stderr duplication is suppressed inside
    # :func:`cadrumo.core.logging.configure_logging`, where the default stderr
    # handler carries a filter that excludes records which already
    # went to the per-run sink (i.e. records with a ``run_event``
    # extra). Keeping the emission at INFO here means other
    # subpackages that attach their own INFO-level handlers still see
    # the observability record.
    _logger.info("run.event %s", kind.value, extra={"run_event": event})
    return event


__all__ = ["record_event"]
