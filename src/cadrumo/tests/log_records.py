"""Records a project logger delivered to a test's capture handler, once each."""

from __future__ import annotations

import logging

import pytest

from cadrumo.core.logging import flush_logging


def delivered_records(caplog: pytest.LogCaptureFixture, logger_name: str | None = None) -> list[logging.LogRecord]:
    """Return the distinct records ``logger_name`` emitted, after the asynchronous dispatch has drained.

    Delivery to the capture handler is not synchronous with the logging call,
    so the dispatch is flushed first. The first record a process emits can
    reach a root handler twice as the same object; it counts once here.
    ``None`` selects every logger, for a check that no logger leaked a value.
    """
    assert flush_logging(timeout=5)
    distinct = {id(record): record for record in caplog.records if logger_name is None or record.name == logger_name}
    return list(distinct.values())


def delivered_text(caplog: pytest.LogCaptureFixture) -> str:
    """Return the capture handler's formatted text, tracebacks included, after the asynchronous dispatch has drained."""
    assert flush_logging(timeout=5)
    return caplog.text
