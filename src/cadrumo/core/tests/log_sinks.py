"""The handlers that write behind the project's asynchronous root handlers, observed once the dispatch has drained."""

from __future__ import annotations

import logging

from cadrumo.tests.hang_guard import HANG_GUARD_SECONDS

from ..logging import _AsyncDiagnosticHandler, flush_logging


def delivery_sinks() -> list[logging.Handler]:
    """Return the handler that decides what is written for each root handler, after a drain.

    The project's root handlers are asynchronous wrappers that stay at ``NOTSET``
    and pass a record to a sink on a thread of its own, so a wrapper's ``level``
    and type say nothing about what is written: the sink carries the level and
    the file or stream. A level change is queued behind the records before it,
    so the dispatch is flushed first. A handler that is not a wrapper is its
    own sink.
    """
    assert flush_logging(timeout=HANG_GUARD_SECONDS)
    return [
        handler.sink if isinstance(handler, _AsyncDiagnosticHandler) else handler
        for handler in tuple(logging.getLogger().handlers)
    ]
