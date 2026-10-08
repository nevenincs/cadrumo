"""Startup phase timing records keep a fixed shape and never replace a primary error."""

from __future__ import annotations

import logging
from typing import override

import pytest

from ..logging import get_logger
from ..startup_phase_log import log_startup_phase, startup_phase

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


class _Capture(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.records: list[logging.LogRecord] = []

    @override
    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


class _Interrupted(BaseException):
    pass


def _raising_filter(error: BaseException) -> logging.Filter:
    class _Raising(logging.Filter):
        @override
        def filter(self, record: logging.LogRecord) -> bool:
            raise error

    return _Raising()


def _logger() -> tuple[logging.Logger, _Capture]:
    get_logger("cadrumo.tests.startup_phase_log")
    logger = logging.Logger("cadrumo.tests.startup_phase_log", level=logging.INFO)
    logger.propagate = False
    capture = _Capture()
    logger.addHandler(capture)
    return logger, capture


def _fields(record: logging.LogRecord) -> tuple[object, object, object]:
    return (
        record.__dict__["startup_phase"],
        record.__dict__["transition"],
        record.__dict__["elapsed_seconds"],
    )


def test_enter_record_has_fixed_message_and_extras() -> None:
    logger, capture = _logger()

    log_startup_phase(logger, "manager_start", "enter", 0.0)

    (record,) = capture.records
    assert record.levelno == logging.INFO
    assert record.name == "cadrumo.tests.startup_phase_log"
    assert record.getMessage() == "runtime_startup phase=manager_start transition=enter elapsed_seconds=0.000000"
    assert _fields(record) == ("manager_start", "enter", 0.0)
    assert record.__dict__["outcome"] == "entered"


def test_context_manager_emits_enter_then_non_negative_leave() -> None:
    logger, capture = _logger()

    with startup_phase(logger, "readiness_wait"):
        assert [r.__dict__["transition"] for r in capture.records] == ["enter"]

    enter, leave = capture.records
    assert enter.getMessage() == "runtime_startup phase=readiness_wait transition=enter elapsed_seconds=0.000000"
    phase, transition, elapsed = _fields(leave)
    assert (phase, transition) == ("readiness_wait", "leave")
    assert isinstance(elapsed, float)
    assert elapsed >= 0.0
    assert leave.getMessage() == f"runtime_startup phase=readiness_wait transition=leave elapsed_seconds={elapsed:.6f}"
    assert leave.__dict__["outcome"] == "completed"
    assert enter.__dict__["_cadrumo_diagnostic_id"] == leave.__dict__["_cadrumo_diagnostic_id"]


def test_ordinary_logging_failure_is_swallowed() -> None:
    logger, capture = _logger()
    logger.addFilter(_raising_filter(RuntimeError("synthetic logging failure")))

    log_startup_phase(logger, "bootstrap", "enter", 0.0)
    with startup_phase(logger, "main_import"):
        pass

    assert capture.records == []


def test_base_exception_from_logging_is_raised_without_a_primary() -> None:
    logger, _ = _logger()
    interruption = _Interrupted()
    logger.addFilter(_raising_filter(interruption))

    with pytest.raises(_Interrupted) as raised:
        log_startup_phase(logger, "bootstrap", "leave", 1.0)

    assert raised.value is interruption


def test_base_exception_from_logging_is_suppressed_behind_a_primary() -> None:
    logger, _ = _logger()
    logger.addFilter(_raising_filter(_Interrupted()))

    log_startup_phase(logger, "bootstrap", "leave", 1.0, primary_error=ValueError("primary"))


def test_context_manager_propagates_body_error_as_the_primary() -> None:
    logger, capture = _logger()
    primary = ValueError("body failure")

    with pytest.raises(ValueError) as raised, startup_phase(logger, "manager_inspect"):
        raise primary

    assert raised.value is primary
    assert [_fields(r)[:2] for r in capture.records] == [("manager_inspect", "enter"), ("manager_inspect", "leave")]
    assert capture.records[-1].levelno == logging.WARNING
    assert capture.records[-1].__dict__["outcome"] == "failed"
    assert capture.records[-1].__dict__["error_type"] == "ValueError"
    assert "body failure" not in capture.records[-1].getMessage()


def test_context_manager_keeps_body_error_when_leave_logging_is_interrupted() -> None:
    logger, capture = _logger()
    primary = ValueError("body failure")

    with pytest.raises(ValueError) as raised, startup_phase(logger, "existing_connect"):
        logger.addFilter(_raising_filter(_Interrupted()))
        raise primary

    assert raised.value is primary
    assert [_fields(r)[1] for r in capture.records] == ["enter"]


def test_context_manager_raises_leave_interruption_without_a_body_error() -> None:
    logger, _ = _logger()

    with pytest.raises(_Interrupted), startup_phase(logger, "existing_connect"):
        logger.addFilter(_raising_filter(_Interrupted()))
