"""The runtime's lifecycle notice for one MCP connection, told to its client on a tool result.

The runtime sends a notice to the connections that offered to receive it
before it stops for an update. The command line prints it and the terminal
interface shows it; an MCP client has no screen of the server's, so the next
tool result carries it, and ``status`` repeats it while the connection that
received it is still held. It is information only: it grants and ends nothing.
"""

from __future__ import annotations

from threading import Lock
from typing import Any

from cadrumo_client.contracts.session_events import LifecycleNotice


class LifecycleNoticeBoard:
    """Hold the latest notice between the transport thread that receives it and the call that tells it."""

    def __init__(self) -> None:
        """Start with nothing to tell."""
        self._guard = Lock()
        self._notice: LifecycleNotice | None = None
        self._owner: int | None = None
        self._told = False

    def receive(self, owner: int, notice: LifecycleNotice) -> None:
        """Keep a notice that arrived on the connection ``owner`` identifies; never blocks the transport."""
        with self._guard:
            self._notice, self._owner, self._told = notice, owner, False

    def released(self, owner: int) -> None:
        """Forget a notice already told once the connection that received it is let go.

        One not yet told is kept for the next result: the runtime it announced
        may already have restarted, and the client is still owed the reason.
        """
        with self._guard:
            if self._owner != owner:
                return
            self._owner = None
            if self._told:
                self._notice = None

    def annotate(self, tool: str, reply: dict[str, Any]) -> None:
        """Add the notice to a reply the first time, and to every ``status`` while its connection is held."""
        with self._guard:
            notice = self._notice
            if notice is None or (self._told and tool != "status"):
                return
            self._told = True
            if self._owner is None:
                self._notice = None
        reply["notice"] = {"event": notice.event, "notice_id": str(notice.notice_id)}
