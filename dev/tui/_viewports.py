"""The terminal geometries a surface is reviewed at.

A TUI has no pixel resolution of its own: what a large monitor buys the
operator is more CELLS, not larger ones, so the axis that decides whether a
layout survives a small screen is the column/row grid. The pixel size of the
artefact is a separate, purely cosmetic scale applied at raster time.

Three landscape shapes mirror the sizes the shipped in-boundary appearance
gate already renders at (``test_visual_verification._SIZES``): 80x24 is the
floor a real terminal can be and the size at which an overflowing layout
stops being cosmetic and starts hiding controls, 120x40 is an ordinary
window, 200x50 a wide one. They are restated here rather than imported
because the architecture decision forbids a development tool from importing
the TUI package at all; when that gate's matrix moves, this one follows.

The portrait shapes are this tool's own addition. Every size the gate
carries is landscape, so a tall narrow window -- a split pane, a docked
terminal, a phone-sized SSH session -- is exactly the shape no existing
proof looks at, and the one where a wide fixed-width row overflows first.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class Viewport:
    """One terminal grid a surface is rendered at."""

    name: str
    columns: int
    rows: int
    summary: str

    @property
    def orientation(self) -> str:
        """Whether this grid is wider than it is tall, in rendered proportion.

        Compared against the terminal cell aspect ratio rather than against
        the raw column and row counts: a cell is roughly twice as tall as it
        is wide, so an 80x24 grid that looks square in numbers is a wide
        landscape rectangle on screen.
        """
        return "landscape" if self.columns >= self.rows * _CELL_ASPECT else "portrait"

    @property
    def label(self) -> str:
        """The ``WxH`` token the in-boundary harness accepts."""
        return f"{self.columns}x{self.rows}"


_CELL_ASPECT: Final[float] = 2.0
"""Cell height divided by cell width, near enough for classifying a shape."""

VIEWPORTS: Final[dict[str, Viewport]] = {
    viewport.name: viewport
    for viewport in (
        Viewport("small", 80, 24, "the floor a real terminal can be"),
        Viewport("medium", 120, 40, "an ordinary window"),
        Viewport("large", 200, 50, "a wide window on a large display"),
        Viewport("tall", 80, 50, "a narrow docked pane, twice the floor's height"),
        Viewport("portrait", 60, 60, "a tall split pane narrower than the floor"),
    )
}

DEFAULT_VIEWPORTS: Final[tuple[str, ...]] = ("small", "medium", "large", "tall")
"""What ``render`` covers when the caller names no viewport.

``portrait`` is deliberately outside the default set: 60 columns is below
the floor the layout is designed against, so it is a deliberate stress
reading rather than a shape every review should carry.
"""


def resolve(name: str) -> Viewport:
    """Return the named viewport, or refuse listing the accepted set."""
    try:
        return VIEWPORTS[name]
    except KeyError:
        accepted = ", ".join(VIEWPORTS)
        message = f"unknown viewport {name!r}; accepted: {accepted}"
        raise KeyError(message) from None


__all__ = ["DEFAULT_VIEWPORTS", "VIEWPORTS", "Viewport", "resolve"]
