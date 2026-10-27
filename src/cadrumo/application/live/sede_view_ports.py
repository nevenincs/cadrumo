"""Ports of the Sede view operation: the view's browser and the stream it draws into.

The profile worker's operation host composes the stream opener; the browser
adapter supplies the view browser. Neither port carries a URL, a title, an
image, an input or a file byte out of the view: those stay in the browser and
the stream, in memory.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol

from cadrumo_client.contracts.view_stream import ViewPhase, ViewResize, ViewStreamSink

from ...core.config import Settings
from ..auth.protocols import BrowserContextPort, BrowserContextProvisioner
from ..operations.models import OperationIdentity


class SedeViewEnd(StrEnum):
    """Why browsing ended, which decides whether the view publishes its session."""

    CLOSED = "closed"
    """The person closed the page or the window, or its view connection dropped: publish."""
    PAGE_LOST = "page_lost"
    """The view's last page closed while the context still holds the session: publish."""
    STREAM_ENDED = "stream_ended"
    """The runtime ended the stream: the session was retired or locked, or the runtime stops."""
    STOPPED = "stopped"
    """The supervisor asked the operation to stop."""
    PROTOCOL_VIOLATION = "protocol_violation"
    """The window sent input the contract refuses."""


PUBLISHING_ENDS = frozenset({SedeViewEnd.CLOSED, SedeViewEnd.PAGE_LOST})
"""The ends after which the view publishes its session through the canonical custody path."""


@dataclass(frozen=True, slots=True)
class SedeViewOpening:
    """Everything the browser adapter needs to open the view, and nothing it could journal."""

    settings: Settings
    sink: ViewStreamSink
    viewport: ViewResize
    storage_state: Mapping[str, object] = field(repr=False)
    provisioner: BrowserContextProvisioner | None = field(repr=False)


class SedeViewBrowser(Protocol):
    """The view's own browser, page, screencast, input and transfers."""

    @property
    def context(self) -> BrowserContextPort:
        """The view context, open until :meth:`close`; close-time publication captures it."""
        ...

    async def browse(self, *, stop_requested: Callable[[], bool]) -> SedeViewEnd:
        """Relay the page and the person's input until the view ends, with no idle or absolute bound."""
        ...

    async def announce_phase(self, phase: ViewPhase) -> None:
        """Tell the window which phase the view is in."""
        ...

    async def close(self) -> None:
        """Stop the screencast and input, discard pending transfers and close the browser."""
        ...


type SedeViewBrowserFactory = Callable[[SedeViewOpening], Awaitable[SedeViewBrowser]]
"""Open the view's browser at the Sede, seeded from custody; it owns its Chromium through the operation scope."""

type SedeViewStreamOpener = Callable[[OperationIdentity], ViewStreamSink]
"""Open the view stream for one running view, bound by the host to the session that admitted it."""


__all__ = [
    "PUBLISHING_ENDS",
    "SedeViewBrowser",
    "SedeViewBrowserFactory",
    "SedeViewEnd",
    "SedeViewOpening",
    "SedeViewStreamOpener",
]
