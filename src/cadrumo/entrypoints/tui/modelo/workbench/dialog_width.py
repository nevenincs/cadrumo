"""Workbench dialogs take the design system's modal width, or the whole terminal when it is narrow.

At the modal width an 80-column terminal leaves a dialog too little room for
its own actions: the review's three buttons clip the one that applies. Below
the threshold a dialog therefore spans the full width, which is the only
percentage the design system admits besides its own tokens.
"""

from __future__ import annotations

from typing import Final

from textual.dom import DOMNode

DIALOG_FULL_WIDTH_BELOW: Final[int] = 100
NARROW_DIALOG_CLASS: Final[str] = "-narrow"


def fit_dialog_width(dialog: DOMNode, terminal_width: int) -> None:
    """Mark a dialog narrow when the terminal is too narrow for the modal width."""
    dialog.set_class(terminal_width < DIALOG_FULL_WIDTH_BELOW, NARROW_DIALOG_CLASS)


__all__ = ["DIALOG_FULL_WIDTH_BELOW", "NARROW_DIALOG_CLASS", "fit_dialog_width"]
