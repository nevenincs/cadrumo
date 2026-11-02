"""Closing a view leg's channel never raises and never logs more than the failure's type."""

from __future__ import annotations

import logging
from typing import cast

import pytest

from cadrumo.core.diagnostic_log import diagnostic_scope
from cadrumo.core.logging import flush_logging
from cadrumo_client.contracts.contracts import ByteChannel

from ..view_stream_state import close_view_leg_quietly

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


class _Channel:
    def __init__(self, failure: Exception | None) -> None:
        self._failure = failure
        self.closed = 0

    def close(self) -> None:
        self.closed += 1
        if self._failure is not None:
            raise self._failure


def test_a_close_failure_is_swallowed_and_logged_by_type_only(caplog: pytest.LogCaptureFixture) -> None:
    channel = _Channel(OSError("secret-path-detail"))

    with caplog.at_level(logging.WARNING), diagnostic_scope(new=True):
        close_view_leg_quietly(cast(ByteChannel, channel))
        assert flush_logging(timeout=5.0)

    assert channel.closed == 1
    records = [record for record in caplog.records if record.getMessage() == "view_leg_close_failed"]
    assert len(records) == 1
    assert records[0].levelno >= logging.WARNING
    assert records[0].__dict__["error_type"] == "OSError"
    assert "secret-path-detail" not in caplog.text


def test_a_clean_close_logs_nothing(caplog: pytest.LogCaptureFixture) -> None:
    channel = _Channel(None)

    with caplog.at_level(logging.DEBUG), diagnostic_scope(new=True):
        close_view_leg_quietly(cast(ByteChannel, channel))
        assert flush_logging(timeout=5.0)

    assert channel.closed == 1
    assert not [record for record in caplog.records if record.getMessage() == "view_leg_close_failed"]
