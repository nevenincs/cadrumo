"""Blank TypeScript comments and string text while keeping every column and newline.

A line reader then sees only code: prose in a comment and a date written as
text are spaces, and template expressions stay readable as code.
"""

from __future__ import annotations

import re

#: How a code character changes the nesting of braces a template expression closes at.
_BRACE_DEPTH = {"{": 1, "}": -1}


def _blank(chunk: str) -> str:
    return re.sub(r"[^\n]", " ", chunk)


class _Blanker:
    """One pass over a source text, appending code as written and blanked text to ``out``."""

    def __init__(self, source: str) -> None:
        self.source = source
        self.length = len(source)
        self.out: list[str] = []

    def code(self, start: int, closing: str | None) -> int:
        """Copy code from ``start`` until ``closing`` at brace depth zero, or the end; return where it stopped."""
        at = start
        depth = 0
        while at < self.length:
            char = self.source[at]
            if closing is not None and depth == 0 and char == closing:
                return at
            skipped = self._text(at, char)
            if skipped is not None:
                at = skipped
                continue
            depth += _BRACE_DEPTH.get(char, 0)
            self.out.append(char)
            at += 1
        return at

    def _text(self, at: int, char: str) -> int | None:
        """Blank the comment or string opening at ``at`` and return where it ends, or ``None`` for code."""
        if self.source.startswith("//", at):
            end = self.source.find("\n", at)
            return self._blank_to(at, self.length if end < 0 else end)
        if self.source.startswith("/*", at):
            end = self.source.find("*/", at + 2)
            return self._blank_to(at, self.length if end < 0 else end + 2)
        if char in "\"'":
            return self._quoted(at, char)
        if char == "`":
            self.out.append("`")
            return self._template(at + 1)
        return None

    def _blank_to(self, start: int, end: int) -> int:
        self.out.append(_blank(self.source[start:end]))
        return end

    def _quoted(self, at: int, quote: str) -> int:
        """Blank a quoted string's body, keeping its quotes; return where it ends."""
        end = at + 1
        while end < self.length and self.source[end] != quote and self.source[end] != "\n":
            end += 2 if self.source[end] == "\\" else 1
        if end < self.length and self.source[end] == quote:
            self.out.append(quote + _blank(self.source[at + 1 : end]) + quote)
            return end + 1
        # An unpaired quote, such as a JSX apostrophe, ends at the line and keeps its newline.
        return self._blank_to(at, end)

    def _template(self, start: int) -> int:
        """Blank a template's text, keeping its expressions as code; return where it ends."""
        at = start
        while at < self.length and self.source[at] != "`":
            at = self._template_part(at)
        self.out.append("`")
        return at + 1

    def _template_part(self, at: int) -> int:
        if self.source[at] == "\\":
            # An escape blanks the character after it, even a backquote; one at the very end runs past it.
            self.out.append(_blank(self.source[at : at + 2]))
            return at + 2
        if self.source.startswith("${", at):
            self.out.append("${")
            end = self.code(at + 2, closing="}")
            self.out.append("}")
            return end + 1
        return self._blank_to(at, at + 1)


def blank_text(source: str) -> str:
    """Blank comments and string text, keeping template expressions and every newline."""
    blanker = _Blanker(source)
    index = 0
    while index < blanker.length:
        index = blanker.code(index, closing=None)
    return "".join(blanker.out)


def comment_free(source: str) -> str:
    """Blank comments only, keeping string text, so string coordinates stay readable."""
    return re.sub(r"/\*.*?\*/|(?<![:\"'\\])//[^\n]*", lambda match: _blank(match.group()), source, flags=re.S)
