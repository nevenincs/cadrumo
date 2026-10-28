"""What the asynchronous diagnostic dispatch delivered to a test, observed once it has drained."""

from __future__ import annotations

import logging

import pytest

from cadrumo.core.logging import _AsyncDiagnosticHandler, flush_logging


def delivered_records(caplog: pytest.LogCaptureFixture, logger_name: str | None = None) -> list[logging.LogRecord]:
    """Return the records ``logger_name`` emitted, after the asynchronous dispatch has drained.

    A project logger hands its record to the capture handler from the dispatch
    thread rather than from the logging call, so the dispatch is flushed first.
    ``None`` selects every logger, for a check that no logger leaked a value.
    """
    assert flush_logging(timeout=5)
    return [record for record in caplog.records if logger_name is None or record.name == logger_name]


def delivered_text(caplog: pytest.LogCaptureFixture) -> str:
    """Return the capture handler's formatted text, tracebacks included, after the asynchronous dispatch has drained."""
    assert flush_logging(timeout=5)
    return caplog.text


def delivery_sinks() -> list[logging.Handler]:
    """Return the handler that decides what is written for each root handler, after a drain.

    The project's root handlers are asynchronous wrappers that stay at ``NOTSET``
    and pass a record to a sink on a thread of its own, so a wrapper's ``level``
    and type say nothing about what is written: the sink carries the level and
    the file or stream. A level change is queued behind the records before it,
    so the dispatch is flushed first. A handler that is not a wrapper is its
    own sink.
    """
    assert flush_logging(timeout=5)
    return [
        handler.sink if isinstance(handler, _AsyncDiagnosticHandler) else handler
        for handler in tuple(logging.getLogger().handlers)
    ]
