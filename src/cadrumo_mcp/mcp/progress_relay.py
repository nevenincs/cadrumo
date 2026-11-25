"""Relay observed operation progress as MCP ``notifications/progress``.

The ``observe`` tool returns one page of the operation's public events. When
the client asked for progress by sending a ``progressToken``, each progress
event on that page is also sent as one progress notification, so a client
can draw a bar while it observes.

The relay reads only what the tool already received. It observes nothing
itself and never decides an outcome, so a notification that is lost changes
nothing.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any, cast

__all__ = ["ProgressSink", "RelayedProgress", "relayed_progress"]

_OBSERVE_TOOL = "observe"


@dataclass(frozen=True, slots=True)
class RelayedProgress:
    """One progress figure as an MCP progress notification carries it."""

    progress: float
    total: float


type ProgressSink = Callable[[RelayedProgress], Awaitable[None]]
"""Sends one figure to the client that asked for progress."""


def _observed_events(tool: str, result: Mapping[str, Any]) -> list[object]:
    """Read only the event list of a successful operation observation."""
    if tool != _OBSERVE_TOOL or result.get("outcome") != "reply":
        return []
    reply = result.get("reply")
    if not isinstance(reply, Mapping) or reply.get("kind") != "operation_observed":
        return []
    observation = reply.get("observation")
    if not isinstance(observation, Mapping) or observation.get("outcome") != "success":
        return []
    page = observation.get("event_page")
    events = page.get("events") if isinstance(page, Mapping) else None
    if not isinstance(events, list):
        return []
    return cast(list[object], events)


def _progress_event(event: object) -> RelayedProgress | None:
    """Admit a positive-total progress event without inferring any operation outcome."""
    if not isinstance(event, Mapping):
        return None
    fields = cast(Mapping[object, object], event)
    if fields.get("kind") != "progress":
        return None
    completed, total = fields.get("completed"), fields.get("total")
    if not isinstance(completed, int) or not isinstance(total, int) or total <= 0:
        return None
    return RelayedProgress(progress=float(completed), total=float(total))


def relayed_progress(tool: str, result: Mapping[str, Any]) -> tuple[RelayedProgress, ...]:
    """Return the progress figures an ``observe`` reply carries, in event order; none for any other tool."""
    events = _observed_events(tool, result)
    relayed: list[RelayedProgress] = []
    for event in events:
        progress = _progress_event(event)
        if progress is not None:
            relayed.append(progress)
    return tuple(relayed)
