"""Logging handler that bridges :mod:`logging` to JSONL run events.

The handler subscribes to the standard :mod:`logging` machinery so any
caller using ``aeat.logging.get_logger`` automatically picks up the
JSONL sink while a run context is active. Records that do not carry a
``run_event`` extra are skipped — bare log lines never leak into
``events.jsonl``.

The ``run_id`` / ``step_id`` attributes are stamped onto every
:class:`logging.LogRecord` by the factory installed in
:mod:`aeat.logging` (``_install_run_context_record_factory``).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TextIO

from aeat.observability._models import RunEvent


class JsonlRunSink(logging.Handler):
    """Append-only JSONL sink for :class:`RunEvent` records.

    The handler opens the target path lazily on first emit so a
    ``run_context`` enter is cheap when no events ever fire. Each emit
    flushes the file handle; ``close()`` additionally calls
    :func:`os.fsync` so a process kill mid-run still leaves a
    durable JSONL trailer on disk.
    """

    def __init__(self, target: Path) -> None:
        """Construct the sink for a specific JSONL file path."""
        super().__init__(level=logging.DEBUG)
        self._target: Path = target
        self._handle: TextIO | None = None
        target.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, record: logging.LogRecord) -> None:
        """Write the JSON-encoded :class:`RunEvent` carried by ``record``."""
        event = getattr(record, "run_event", None)
        if not isinstance(event, RunEvent):
            return
        try:
            handle = self._open()
            handle.write(event.model_dump_json() + "\n")
            handle.flush()
        except Exception:
            self.handleError(record)

    def _open(self) -> TextIO:
        """Lazily open the JSONL file in append mode."""
        if self._handle is None:
            self._handle = self._target.open("a", encoding="utf-8")
        return self._handle

    def close(self) -> None:
        """Flush + fsync + close the underlying file handle."""
        try:
            handle = self._handle
            if handle is not None:
                try:
                    handle.flush()
                    os.fsync(handle.fileno())
                finally:
                    handle.close()
                    self._handle = None
        finally:
            super().close()


__all__ = [
    "JsonlRunSink",
]
