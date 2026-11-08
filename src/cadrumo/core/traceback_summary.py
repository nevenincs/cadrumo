"""The bounded, identifier-only summary of a Python traceback that names no message or source line."""

from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass
from typing import Final

from .log_scrubbing import scrub_text

TRACEBACK_HEADER: Final = "Traceback (most recent call last):"
"""The exact line that opens a traceback block."""

TRACEBACK_FRAMES: Final = 8
"""How many of a traceback's innermost frames a summary names."""

_FRAME_LINE: Final = re.compile(r'^\s+File "(?P<file>[^"]+)", line (?P<line>\d+), in (?P<name>.+?)\s*$')

_FILE_NAME: Final = re.compile(r"^(?:[A-Za-z_][A-Za-z0-9_-]*\.pyw?|<frozen [A-Za-z_][A-Za-z0-9_.]*>)$")

_FUNCTION_NAME: Final = re.compile(
    r"^(?:[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*|<(?:module|lambda|listcomp|dictcomp|setcomp|genexpr)>)$"
)

_LINE_NUMBER: Final = re.compile(r"^[1-9][0-9]{0,6}$")

_DIGIT_RUN: Final = re.compile(r"[0-9]{5,}")
"""Identification, account and telephone numbers carry long digit runs; code identifiers do not."""

_EXCEPTION_LINE: Final = re.compile(r"^(?P<type>[^:\s]+)(?::|$)")

_EXCEPTION_TYPE: Final = re.compile(
    r"^(?:[A-Za-z_][A-Za-z0-9_]*\.){0,6}"
    r"[A-Za-z_][A-Za-z0-9_]{0,80}(?:Error|Exception|Exit|Interrupt|Warning|Iteration|Group)$"
)


@dataclass(frozen=True, slots=True)
class TracebackSummary:
    """What a traceback block admits to a log: its exception type and innermost frame locations."""

    error_type: str | None
    """The exception type, or ``None`` when the exception line is not a strict type name."""

    frames: tuple[str, ...]
    """Up to :data:`TRACEBACK_FRAMES` admitted ``file.py:line:function`` frames, innermost first."""

    innermost_admitted: bool
    """Whether the last frame line read was admitted, so that ``frames[0]`` is the true innermost frame."""

    @property
    def origin(self) -> str | None:
        """The innermost frame, named only when no refused frame lies inside it."""
        return self.frames[0] if self.frames and self.innermost_admitted else None


class TracebackReader:
    """Read the body of one traceback a line at a time, holding no more than its innermost frames.

    No message, source line or other text is retained: a frame line is kept
    only as its admitted identity, and every other line is discarded as read.
    """

    def __init__(self) -> None:
        """Start a body that has read no line."""
        self._frames: deque[str] = deque(maxlen=TRACEBACK_FRAMES)
        self._innermost_admitted = False

    def read(self, line: str) -> TracebackSummary | None:
        """Take the next body line; the exception line ends the body and returns its summary."""
        if not line.strip():
            return None
        frame_line = _FRAME_LINE.match(line)
        if frame_line is not None:
            frame = _frame_identity(frame_line)
            self._innermost_admitted = frame is not None
            if frame is not None:
                self._frames.append(frame)
            return None
        if line[:1].isspace():
            return None
        exception = _EXCEPTION_LINE.match(line)
        error_type = None if exception is None else _admitted(str(exception.group("type")), _EXCEPTION_TYPE)
        return self._summary(error_type)

    def unfinished(self) -> TracebackSummary:
        """Summarise a body whose exception line was never read."""
        return self._summary(None)

    def _summary(self, error_type: str | None) -> TracebackSummary:
        return TracebackSummary(
            error_type=error_type, frames=tuple(reversed(self._frames)), innermost_admitted=self._innermost_admitted
        )


def _frame_identity(frame: re.Match[str]) -> str | None:
    """A frame as ``file.py:line:function``, the file by name alone, or ``None`` if any token is not admitted."""
    file_name = _admitted(str(frame.group("file")).replace("\\", "/").rsplit("/", 1)[-1], _FILE_NAME)
    line = _admitted(str(frame.group("line")), _LINE_NUMBER, numeric=True)
    name = _admitted(str(frame.group("name")), _FUNCTION_NAME)
    if file_name is None or line is None or name is None:
        return None
    return f"{file_name}:{line}:{name}"


def _admitted(token: str, pattern: re.Pattern[str], *, numeric: bool = False) -> str | None:
    """Admit a token only in its strict shape, without a long digit run, and unchanged by the log scrubber."""
    if pattern.fullmatch(token) is None or (not numeric and _DIGIT_RUN.search(token) is not None):
        return None
    return token if scrub_text(token) == token else None
