"""Find the box panel wherever it is open: docked in the workbench, or held in the centred dialog."""

from __future__ import annotations

from textual.dom import DOMNode

from ..editor import CasillaEditorPanel


def open_panel(screen: DOMNode) -> CasillaEditorPanel | None:
    """The box panel on ``screen``, the one on top; ``None`` when no panel is open there."""
    panels = list(screen.query(CasillaEditorPanel))
    assert len(panels) <= 1, "one box panel is open at a time"
    return panels[0] if panels else None


__all__ = ["open_panel"]
