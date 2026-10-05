"""Escape authored casilla prose and format RST headings and raw HTML blocks."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


#: RST inline-markup start characters. Registry labels carry free AEAT prose
#: with footnote markers (``2025(*)``), pipes, and stray asterisks, so every
#: embedded free-text value reaching an RST heading is backslash-escaped or the
#: ``-n -W`` build reds on an unbalanced ``*`` / ``` ` ``` / ``|`` run. Card
#: bodies are raw HTML and are HTML-escaped instead.
_RST_SPECIAL = "\\`*_|[]"


def _rst_escape(text: str) -> str:
    """Backslash-escape RST inline-markup characters in arbitrary free text."""
    return "".join(f"\\{ch}" if ch in _RST_SPECIAL else ch for ch in text)


def _rst_heading(text: str, underline: str) -> str:
    return f"{text}\n{underline * max(len(text), 3)}\n"


def _raw_html(lines: list[str]) -> str:
    """Wrap rendered HTML lines in an RST ``raw`` directive block."""
    body = "\n".join(f"   {line}" for line in lines)
    return f".. raw:: html\n\n{body}\n"
