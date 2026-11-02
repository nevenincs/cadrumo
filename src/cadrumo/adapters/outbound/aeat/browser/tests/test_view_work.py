"""Background view work settles without raising and logs only the exception type."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable

import pytest

from ..._playwright import PlaywrightError
from ..view_work import settle

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_LOG = logging.getLogger("tests.view_work")


async def _raise(error: Exception) -> None:
    raise error


def _settle_and_collect(work: Awaitable[object], caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    with caplog.at_level(logging.DEBUG, logger=_LOG.name):
        asyncio.run(settle(work, _LOG))
    return [record for record in caplog.records if record.name == _LOG.name]


def test_a_playwright_failure_is_a_debug_note_with_the_type_name_only(caplog: pytest.LogCaptureFixture) -> None:
    records = _settle_and_collect(_raise(PlaywrightError("secret page detail")), caplog)

    assert [(record.levelno, record.getMessage()) for record in records] == [
        (logging.DEBUG, f"aeat view page work ended exc_type={PlaywrightError.__name__}")
    ]


def test_any_other_failure_is_an_error_with_the_type_name_only(caplog: pytest.LogCaptureFixture) -> None:
    records = _settle_and_collect(_raise(RuntimeError("secret page detail")), caplog)

    assert [(record.levelno, record.getMessage()) for record in records] == [
        (logging.ERROR, "aeat view page work failed exc_type=RuntimeError")
    ]


def test_work_that_completes_logs_nothing(caplog: pytest.LogCaptureFixture) -> None:
    async def finish() -> None:
        return None

    assert _settle_and_collect(finish(), caplog) == []
