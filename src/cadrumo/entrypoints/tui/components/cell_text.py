"""Terminal-cell text fitting shared by Textual surfaces.

Widths here are display cells, never code points, so wide and combining
characters fit the room a terminal gives them.
"""

from __future__ import annotations

import re
from typing import Final

from rich.cells import cell_len

ELLIPSIS: Final[str] = "…"
_BREAKABLE_SPACE: Final[re.Pattern[str]] = re.compile(r"[^\S\u00a0]+")
"""Where a text may break: any space except a no-break space, which holds "art. 71" or "1 000" together."""


def ellipsize(text: str, width: int) -> str:
    """Cut ``text`` to at most ``width`` cells, ending a cut with an ellipsis rather than a dangling space."""
    if cell_len(text) <= width:
        return text
    kept = ""
    for character in text:
        if cell_len(kept + character + ELLIPSIS) > width:
            break
        kept += character
    return kept.rstrip() + ELLIPSIS


def wrap_words(text: str, width: int) -> tuple[str, ...]:
    """Break ``text`` into lines of at most ``width`` cells, only where a space other than a no-break one stands.

    A single word wider than the line is cut where it must be, so no line
    ever runs past ``width``; nothing is dropped.
    """
    width = max(width, 1)
    lines: list[str] = []
    line = ""
    for word in _BREAKABLE_SPACE.split(text.strip()):
        candidate = f"{line} {word}" if line else word
        if cell_len(candidate) <= width:
            line = candidate
            continue
        if line:
            lines.append(line)
        line = word
        while cell_len(line) > width:
            cut = 1
            while cell_len(line[: cut + 1]) <= width:
                cut += 1
            lines.append(line[:cut])
            line = line[cut:]
    lines.append(line)
    return tuple(lines)


def longest_word(text: str) -> int:
    """The widest unbreakable run of ``text``, in cells."""
    return max((cell_len(word) for word in _BREAKABLE_SPACE.split(text.strip())), default=0)
