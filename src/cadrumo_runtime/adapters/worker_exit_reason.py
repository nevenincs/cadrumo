"""The bounded, identifier-only account of why a profile worker process ended."""

from __future__ import annotations

import contextlib
from threading import Lock, Thread
from typing import BinaryIO, Final

from cadrumo.core.diagnostic_log import DiagnosticValue
from cadrumo.core.traceback_summary import SUMMARY_FRAMES, TRACEBACK_HEADER, TracebackReader, TracebackSummary

WORKER_STANDARD_ERROR_BYTES: Final = 4096
"""How much of a worker's standard error is held in memory, only as the source an exit account parses."""

WORKER_STANDARD_ERROR_SETTLE_SECONDS: Final = 0.5
"""How long an exit account waits for the output's end after the worker exited.

A descendant that inherited the pipe can hold it open; what arrived by then is used.
"""

_READ_CHUNK_BYTES: Final = 4096


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
    summary = _final_exception(_held_lines(standard_error))
    if summary is None:
        return fields
    if summary.error_type is not None:
        fields["worker_error_type"] = summary.error_type
    if summary.origin is not None:
        fields["worker_error_origin"] = summary.origin
    if summary.frames:
        fields["worker_error_frames"] = " <- ".join(summary.frames[:SUMMARY_FRAMES])
    return fields


def _held_lines(standard_error: bytes) -> tuple[list[str], bool]:
    text = standard_error.decode("utf-8", errors="replace")
    lines = text.splitlines()
    truncated = len(standard_error) >= WORKER_STANDARD_ERROR_BYTES
    if truncated and lines:
        # The held bytes begin mid-line once the bound discarded the output before them.
        lines = lines[1:]
    return [line.rstrip() for line in lines if line.strip()], truncated


def _final_exception(held: tuple[list[str], bool]) -> TracebackSummary | None:
    """Read the last traceback's type and frames, innermost first; never a message or source line."""
    lines, truncated = held
    starts = [index for index, line in enumerate(lines) if line == TRACEBACK_HEADER]
    if starts:
        body = lines[starts[-1] + 1 :]
    elif truncated:
        # A long traceback's header can precede the held bytes; its frames still follow.
        body = lines
    else:
        return None
    reader = TracebackReader()
    for line in body:
        if (summary := reader.read(line)) is not None:
            return summary
    return reader.unfinished()
