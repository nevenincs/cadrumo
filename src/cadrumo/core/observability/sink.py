"""Logging handler that bridges :mod:`logging` to JSONL run events.

The handler subscribes to the standard :mod:`logging` machinery so any
caller using :func:`cadrumo.core.logging.get_logger` automatically picks
up the JSONL sink while a
:func:`cadrumo.core.observability.run_context` is active. Records that do
not carry a ``run_event`` extra are skipped — bare log lines never
leak into ``events.jsonl``.

The ``run_id`` / ``step_id`` attributes are stamped onto every
:class:`logging.LogRecord` by the factory installed in
:mod:`cadrumo.core.logging`.

Each sink instance is bound to a single ``run_id`` and filters any
event whose ``run_id`` does not match. This prevents cross-run
contamination when several
:func:`cadrumo.core.observability.run_context` blocks execute concurrently
(e.g. tasks in an :mod:`asyncio` event loop) and therefore have
competing sinks attached to the root logger at the same time.
"""

from __future__ import annotations

import json

# LOGGING-STDLIB-RATIONALE-SINK-HANDLER:
# JsonlRunSink subclasses logging.Handler and accepts logging.LogRecord; stdlib
# import is required by the ABC contract.
import logging  # LOGGING-STDLIB-RATIONALE-SINK-HANDLER
import os
import threading
from pathlib import Path
from typing import TextIO, override

from ..logging import get_logger
from .models import RunEvent
from .redaction_rules import diagnostic_rules
from .store import EVENTS_APPEND_LOCK

logger = get_logger(__name__)


class JsonlRunSink(logging.Handler):
    """Append-only JSONL sink for :class:`cadrumo.core.observability.RunEvent` records.

    The handler opens the target path lazily on first emit so a
    :func:`cadrumo.core.observability.run_context` enter is cheap when no
    events ever fire. Each emit flushes the file handle;
    :meth:`close` additionally calls :func:`os.fsync` so a process kill
    mid-run still leaves a durable JSONL trailer on disk.

    Concurrency: the sink is bound to a single ``run_id`` and rejects
    events carrying a different ``run_id``. File-handle mutations are
    guarded by the shared event-store lock plus an internal
    :class:`threading.Lock`, so direct appends and sink emissions cannot
    interleave bytes on disk.
    """

    def __init__(self, target: Path, *, run_id: str) -> None:
        """Construct a sink bound to a specific JSONL file path and run.

        Args:
            target: Path of the ``events.jsonl`` file this sink writes.
                The parent directory is created eagerly.
            run_id: The owning run identifier. Events whose ``run_id``
                does not match are dropped silently so concurrent runs
                that share the same root logger stay isolated.
        """
        super().__init__(level=logging.DEBUG)
        self._target: Path = target
        self._run_id: str = run_id
        self._handle: TextIO | None = None
        self._lock: threading.Lock = threading.Lock()
        target.parent.mkdir(parents=True, exist_ok=True)

    @property
    def run_id(self) -> str:
        """The run identifier this sink is bound to."""
        return self._run_id

    @override
    def emit(self, record: logging.LogRecord) -> None:
        """Write the JSON-encoded :class:`RunEvent` carried by ``record``.

        Drops the record when there is no ``run_event`` extra or when
        the event belongs to a different run — see the module docstring
        for the concurrency rationale.

        JSON serialisation runs outside the file-handle lock so
        concurrent threads can encode in parallel; only the write and
        flush are serialised. The whole emit path (including the
        encode) is wrapped in a single ``try`` — a serialisation
        failure (e.g. the pydantic model grew a non-JSON-safe field in
        a future refactor) must not crash the logging system, and must
        instead fall through to ``handleError`` like any other
        handler failure.
        """
        event = getattr(record, "run_event", None)
        if not isinstance(event, RunEvent):
            return
        if event.run_id != self._run_id:
            return
        try:
            # Run traces are DIAGNOSTIC class. The substrate's redaction
            # rule set walks every string leaf (NIF SHA-256-prefixed, URL
            # host-only, bearer-shaped tokens fingerprinted, opaque
            # bearers fingerprinted) before serialisation so the JSONL
            # never carries a plaintext NIF / token / URL path even if
            # a caller feeds one in. Encoding happens outside the lock
            # — pydantic dump and dict walk are CPU-bound and
            # thread-safe on a frozen model, so holding the lock across
            # the encode step would serialise work that does not need
            # mutual exclusion.
            from ..redaction.rules import redact_structured

            redacted = redact_structured(event.model_dump(mode="json"), rules=diagnostic_rules())
            line = json.dumps(redacted, sort_keys=True, separators=(",", ":")) + "\n"
            with EVENTS_APPEND_LOCK, self._lock:
                handle = self._open()
                handle.write(line)
                handle.flush()
        except Exception:
            # Stdlib logging.Handler.emit contract: any emit-side failure
            # must route through handleError(record) so the application is
            # never killed by a logging path. Broad catch is mandated by
            # the cpython logging module's documented protocol.
            logger.warning("jsonl run sink emit failed", exc_info=True)
            self.handleError(record)

    def _open(self) -> TextIO:
        r"""Lazily open the JSONL file in append mode.

        ``newline=""`` disables the Python text-mode newline translation
        (CRLF on Windows) so ``events.jsonl`` stays byte-stable across
        platforms — emitting exactly one ``\\n`` per record on every OS.
        """
        if self._handle is None:
            self._handle = self._target.open("a", encoding="utf-8", newline="")
        return self._handle

    @override
    def close(self) -> None:
        """Flush, :func:`os.fsync`, and close the underlying file handle.

        Always invokes the base :meth:`logging.Handler.close` so the
        handler is removed from the logging registry even when the
        flush or fsync raises.
        """
        try:
            with EVENTS_APPEND_LOCK, self._lock:
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
