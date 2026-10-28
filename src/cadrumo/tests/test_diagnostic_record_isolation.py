"""Diagnostic records one test leaves queued are delivered before the next test begins.

The two tests depend on running in file order, which the repository's
file-grouped distribution preserves. The second passes alone, and fails when
the first leaves its record queued and nothing drains it before the capture
handler of the second attaches.
"""

from __future__ import annotations

import logging
import time

import pytest

from ..core import log_scrubbing as project_logging
from ..core.logging import flush_logging, get_logger
from .hang_guard import HANG_GUARD_SECONDS

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_NAME = "cadrumo.tests.record_isolation"
_STALL_SECONDS = 0.4


def test_a_test_can_end_while_its_diagnostic_record_is_still_queued(monkeypatch: pytest.MonkeyPatch) -> None:
    redact = project_logging._scrub_record_message_and_args
    resume = time.monotonic() + _STALL_SECONDS

    def stalled(record: logging.LogRecord) -> None:
        time.sleep(max(0.0, resume - time.monotonic()))
        redact(record)

    monkeypatch.setattr(project_logging, "_scrub_record_message_and_args", stalled)
    get_logger(_NAME).warning("left queued by the previous test")

    assert not flush_logging(timeout=0.01)


def test_the_capture_of_the_next_test_holds_only_its_own_records(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.DEBUG):
        get_logger(_NAME).warning("own record")
        assert flush_logging(timeout=HANG_GUARD_SECONDS)

    assert [record.getMessage() for record in caplog.records if record.name == _NAME] == ["own record"]
