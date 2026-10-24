"""Relay progress as MCP ``notifications/progress``: an observed operation's, and a running setup's.

The ``observe`` tool returns one page of the operation's public events. When
the client asked for progress by sending a ``progressToken``, each progress
event on that page is also sent as one progress notification, so a client
can draw a bar while it observes. The setup tools relay each byte figure the
components role sends while the call runs, in the same way. A figure that
belongs to a setup item names it in ``subject_code``; the notification's
message then names that item in plain words from the setup registry, never by
its code.

The relay reads only what the tool already received. It observes nothing
itself and never decides an outcome, so a notification that is lost changes
nothing.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any

from cadrumo.adapters.outbound.components.protocol import ComponentsProgressLine
from cadrumo.application.dependency_contracts import dependency_item_kind
from cadrumo.application.dependency_registry import dependency_item_declarations
from cadrumo.core.i18n.render import tr

__all__ = ["ProgressSink", "RelayedProgress", "component_progress", "relayed_progress"]

_OBSERVE_TOOL = "observe"


@dataclass(frozen=True, slots=True)
class RelayedProgress:
    """One progress figure as an MCP progress notification carries it."""

    progress: float
    total: float
    message: str | None


type ProgressSink = Callable[[RelayedProgress], Awaitable[None]]
"""Sends one figure to the client that asked for progress."""


def _subject_message(subject_code: object) -> str | None:
    if not isinstance(subject_code, str):
        return None
    try:
        dependency_item_kind(subject_code)
    except ValueError:
        return None
    for declaration in dependency_item_declarations():
        if declaration.item_id == subject_code:
            return tr(f"application.{declaration.display_key}")
    return None


def relayed_progress(tool: str, result: Mapping[str, Any]) -> tuple[RelayedProgress, ...]:
    """Return the progress figures an ``observe`` reply carries, in event order; none for any other tool."""
    if tool != _OBSERVE_TOOL or result.get("outcome") != "reply":
        return ()
    reply = result.get("reply")
    if not isinstance(reply, Mapping) or reply.get("kind") != "operation_observed":
        return ()
    observation = reply.get("observation")
    if not isinstance(observation, Mapping) or observation.get("outcome") != "success":
        return ()
    page = observation.get("event_page")
    events = page.get("events") if isinstance(page, Mapping) else None
    if not isinstance(events, list):
        return ()
    relayed: list[RelayedProgress] = []
    for event in events:
        if not isinstance(event, Mapping) or event.get("kind") != "progress":
            continue
        completed, total = event.get("completed"), event.get("total")
        if not isinstance(completed, int) or not isinstance(total, int) or total <= 0:
            continue
        relayed.append(
            RelayedProgress(
                progress=float(completed), total=float(total), message=_subject_message(event.get("subject_code"))
            )
        )
    return tuple(relayed)


def component_progress(event: object) -> RelayedProgress | None:
    """Return the figure a components role event carries, or ``None`` for an event that carries none."""
    if not isinstance(event, ComponentsProgressLine):
        return None
    return RelayedProgress(
        progress=float(event.completed), total=float(event.total), message=_subject_message(event.subject_code)
    )
