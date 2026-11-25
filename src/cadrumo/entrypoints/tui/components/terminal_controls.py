"""Keep imported text from driving the terminal that displays a Textual frame.

Textual measures and places text in cells, then writes each rendered line to
the terminal. Rich and Textual strip only a few controls when content is built,
so an ESC, C1, carriage return or bidi control carried by an imported narrative
would otherwise reach the terminal's protocol parser inside the frame: an OSC 52
clipboard write, a screen clear, or reordered text. Textual's own styling,
cursor and hyperlink sequences are generated from styles and control segments
after this filter runs, never from segment text, so they are unaffected.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, override

from rich.segment import Segment
from textual.filter import LineFilter

from ....core.terminal_encoding import has_terminal_controls, strip_terminal_controls

if TYPE_CHECKING:
    from textual.color import Color


class TerminalControlFilter(LineFilter):
    """Delete terminal controls from every rendered line's text.

    Deletion rather than a visible escape: each removed character occupies zero
    cells, so the line keeps the width Textual already laid out.
    """

    @override
    def apply(self, segments: list[Segment], background: Color) -> list[Segment]:
        if not any(_carries_controls(segment) for segment in segments):
            return segments
        return [
            Segment(strip_terminal_controls(segment.text), segment.style, segment.control)
            if _carries_controls(segment)
            else segment
            for segment in segments
        ]


def _carries_controls(segment: Segment) -> bool:
    # A control segment is Textual's own cursor or mode sequence, not displayed text.
    return segment.control is None and has_terminal_controls(segment.text)
