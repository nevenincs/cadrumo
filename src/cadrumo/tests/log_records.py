"""Records a project logger delivered to a test's capture handler, once each."""

from __future__ import annotations

import logging

import pytest

from cadrumo.core.logging import flush_logging


def delivered_records(caplog: pytest.LogCaptureFixture, logger_name: str) -> list[logging.LogRecord]:
    """Return the distinct records ``logger_name`` emitted, after the asynchronous dispatch has drained.

    Delivery to the capture handler is not synchronous with the logging call,
    so the dispatch is flushed first. The first record a process emits can
    reach a root handler twice as the same object; it counts once here.
    """
    assert flush_logging(timeout=5)
    distinct = {id(record): record for record in caplog.records if record.name == logger_name}
    return list(distinct.values())
