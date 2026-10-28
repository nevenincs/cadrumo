"""Records that reached a test's capture handler once the asynchronous dispatch has drained."""

from __future__ import annotations

import logging

import pytest

from cadrumo.core.logging import flush_logging


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
