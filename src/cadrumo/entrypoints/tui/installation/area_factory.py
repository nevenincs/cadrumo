"""How a screen that has no session is given the installation area to open."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from textual.screen import Screen


class InstallationAreaFactory(Protocol):
    """Build the installation area for a screen that opens it before any session exists."""

    def __call__(self, report_change: Callable[[], None], /, *, locale: str | None = None) -> Screen[None]:
        """Return the area.

        Args:
            report_change: Called when an act may have changed which profiles exist.
            locale: The language the opening page is written in, when it chose
                one of its own; ``None`` for the language already on screen.
        """
        ...


__all__ = ["InstallationAreaFactory"]
