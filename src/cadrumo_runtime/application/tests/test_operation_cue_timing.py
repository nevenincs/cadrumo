"""Cue diagnostics remain bounded, INFO-visible and independent of operation outcomes."""

from __future__ import annotations

import logging
from hashlib import sha256
from threading import Event, Lock, Thread

import pytest

from cadrumo.core.diagnostic_log import DiagnosticFormatter
from cadrumo.core.logging import LOG_FILE_FORMAT, flush_logging

from .. import operation_cue_timing

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.fixture(autouse=True)
def isolated_diagnostic_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(operation_cue_timing, "_line_counts", {})
    monkeypatch.setattr(operation_cue_timing, "_budget_lock", Lock())


def test_actual_dispatch_and_scrubber_keep_joinable_ids_without_private_content(
    caplog: pytest.LogCaptureFixture,
) -> None:
    identifiers = tuple(sha256(f"synthetic operation {index}".encode()).hexdigest() for index in range(4))
    private = "synthetic-private-password-and-profile-path"
    with caplog.at_level(logging.INFO), caplog.at_level(logging.INFO, logger=operation_cue_timing.__name__):
        operation_cue_timing.log_operation_cue_timing(
            "publish_cues_complete", (*identifiers[:3], private, identifiers[3]), cue_attempt_count=0
        )
        assert flush_logging(timeout=5)
    records = [record for record in caplog.records if record.name == operation_cue_timing.__name__]
    assert len(records) == 1
    assert records[0].levelno == logging.INFO
    rendered = DiagnosticFormatter(LOG_FILE_FORMAT).format(records[0])
    assert all(identifier in rendered for identifier in identifiers[:3])
    assert identifiers[3] not in rendered
    assert private not in rendered
    assert " batch_count=5 truncated=True cue_attempt_count=0" in rendered
    assert "invalid" not in rendered


def test_timing_has_only_bounded_opaque_ids_and_two_clocks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(operation_cue_timing, "time_ns", lambda: 123_456_789)
    monkeypatch.setattr(operation_cue_timing, "monotonic_ns", lambda: 987_654_321)
    identifiers = tuple(character * 64 for character in "abcdef")
    records: list[tuple[str, int]] = []

    def record(_logger: logging.Logger, event: str, *, level: int, primary_error: BaseException | None) -> None:
        records.append((event, level))

    monkeypatch.setattr(operation_cue_timing._LOGGER, "isEnabledFor", lambda _level: True)
    monkeypatch.setattr(operation_cue_timing, "diagnostic_event", record)
    operation_cue_timing.log_operation_cue_timing("report_send", identifiers)
    assert len(records) == 1
    message, level = records[0]
    assert level == logging.INFO
    assert message == (
        "operation cue timing stage=report_send epoch_ms=123 monotonic_ns=987654321 "
        f"operation_ids={','.join(identifiers[:4])} batch_count=6 truncated=True"
    )
    assert identifiers[4] not in message and identifiers[5] not in message


def test_invalid_identifier_never_becomes_diagnostic_content(monkeypatch: pytest.MonkeyPatch) -> None:
    messages: list[str] = []

    def record(_logger: logging.Logger, event: str, *, level: int, primary_error: BaseException | None) -> None:
        messages.append(event)

    monkeypatch.setattr(operation_cue_timing._LOGGER, "isEnabledFor", lambda _level: True)
    monkeypatch.setattr(operation_cue_timing, "diagnostic_event", record)
    operation_cue_timing.log_operation_cue_timing("parent_received", ("private-profile-path-or-payload",))
    assert not messages
    assert not operation_cue_timing._line_counts


def test_no_observers_is_explicitly_zero_attempts(monkeypatch: pytest.MonkeyPatch) -> None:
    messages: list[str] = []

    def record(_logger: logging.Logger, event: str, *, level: int, primary_error: BaseException | None) -> None:
        messages.append(event)

    monkeypatch.setattr(operation_cue_timing._LOGGER, "isEnabledFor", lambda _level: True)
    monkeypatch.setattr(operation_cue_timing, "diagnostic_event", record)
    operation_cue_timing.log_operation_cue_timing("publish_cues_complete", ("a" * 64,), cue_attempt_count=0)
    assert len(messages) == 1
    assert messages[0].endswith("batch_count=1 truncated=False cue_attempt_count=0")


def test_warning_level_does_not_read_clocks(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[bool] = []

    def unavailable_clock() -> int:
        calls.append(True)
        raise AssertionError("disabled diagnostics must not read a clock")

    monkeypatch.setattr(operation_cue_timing, "time_ns", unavailable_clock)
    previous_level = operation_cue_timing._LOGGER.level
    operation_cue_timing._LOGGER.setLevel(logging.WARNING)
    try:
        operation_cue_timing.log_operation_cue_timing("commit_observed", ("a" * 64,))
    finally:
        operation_cue_timing._LOGGER.setLevel(previous_level)
    assert not calls
    assert not operation_cue_timing._line_counts


def test_each_operation_has_32_lines_even_in_repeated_or_mixed_batches(monkeypatch: pytest.MonkeyPatch) -> None:
    messages: list[str] = []

    def record(_logger: logging.Logger, event: str, *, level: int, primary_error: BaseException | None) -> None:
        messages.append(event)

    monkeypatch.setattr(operation_cue_timing._LOGGER, "isEnabledFor", lambda _level: True)
    monkeypatch.setattr(operation_cue_timing, "diagnostic_event", record)
    first, second = "a" * 64, "b" * 64
    for _ in range(40):
        operation_cue_timing.log_operation_cue_timing("report_send", (first, first))
    assert len(messages) == 32
    assert operation_cue_timing._line_counts == {first: 32}
    operation_cue_timing.log_operation_cue_timing("report_send", (first, second))
    assert len(messages) == 33
    assert first not in messages[-1] and second in messages[-1]
    assert "batch_count=2 truncated=True" in messages[-1]


def test_capacity_drops_new_operations_without_resetting_existing_budgets(monkeypatch: pytest.MonkeyPatch) -> None:
    messages: list[str] = []

    def record(_logger: logging.Logger, event: str, *, level: int, primary_error: BaseException | None) -> None:
        messages.append(event)

    monkeypatch.setattr(operation_cue_timing._LOGGER, "isEnabledFor", lambda _level: True)
    monkeypatch.setattr(operation_cue_timing, "diagnostic_event", record)
    identifiers = tuple(sha256(f"synthetic budget {index}".encode()).hexdigest() for index in range(1025))
    for identifier in identifiers:
        operation_cue_timing.log_operation_cue_timing("report_send", (identifier,))
    assert len(messages) == len(operation_cue_timing._line_counts) == 1024
    assert identifiers[-1] not in operation_cue_timing._line_counts
    operation_cue_timing.log_operation_cue_timing("report_send", (identifiers[0], identifiers[-1]))
    assert operation_cue_timing._line_counts[identifiers[0]] == 2
    assert identifiers[-1] not in messages[-1]


def test_contended_budget_drops_without_waiting_or_reading_clocks(monkeypatch: pytest.MonkeyPatch) -> None:
    clock_reads: list[bool] = []
    finished = Event()

    def clock() -> int:
        clock_reads.append(True)
        return 1

    def observe() -> None:
        operation_cue_timing.log_operation_cue_timing("report_send", ("a" * 64,))
        finished.set()

    monkeypatch.setattr(operation_cue_timing._LOGGER, "isEnabledFor", lambda _level: True)
    monkeypatch.setattr(operation_cue_timing, "time_ns", clock)
    with operation_cue_timing._budget_lock:
        thread = Thread(target=observe, daemon=True)
        thread.start()
        assert finished.wait(2), "diagnostic contention must never wait for a budget lock"
    thread.join(2)
    assert not clock_reads and not operation_cue_timing._line_counts


def test_budget_lock_is_released_before_clocks_and_logging(monkeypatch: pytest.MonkeyPatch) -> None:
    observed: list[str] = []

    def check_unlocked(stage: str) -> None:
        assert operation_cue_timing._budget_lock.acquire(blocking=False)
        operation_cue_timing._budget_lock.release()
        observed.append(stage)

    def clock() -> int:
        check_unlocked("clock")
        return 1

    def record(*args: object, **kwargs: object) -> None:
        check_unlocked("logger")

    monkeypatch.setattr(operation_cue_timing._LOGGER, "isEnabledFor", lambda _level: True)
    monkeypatch.setattr(operation_cue_timing, "time_ns", clock)
    monkeypatch.setattr(operation_cue_timing, "monotonic_ns", clock)
    monkeypatch.setattr(operation_cue_timing, "diagnostic_event", record)
    operation_cue_timing.log_operation_cue_timing("report_send", ("a" * 64,))
    assert observed == ["clock", "clock", "logger"]


@pytest.mark.parametrize("boundary", ["clock", "logger"])
def test_diagnostic_failure_does_not_change_operation_result(monkeypatch: pytest.MonkeyPatch, boundary: str) -> None:
    def failed_clock() -> int:
        raise OSError("private clock details")

    def failed_logger(*args: object, **kwargs: object) -> None:
        raise OSError("private logger details")

    monkeypatch.setattr(operation_cue_timing._LOGGER, "isEnabledFor", lambda _level: True)
    if boundary == "clock":
        monkeypatch.setattr(operation_cue_timing, "time_ns", failed_clock)
    else:
        monkeypatch.setattr(operation_cue_timing, "diagnostic_event", failed_logger)
    operation_cue_timing.log_operation_cue_timing("report_send", ("a" * 64,))


def test_diagnostic_interrupt_preserves_an_active_primary(monkeypatch: pytest.MonkeyPatch) -> None:
    def interrupted_clock() -> int:
        raise KeyboardInterrupt

    monkeypatch.setattr(operation_cue_timing._LOGGER, "isEnabledFor", lambda _level: True)
    monkeypatch.setattr(operation_cue_timing, "time_ns", interrupted_clock)
    primary = SystemExit("primary operation interruption")
    operation_cue_timing.log_operation_cue_timing("report_unacknowledged", ("a" * 64,), primary_error=primary)
    with pytest.raises(KeyboardInterrupt):
        operation_cue_timing.log_operation_cue_timing("report_send", ("a" * 64,))


def test_a_settlement_is_logged_after_its_operation_spent_its_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    messages: list[str] = []

    def record(_logger: logging.Logger, event: str, *, level: int, primary_error: BaseException | None) -> None:
        messages.append(event)

    monkeypatch.setattr(operation_cue_timing._LOGGER, "isEnabledFor", lambda _level: True)
    monkeypatch.setattr(operation_cue_timing, "diagnostic_event", record)
    spent, other = "a" * 64, "b" * 64
    for _ in range(40):
        operation_cue_timing.log_operation_cue_timing("fanout_start", (spent,))
    assert len(messages) == 32
    operation_cue_timing.log_operation_cue_timing("fanout_start", (spent,))
    assert len(messages) == 32
    # Named fifth in its batch, the settlement still comes first among the four kept.
    batch = (*(character * 64 for character in "cdef"), spent)
    operation_cue_timing.log_operation_cue_timing("publish_cues_complete", batch, cue_attempt_count=1, settled=(spent,))
    operation_cue_timing.log_operation_cue_timing("parent_ack_written", (other, spent), settled=(spent,))
    assert len(messages) == 34
    assert f"operation_ids={spent},{'c' * 64},{'d' * 64},{'e' * 64} " in messages[32]
    assert messages[32].endswith("batch_count=5 truncated=True cue_attempt_count=1 settled_count=1")
    assert f"operation_ids={spent},{other} " in messages[33]
    assert messages[33].endswith("settled_count=1")
    assert operation_cue_timing._line_counts[spent] == 32
