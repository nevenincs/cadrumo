"""Narrow :class:`BrowserSessionLike` Protocol for submitters.

The concrete :class:`aeat.browser.BrowserSession` is an async factory
around a full Playwright context. The submission engine only needs a
narrow subset of its surface, and pinning to the full class would
force unit tests to either spin up a real browser or use mocks — both
are ruled out by the project's testing mandate.

``BrowserSessionLike`` is a ``runtime_checkable`` Protocol listing
exactly the methods a :class:`Submitter` calls. Unit tests pass a
deterministic Python class implementing these methods that records
every call into a list; this is not a mock, it is a real Protocol
implementation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class BrowserSessionLike(Protocol):
    """Narrow browser-session surface consumed by :class:`Submitter`s."""

    async def navigate(self, url: str) -> None:
        """Navigate the browser to ``url``."""
        ...

    async def fill(self, selector: str, value: str) -> None:
        """Fill the input located by ``selector`` with ``value``."""
        ...

    async def click(self, selector: str) -> None:
        """Click the element located by ``selector``."""
        ...

    async def screenshot(self, path: Path) -> None:
        """Write a full-page screenshot to ``path``."""
        ...

    async def trace_start(self, name: str) -> None:
        """Begin a Playwright trace under ``name``."""
        ...

    async def trace_stop(self, path: Path) -> None:
        """Stop the current trace and write the zip to ``path``."""
        ...

    async def snapshot_form_state(self, path: Path) -> None:
        """Write a JSON snapshot of the current form state to ``path``."""
        ...
