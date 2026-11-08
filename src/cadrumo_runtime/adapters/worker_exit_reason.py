"""The bounded, identifier-only account of why a profile worker process ended."""

from __future__ import annotations

import contextlib
import re
from threading import Lock, Thread
from typing import BinaryIO, Final

from cadrumo.core.diagnostic_log import DiagnosticValue
from cadrumo.core.log_scrubbing import scrub_text

WORKER_STANDARD_ERROR_BYTES: Final = 4096
"""How much of a worker's standard error is held in memory, only as the source an exit account parses."""

WORKER_ERROR_FRAMES: Final = 8
"""How many of the final exception's innermost frames an exit account names."""

WORKER_STANDARD_ERROR_SETTLE_SECONDS: Final = 0.5
"""How long an exit account waits for the output's end after the worker exited.

A descendant that inherited the pipe can hold it open; what arrived by then is used.
"""

_READ_CHUNK_BYTES: Final = 4096

_TRACEBACK_HEADER: Final = "Traceback (most recent call last):"

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


class WorkerStandardErrorTail:
    """Drain a worker's private standard error for its whole life, holding only its end in memory.

    Nothing is written to disk or logged as it arrives. The held bytes are
    read only by :func:`worker_exit_fields`, which takes identifiers from
    them and lets no text of the output itself out.
    """

    def __init__(self, stream: BinaryIO) -> None:
        """Start draining on a daemon thread that closes the stream at the end of the output."""
        self._stream = stream
        self._lock = Lock()
        self._held = bytearray()
        self._drain = Thread(target=self._read, name="profile-worker-standard-error", daemon=True)
        try:
            self._drain.start()
        except BaseException:
            stream.close()
            raise

    def settled(self, *, timeout: float = WORKER_STANDARD_ERROR_SETTLE_SECONDS) -> bytes:
        """Wait up to ``timeout`` for the output to end and return its held end."""
        self._drain.join(timeout)
        with self._lock:
            return bytes(self._held)

    def _read(self) -> None:
        try:
            with contextlib.suppress(OSError, ValueError):
                reader = getattr(self._stream, "read1", self._stream.read)
                while chunk := reader(_READ_CHUNK_BYTES):
                    with self._lock:
                        self._held += chunk
                        del self._held[:-WORKER_STANDARD_ERROR_BYTES]
        finally:
            with contextlib.suppress(OSError):
                self._stream.close()


def worker_exit_fields(*, exit_code: int | None, standard_error: bytes | None) -> dict[str, DiagnosticValue]:
    """Name a worker exit by its status and its final exception's type and frame locations.

    No message, source line or other text of the output is returned. A type
    or frame token that is not a strict identifier, file name or line number,
    or that the canonical log scrubber would alter, is dropped.
    ``standard_error`` is ``None`` where the platform's launch does not
    capture it.
    """
    fields: dict[str, DiagnosticValue] = {"exit_code": exit_code}
    if standard_error is None:
        return fields
    error_type, frames, innermost_admitted = _final_exception(_held_lines(standard_error))
    if error_type is not None:
        fields["worker_error_type"] = error_type
    if frames:
        if innermost_admitted:
            fields["worker_error_origin"] = frames[0]
        fields["worker_error_frames"] = " <- ".join(frames[:WORKER_ERROR_FRAMES])
    return fields


def _held_lines(standard_error: bytes) -> tuple[list[str], bool]:
    text = standard_error.decode("utf-8", errors="replace")
    lines = text.splitlines()
    truncated = len(standard_error) >= WORKER_STANDARD_ERROR_BYTES
    if truncated and lines:
        # The held bytes begin mid-line once the bound discarded the output before them.
        lines = lines[1:]
    return [line.rstrip() for line in lines if line.strip()], truncated


def _final_exception(held: tuple[list[str], bool]) -> tuple[str | None, list[str], bool]:
    """Read the last traceback's type and its frames, innermost first; never a message or source line."""
    lines, truncated = held
    starts = [index for index, line in enumerate(lines) if line == _TRACEBACK_HEADER]
    if starts:
        body = lines[starts[-1] + 1 :]
    elif truncated:
        # A long traceback's header can precede the held bytes; its frames still follow.
        body = lines
    else:
        return None, [], False
    frames: list[str] = []
    innermost_admitted = False
    for line in body:
        frame_line = _FRAME_LINE.match(line)
        if frame_line is not None:
            frame = _frame_identity(frame_line)
            innermost_admitted = frame is not None
            if frame is not None:
                frames.append(frame)
            continue
        if line[:1].isspace():
            continue
        exception = _EXCEPTION_LINE.match(line)
        error_type = None if exception is None else _admitted(str(exception.group("type")), _EXCEPTION_TYPE)
        return error_type, frames[::-1], innermost_admitted
    return None, frames[::-1], innermost_admitted


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
