"""Escape authored casilla prose and format RST headings and raw HTML blocks."""

from __future__ import annotations

from .compile_slots import widest

#: RST inline-markup start characters. Registry labels carry free AEAT prose
#: with footnote markers (``2025(*)``), pipes, and stray asterisks, so every
#: embedded free-text value reaching an RST heading is backslash-escaped or the
#: ``-n -W`` build reds on an unbalanced ``*`` / ``` ` ``` / ``|`` run. Card
#: bodies are raw HTML and are HTML-escaped instead.
#:
#: A mark (:mod:`dev.docs.compile_slots`) carries none of them, so a value the
#: one compile marked passes through untouched -- which is right: the escaping
#: protects the parser from free text, and the free text is in the record of
#: marks rather than in the source the parser reads.
_RST_SPECIAL = "\\`*_|[]"


def _rst_escape(text: str) -> str:
    """Backslash-escape RST inline-markup characters in arbitrary free text."""
    return "".join(f"\\{ch}" if ch in _RST_SPECIAL else ch for ch in text)


def _rst_heading(text: str, underline: str) -> str:
    return f"{text}\n{underline * max(widest(text), 3)}\n"


def _raw_html(lines: list[str]) -> str:
    """Wrap rendered HTML lines in an RST ``raw`` directive block.

    Each entry is indented by its own physical lines rather than as one string:
    an element only some languages carry rides at the end of the preceding entry
    with its own line break (:func:`~dev.docs._locale_chrome.docs_line`), so an
    entry can be two lines of HTML and both have to sit inside the block.
    """
    body = "\n".join(f"   {line}" for line in "\n".join(lines).split("\n"))
    return f".. raw:: html\n\n{body}\n"
