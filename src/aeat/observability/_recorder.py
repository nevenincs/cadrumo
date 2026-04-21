"""``record_event`` — the single emit primitive used by every call site."""

from __future__ import annotations

import inspect
from datetime import UTC, datetime

from ..logging import get_logger
from ._context import RUN_CONTEXT_VAR, STEP_CONTEXT_VAR
from ._errors import RunContextMissingError
from ._models import RunEvent, RunEventKind, RunEventPayload

_logger = get_logger("aeat.observability")


def _caller_module() -> str:
    """Return the module name of the first frame outside this file.

    Falls back to ``"aeat.observability"`` if the walk reaches the
    interpreter without finding a caller (which should never happen
    in practice).
    """
    frame = inspect.currentframe()
    if frame is None:
        return "aeat.observability"
    candidate = frame.f_back
    while candidate is not None:
        module_name = candidate.f_globals.get("__name__", "")
        if isinstance(module_name, str) and module_name and module_name != __name__:
            return module_name
        candidate = candidate.f_back
    return "aeat.observability"


def record_event(
    kind: RunEventKind,
    *,
    payload: RunEventPayload,
    module: str | None = None,
) -> RunEvent:
    """Record a single :class:`RunEvent` against the active run context.

    Args:
        kind: The event kind.
        payload: A :class:`RunEventPayload` with exactly one variant set.
        module: Optional explicit module string; defaults to the
            caller's ``__name__``.

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
        timestamp=datetime.now(UTC),
        module=module or _caller_module(),
    )
    _logger.info("run.event %s", kind.value, extra={"run_event": event})
    return event


__all__ = ["record_event"]
