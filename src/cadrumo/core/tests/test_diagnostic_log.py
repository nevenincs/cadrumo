"""Diagnostic metadata preserves UTC, context ownership and private-data bounds."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import threading
import time
import tracemalloc
from io import StringIO
from pathlib import Path
from threading import Barrier
from typing import cast, override

import pytest

from cadrumo.tests.log_records import delivered_records

from ..diagnostic_log import (
    DiagnosticFormatter,
    DiagnosticValue,
    diagnostic_event,
    diagnostic_phase,
    diagnostic_process,
    diagnostic_scope,
    diagnostic_slow_call,
    diagnostic_timing_event,
    stamp_diagnostic_record,
    stamp_diagnostic_scalar_fields,
)
from ..log_file_handler import AnnouncingRotatingFileHandler
from ..logging import LOG_FILE_FORMAT, SecretScrubbingFilter, flush_logging, get_logger

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_PRIVATE_INPUT_CANARY = "synthetic-private-password"


def _record() -> logging.LogRecord:
    record = logging.LogRecord("cadrumo.tests.diagnostics", logging.WARNING, __file__, 1, "result", (), None)
    record.created = 0.125
    stamp_diagnostic_record(record)
    return record


def _context(record: logging.LogRecord) -> tuple[str, dict[str, object]]:
    line = DiagnosticFormatter(LOG_FILE_FORMAT).format(record)
    message, suffix = line.split(" | ", 1)
    context: object = json.loads(suffix)
    assert isinstance(context, dict)
    return message, cast("dict[str, object]", context)


def test_formatter_keeps_utc_time_when_logging_supplies_a_date_format() -> None:
    formatter = DiagnosticFormatter(LOG_FILE_FORMAT, datefmt="%Y")
    record = _record()
    assert formatter.formatTime(record, datefmt="%Y") == "1970-01-01T00:00:00.125Z"
    assert formatter.format(record).startswith("1970-01-01T00:00:00.125Z [WARNING]")


def test_utc_record_contains_scrubbed_process_and_attempt_context() -> None:
    with diagnostic_process("tui"), diagnostic_scope() as identifier:
        record = _record()
    record.__dict__.update(outcome="refused", reason_code="runtime_unavailable", password=_PRIVATE_INPUT_CANARY)
    SecretScrubbingFilter().filter(record)

    message, context = _context(record)

    assert message == "1970-01-01T00:00:00.125Z [WARNING] cadrumo.tests.diagnostics: result"
    assert context == {
        "diagnostic_id": identifier,
        "outcome": "refused",
        "process_id": os.getpid(),
        "process_role": "tui",
        "thread_id": threading.get_ident(),
        "thread_name": threading.current_thread().name,
        "reason_code": "runtime_unavailable",
    }


def test_context_is_bounded_and_never_renders_non_scalar_extras() -> None:
    class PrivateObject:
        @override
        def __str__(self) -> str:
            raise AssertionError("an opaque private object must never be rendered")

    record = _record()
    record.__dict__["opaque"] = PrivateObject()
    record.__dict__["nested"] = {"private": "synthetic-private-taxpayer"}
    record.__dict__["run_event"] = PrivateObject()
    record.__dict__["run_id"] = ""
    record.__dict__["error_origin"] = "x" * 700
    record.__dict__["profile_label"] = "private-profile-label-canary"
    record.__dict__["tax_amount"] = 12345
    for index in range(50):
        record.__dict__[f"field_{index:02}"] = index
    record.__dict__["elapsed_seconds"] = float("nan")

    _, context = _context(record)

    assert len(context) <= 32
    assert context["error_origin"] == "x" * 512
    assert context["elapsed_seconds"] is None
    assert context["process_id"] == os.getpid()
    assert not {"opaque", "nested", "run_event", "run_id", "profile_label", "tax_amount"}.intersection(context)


def test_login_witness_context_allows_only_fixed_scalar_counts_and_spans() -> None:
    fields = {
        "inventory_complete": False,
        "inventory_login_count": 2,
        "retained_peer_witness_count": 1,
        "observed_active_count": 2,
        "observed_eligible_count": 0,
        "observed_unknown_count": 1,
        "inventory_elapsed_ms": 0.125,
        "observation_elapsed_ms": 1.5,
    }
    record = _record()
    record.__dict__.update(fields)
    record.__dict__["os_owner_id"] = "synthetic-private-owner-canary"
    record.__dict__["login_id"] = "synthetic-private-login-canary"
    record.__dict__["native_observation"] = {"sid": "synthetic-private-sid-canary"}
    record.__dict__["luid"] = 12345
    stamp_diagnostic_scalar_fields(record)

    _, context = _context(record)

    assert context == {
        "process_id": os.getpid(),
        "process_role": "python",
        "thread_id": threading.get_ident(),
        "thread_name": threading.current_thread().name,
        **fields,
    }
    assert "canary" not in record.__dict__["diagnostic_context"]

    record.__dict__["observed_unknown_count"] = {"private": "synthetic-private-canary"}
    record.__dict__["inventory_elapsed_ms"] = object()
    _, context = _context(record)
    assert "observed_unknown_count" not in context and "inventory_elapsed_ms" not in context


def test_worker_timing_context_allows_closed_dispatch_and_native_call_labels() -> None:
    fields = {
        "handler_name": "custody_control",
        "request_type": "ProfileWorkerRetireRequest",
        "request_action": "retire",
        "call_name": "containment",
        "held_call_name": "process_membership",
        "held_elapsed_seconds": 0.75,
        "elapsed_seconds": 0.75,
        "outcome": "completed",
    }
    record = _record()
    record.__dict__.update(fields)
    record.__dict__["session_id"] = "synthetic-private-session-canary"
    stamp_diagnostic_scalar_fields(record)

    _, context = _context(record)

    assert context == {
        "process_id": os.getpid(),
        "process_role": "python",
        "thread_id": threading.get_ident(),
        "thread_name": threading.current_thread().name,
        **fields,
    }
    assert "session_id" not in record.__dict__["diagnostic_context"]


def test_kdf_context_admits_fixed_phase_spans_and_cleanup_without_private_payloads() -> None:
    fields = {
        "stage": "ready_wait",
        "outcome": "failed",
        "error_type": "TimeoutError",
        "cleanup_status": "failed",
        "cleanup_incomplete": True,
        "cleanup_error_type": "OSError",
        "kdf_start_elapsed_ms": 1.25,
        "kdf_ready_wait_elapsed_ms": 0.0,
        "kdf_ready_attestation_elapsed_ms": None,
        "kdf_request_write_elapsed_ms": None,
        "kdf_result_wait_elapsed_ms": None,
        "kdf_clean_exit_elapsed_ms": None,
        "kdf_cleanup_elapsed_ms": 0.125,
        "kdf_cleanup_process_elapsed_ms": 0.075,
        "kdf_cleanup_pipes_elapsed_ms": 0.025,
        "kdf_cleanup_directory_elapsed_ms": 0.025,
        "request_type": "WorkerControlRequest",
        "request_action": "status",
        "operation_channel": False,
        "budget_seconds": 10.0,
        "queue_seconds": 0.1,
    }
    record = _record()
    record.__dict__.update(fields)
    for private_key in (
        "request",
        "response",
        "password",
        "profile_id",
        "worker_environment",
        "worker_argv",
        "neutral_root",
    ):
        record.__dict__[private_key] = "synthetic-private-kdf-canary"
    stamp_diagnostic_scalar_fields(record)

    _, context = _context(record)

    assert context == {
        "process_id": os.getpid(),
        "process_role": "python",
        "thread_id": threading.get_ident(),
        "thread_name": threading.current_thread().name,
        **fields,
    }
    assert "canary" not in record.__dict__["diagnostic_context"]
    record.__dict__["kdf_start_elapsed_ms"] = {"private": "synthetic-private-kdf-canary"}
    record.__dict__["cleanup_error_type"] = object()
    _, context = _context(record)
    assert "kdf_start_elapsed_ms" not in context and "cleanup_error_type" not in context


def test_suffix_escapes_newlines_and_scrubs_allowed_field_values_before_truncation() -> None:
    record = _record()
    record.__dict__["error_origin"] = 'module.py:4:function\n[ERROR] forged | {"outcome":"forged"}'
    record.__dict__["reason_code"] = "Bearer SYNTHETIC-SECRET-VALUE"
    record.__dict__["_cadrumo_diagnostic_id"] = "x" * 700
    SecretScrubbingFilter().filter(record)

    message, context = _context(record)
    line = DiagnosticFormatter(LOG_FILE_FORMAT).format(record)

    assert len(line.splitlines()) == 1
    assert message.endswith(": result")
    assert "<redacted>" in str(context["reason_code"])
    assert "SYNTHETIC-SECRET-VALUE" not in line
    assert context["diagnostic_id"] == "<redacted:payload>"

    long_identifier = "diagnostic-segment-" * 50
    record.__dict__["_cadrumo_diagnostic_id"] = long_identifier
    _, bounded = _context(record)
    assert bounded["diagnostic_id"] == long_identifier[:512]


def test_redaction_does_not_promote_an_opaque_extra_to_exported_text() -> None:
    class PrivatePath:
        @override
        def __str__(self) -> str:
            from pathlib import Path

            return str(Path.home() / "private-profile-canary")

    record = _record()
    record.__dict__["error_origin"] = PrivatePath()
    scrubber = SecretScrubbingFilter()
    scrubber.filter(record)
    original_scalars = record.__dict__["_cadrumo_scalar_fields"]
    scrubber.filter(record)

    _, context = _context(record)

    assert "error_origin" not in context
    assert record.__dict__["_cadrumo_scalar_fields"] == original_scalars


def test_multiline_message_keeps_context_on_its_header_before_message_and_exception_details() -> None:
    record = _record()
    record.msg = 'first\nsecond | {"process_id":999,"process_role":"foreign"}\nthird'
    record.__dict__["reason_code"] = "multiline_message"
    try:
        raise ValueError("synthetic diagnostic exception")
    except ValueError:
        record.exc_info = sys.exc_info()
    SecretScrubbingFilter().filter(record)

    lines = DiagnosticFormatter(LOG_FILE_FORMAT).format(record).splitlines()
    header, suffix = lines[0].split(" | ", 1)
    context: object = json.loads(suffix)
    assert isinstance(context, dict)
    assert header.endswith(": first")
    assert context["process_id"] == os.getpid()
    assert context["reason_code"] == "multiline_message"
    assert lines[1:3] == ['second | {"process_id":999,"process_role":"foreign"}', "third"]
    assert lines[3] == "Traceback (most recent call last):"
    assert lines[-1] == "ValueError: synthetic diagnostic exception"


@pytest.mark.asyncio
async def test_scopes_inherit_across_threads_and_fresh_attempts_are_distinct() -> None:
    logger = get_logger("cadrumo.tests.diagnostic_scope")

    def make_record() -> logging.LogRecord:
        return logger.makeRecord(logger.name, logging.INFO, __file__, 1, "probe", (), None)

    with diagnostic_process("tui"), diagnostic_scope() as process:
        with diagnostic_scope(new=True) as attempt, diagnostic_scope() as nested:
            record = await asyncio.to_thread(make_record)
        later = make_record()
        with diagnostic_scope(new=True) as second:
            assert second != attempt
    outside = make_record()

    assert nested == attempt and process != attempt
    assert record.__dict__["_cadrumo_diagnostic_id"] == attempt
    assert record.__dict__["_cadrumo_process_role"] == "tui"
    assert later.__dict__["_cadrumo_diagnostic_id"] == process
    assert outside.__dict__["_cadrumo_diagnostic_id"] is None


@pytest.mark.asyncio
async def test_concurrent_tasks_and_threads_keep_distinct_attempts_and_restore_parent_context() -> None:
    logger = get_logger("cadrumo.tests.concurrent_diagnostic_scope")
    ready = asyncio.Event()
    threaded = Barrier(4)
    identifiers: list[str] = []

    def make_record() -> logging.LogRecord:
        return logger.makeRecord(logger.name, logging.INFO, __file__, 1, "probe", (), None)

    def make_thread_record() -> logging.LogRecord:
        record = make_record()
        threaded.wait(timeout=5)
        return record

    async def attempt() -> tuple[str, tuple[logging.LogRecord, ...], logging.LogRecord]:
        with diagnostic_scope(new=True) as identifier:
            identifiers.append(identifier)
            if len(identifiers) == 8:
                ready.set()
            await asyncio.wait_for(ready.wait(), timeout=5)
            before = make_record()
            inherited = await asyncio.to_thread(make_thread_record)
            with diagnostic_scope() as nested:
                assert nested == identifier
                after = make_record()
        return identifier, (before, inherited, after), make_record()

    with diagnostic_process("tui"), diagnostic_scope() as parent:
        completed = await asyncio.gather(*(attempt() for _ in range(8)))
        parent_record = make_record()

    assert len(set(identifiers)) == 8 and parent not in identifiers
    for identifier, records, restored in completed:
        for record in records:
            _, context = _context(record)
            assert context["diagnostic_id"] == identifier
            assert context["process_role"] == "tui"
        assert restored.__dict__["_cadrumo_diagnostic_id"] == parent
    assert parent_record.__dict__["_cadrumo_diagnostic_id"] == parent


@pytest.mark.asyncio
async def test_cancelled_task_restores_its_parent_context_without_changing_sibling_records() -> None:
    entered = asyncio.Event()
    waiting = asyncio.Event()
    observed: list[logging.LogRecord] = []

    async def cancelled_attempt() -> None:
        try:
            with diagnostic_scope(new=True):
                observed.append(_record())
                entered.set()
                await waiting.wait()
        finally:
            observed.append(_record())

    with diagnostic_process("tui"), diagnostic_scope() as parent:
        task = asyncio.create_task(cancelled_attempt())
        await asyncio.wait_for(entered.wait(), timeout=5)
        sibling = _record()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        later = _record()

    assert observed[0].__dict__["_cadrumo_diagnostic_id"] != parent
    assert observed[1].__dict__["_cadrumo_diagnostic_id"] == parent
    assert sibling.__dict__["_cadrumo_diagnostic_id"] == parent
    assert later.__dict__["_cadrumo_diagnostic_id"] == parent


def test_nested_process_scope_restores_after_exception_and_deferred_records_keep_original_role() -> None:
    baseline = _record()
    worker: logging.LogRecord | None = None
    attempt: str | None = None
    with diagnostic_process("runtime"), diagnostic_scope() as parent:
        with (
            pytest.raises(RuntimeError, match="synthetic scope failure"),
            diagnostic_process("profile_worker"),
            diagnostic_scope(new=True) as attempt,
        ):
            worker = _record()
            raise RuntimeError("synthetic scope failure")
        resumed = _record()
    outside = _record()

    assert worker is not None and attempt is not None
    _, context = _context(worker)
    assert context["process_role"] == "profile_worker"
    assert context["diagnostic_id"] == attempt
    assert resumed.__dict__["_cadrumo_process_role"] == "runtime"
    assert resumed.__dict__["_cadrumo_diagnostic_id"] == parent
    assert outside.__dict__["_cadrumo_process_role"] == baseline.__dict__["_cadrumo_process_role"]
    assert outside.__dict__["_cadrumo_diagnostic_id"] == baseline.__dict__["_cadrumo_diagnostic_id"]


@pytest.mark.parametrize("message", ["synthetic result", "synthetic result\nsecond line"])
def test_ignored_scalar_overflow_does_not_expand_context_provenance_or_formatter_memory(message: str) -> None:
    record = _record()
    record.msg = message
    record.__dict__.update({f"synthetic_ignored_{index:06}": index for index in range(100_000)})
    record.__dict__["reason_code"] = "synthetic-reason-" * 500
    formatter = DiagnosticFormatter(LOG_FILE_FORMAT)
    formatter.format(record)
    owns_tracing = not tracemalloc.is_tracing()
    if owns_tracing:
        tracemalloc.start()
    baseline, _ = tracemalloc.get_traced_memory()
    tracemalloc.reset_peak()
    try:
        stamp_diagnostic_scalar_fields(record)
        line = formatter.format(record)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        if owns_tracing:
            tracemalloc.stop()

    assert peak - baseline < 64 * 1024
    assert len(record.__dict__["_cadrumo_scalar_fields"]) <= 32
    _, suffix = line.splitlines()[0].split(" | ", 1)
    context: object = json.loads(suffix)
    assert isinstance(context, dict)
    assert len(context) <= 32
    assert context["reason_code"] == ("synthetic-reason-" * 500)[:512]
    assert all(not key.startswith("synthetic_ignored_") for key in context)


def test_large_message_retains_content_and_uses_storage_proportional_to_its_output() -> None:
    record = _record()
    message = "first line\n" + "synthetic detail; " * 65_536
    record.msg = message
    record.__dict__.update({f"synthetic_ignored_{index:04}": index for index in range(1_000)})
    record.__dict__["reason_code"] = "synthetic-reason-" * 500
    stamp_diagnostic_scalar_fields(record)
    formatter = DiagnosticFormatter(LOG_FILE_FORMAT)
    formatter.format(record)
    owns_tracing = not tracemalloc.is_tracing()
    if owns_tracing:
        tracemalloc.start()
    baseline, _ = tracemalloc.get_traced_memory()
    tracemalloc.reset_peak()
    try:
        line = formatter.format(record)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        if owns_tracing:
            tracemalloc.stop()

    header, continuation = line.split("\n", 1)
    _, suffix = header.split(" | ", 1)
    context: object = json.loads(suffix)
    assert isinstance(context, dict)
    assert continuation == message.split("\n", 1)[1]
    assert context["reason_code"] == ("synthetic-reason-" * 500)[:512]
    assert record.msg == record.message == message
    assert peak - baseline < len(message.encode("utf-8")) * 3 + 64 * 1024


def test_multiple_handlers_format_same_multiline_record_without_mutating_message_or_arguments() -> None:
    record = _record()
    record.msg, record.args = "%s\nsecond line", ("first line",)
    record.stack_info = "Stack (most recent call last):\nsynthetic stack frame"
    streams = StringIO(), StringIO()
    logger = logging.Logger("synthetic.multiple_diagnostic_handlers")
    for stream in streams:
        handler = logging.StreamHandler(stream)
        handler.setFormatter(DiagnosticFormatter(LOG_FILE_FORMAT))
        logger.addHandler(handler)

    logger.handle(record)
    rendered = streams[0].getvalue()
    assert rendered == streams[1].getvalue()
    assert rendered.splitlines()[0].split(" | ", 1)[0].endswith(": first line")
    assert rendered.splitlines()[1:] == ["second line", "Stack (most recent call last):", "synthetic stack frame"]
    assert record.msg == "%s\nsecond line"
    assert record.args == ("first line",)
    assert record.message == "first line\nsecond line"
    assert DiagnosticFormatter(LOG_FILE_FORMAT).format(record) + "\n" == rendered


def test_failed_header_format_restores_message_for_a_later_handler() -> None:
    record = _record()
    record.msg, record.args = "%s\nsecond line", ("first line",)
    with pytest.raises(ValueError, match="missing"):
        DiagnosticFormatter(LOG_FILE_FORMAT + " %(missing)s").format(record)

    assert record.message == "first line\nsecond line"
    assert record.msg == "%s\nsecond line"
    assert record.args == ("first line",)
    rendered = DiagnosticFormatter(LOG_FILE_FORMAT).format(record)
    assert rendered.splitlines()[0].split(" | ", 1)[0].endswith(": first line")
    assert rendered.splitlines()[1:] == ["second line"]


@pytest.mark.parametrize("observed", (-1, True, 1 << 63, 0, (1 << 63) - 1))
def test_timing_observations_are_bounded_and_keep_only_scalar_diagnostic_context(
    caplog: pytest.LogCaptureFixture, observed: int
) -> None:
    logger = get_logger("cadrumo.tests.timing_bounds")
    with caplog.at_level(logging.DEBUG, logger=logger.name), diagnostic_scope(new=True) as identifier:
        diagnostic_timing_event(
            logger,
            "synthetic_timing",
            fields={
                "stage": "synthetic_phase",
                "phase_monotonic_ns": 123,
                "profile_id": _PRIVATE_INPUT_CANARY,
            },
            clock=lambda: observed,
        )
        assert flush_logging(timeout=5)
    records = [record for record in caplog.records if record.name == logger.name]
    if isinstance(observed, bool) or not 0 <= observed <= (1 << 63) - 1:
        assert records == []
        return
    assert len(records) == 1
    assert records[0].levelno == logging.DEBUG
    _, context = _context(records[0])
    assert context["phase_monotonic_ns"] == observed
    assert context["diagnostic_id"] == identifier
    assert "profile_id" not in context
    assert _PRIVATE_INPUT_CANARY not in records[0].__dict__["diagnostic_context"]
    assert len(context) <= 32


def test_event_fields_reach_the_written_line_only_as_scrubbed_allowed_scalars() -> None:
    # Isolated from the root handlers, which carry their own scrubbing filter:
    # this pins the project logger's filter, the layer that also covers records
    # written before any host configured logging.
    iban = "ES9121000418450200051332"
    logger = get_logger("cadrumo.tests.event_fields")
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(DiagnosticFormatter(LOG_FILE_FORMAT))
    logger.addHandler(handler)
    previous_level, previous_propagate = logger.level, logger.propagate
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    try:
        diagnostic_event(
            logger,
            "synthetic_dispatch_slow",
            fields={
                "budget_seconds": 1.5,
                "password": _PRIVATE_INPUT_CANARY,
                "reason": f"account {iban}",
                "outcome": "refused",
            },
            level=logging.WARNING,
        )
        assert flush_logging(timeout=5)
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous_level)
        logger.propagate = previous_propagate
    line = stream.getvalue()
    context: object = json.loads(line.split(" | ", 1)[1])
    assert isinstance(context, dict)

    assert context["budget_seconds"] == 1.5
    assert str(context["reason"]).startswith("account sha256:")
    assert "password" not in context
    assert _PRIVATE_INPUT_CANARY not in line
    assert iban not in line


def test_stall_lock_and_recovery_timing_fields_reach_the_log_file_and_unlisted_fields_do_not(tmp_path: Path) -> None:
    logger = get_logger("cadrumo.tests.stall_timing_fields")
    log_file = tmp_path / "diagnostic.log"
    handler = AnnouncingRotatingFileHandler(str(log_file), encoding="utf-8")
    handler.setFormatter(DiagnosticFormatter(LOG_FILE_FORMAT))
    logger.addHandler(handler)
    previous_level, previous_propagate = logger.level, logger.propagate
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    listed: dict[str, DiagnosticValue] = {
        "child_process_id": 4321,
        "definition_id": "ledger.rule.add",
        "dump_file": "profile-worker-stall-4321.txt",
        "hold_seconds": 1.25,
        "job_empty_seconds": 0.5,
        "members_signalled_seconds": 2.0,
        "wait_seconds": 0.75,
        # The custody recovery window a worker loss opens.
        "window_seconds": 120.0,
    }
    try:
        diagnostic_event(
            logger,
            "synthetic_stall_timing",
            fields={
                **listed,
                "dump_path": str(tmp_path / "profile-worker-stall-4321.txt"),
                "session_id": _PRIVATE_INPUT_CANARY,
            },
            level=logging.WARNING,
        )
        assert flush_logging(timeout=5)
    finally:
        logger.removeHandler(handler)
        handler.close()
        logger.setLevel(previous_level)
        logger.propagate = previous_propagate
    line = log_file.read_text(encoding="utf-8")
    context: object = json.loads(line.split(" | ", 1)[1])
    assert isinstance(context, dict)

    assert {name: context[name] for name in listed} == listed
    assert "dump_path" not in context and "session_id" not in context
    assert _PRIVATE_INPUT_CANARY not in line
    assert str(tmp_path) not in line


def test_a_slow_call_is_reported_once_with_its_fields_and_a_prompt_call_is_not(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = get_logger("cadrumo.tests.slow_call")
    with caplog.at_level(logging.DEBUG, logger=logger.name):
        with diagnostic_slow_call(logger, "synthetic_prompt_call", threshold_seconds=60.0):
            pass
        with diagnostic_slow_call(
            logger, "synthetic_slow_call", threshold_seconds=0.02, fields={"phase": "lookup", "definition_id": "x"}
        ):
            time.sleep(0.05)

    (record,) = delivered_records(caplog, logger.name)
    assert record.getMessage() == "synthetic_slow_call"
    assert record.levelno == logging.WARNING
    _, context = _context(record)
    assert context["phase"] == "lookup" and context["definition_id"] == "x"
    assert context["outcome"] == "completed"
    assert isinstance(context["elapsed_seconds"], float) and context["elapsed_seconds"] >= 0.02


def test_a_slow_call_that_raises_is_reported_and_its_exception_propagates_unchanged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = get_logger("cadrumo.tests.slow_call_raising")
    failure = ValueError("synthetic failure")
    with (
        caplog.at_level(logging.DEBUG, logger=logger.name),
        pytest.raises(ValueError, match="synthetic failure") as caught,
        diagnostic_slow_call(logger, "synthetic_slow_call", threshold_seconds=0.0),
    ):
        raise failure

    assert caught.value is failure
    (record,) = delivered_records(caplog, logger.name)
    assert record.levelno == logging.WARNING
    assert _context(record)[1]["outcome"] == "raised"


def test_a_prompt_call_is_recorded_at_the_level_asked_for_and_a_slow_one_still_warns(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = get_logger("cadrumo.tests.slow_call_prompt_level")
    with caplog.at_level(logging.DEBUG, logger=logger.name):
        with diagnostic_slow_call(
            logger, "synthetic_prompt_call", threshold_seconds=60.0, prompt_level=logging.DEBUG, fields={"phase": "a"}
        ):
            pass
        with diagnostic_slow_call(
            logger, "synthetic_slow_call", threshold_seconds=0.0, prompt_level=logging.DEBUG, fields={"phase": "b"}
        ):
            pass

    prompt, slow = delivered_records(caplog, logger.name)
    assert (prompt.levelno, slow.levelno) == (logging.DEBUG, logging.WARNING)
    for record, phase in ((prompt, "a"), (slow, "b")):
        _, context = _context(record)
        assert context["phase"] == phase and context["outcome"] == "completed"
        assert isinstance(context["elapsed_seconds"], float) and context["elapsed_seconds"] >= 0.0


def test_a_phase_is_recorded_with_its_name_its_seconds_and_what_the_block_counted(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = get_logger("cadrumo.tests.phase")
    with caplog.at_level(logging.DEBUG, logger=logger.name), diagnostic_scope(new=True) as identifier:
        with diagnostic_phase(logger, "synthetic_phase", "loading", fields={"definition_id": "x.y"}) as measured:
            measured["item_count"] = 3
            measured["taxpayer_name"] = _PRIVATE_INPUT_CANARY
        with diagnostic_phase(logger, "synthetic_phase", "waiting", slow_seconds=0.0):
            pass

    prompt, slow = delivered_records(caplog, logger.name)
    assert [record.getMessage() for record in (prompt, slow)] == ["synthetic_phase"] * 2
    assert (prompt.levelno, slow.levelno) == (logging.DEBUG, logging.WARNING)
    _, context = _context(prompt)
    assert context["phase"] == "loading" and context["definition_id"] == "x.y"
    assert context["item_count"] == 3 and context["outcome"] == "completed"
    assert context["diagnostic_id"] == identifier
    assert isinstance(context["elapsed_seconds"], float)
    assert "taxpayer_name" not in context
    assert _PRIVATE_INPUT_CANARY not in prompt.__dict__["diagnostic_context"]
    assert _context(slow)[1]["phase"] == "waiting"


def test_a_phase_that_raises_is_recorded_and_its_exception_propagates_unchanged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = get_logger("cadrumo.tests.phase_raising")
    failure = ValueError("synthetic failure")
    with (
        caplog.at_level(logging.DEBUG, logger=logger.name),
        pytest.raises(ValueError, match="synthetic failure") as caught,
        diagnostic_phase(logger, "synthetic_phase", "loading"),
    ):
        raise failure

    assert caught.value is failure
    (record,) = delivered_records(caplog, logger.name)
    assert _context(record)[1]["outcome"] == "raised"


@pytest.mark.parametrize("failure_site", ("clock", "log"))
def test_ordinary_timing_failure_never_changes_success_or_the_business_primary(
    monkeypatch: pytest.MonkeyPatch, failure_site: str
) -> None:
    logger = get_logger("cadrumo.tests.timing_failure")

    def failed_clock() -> int:
        raise OSError("synthetic diagnostic clock failure")

    def failed_log(*_args: object, **_kwargs: object) -> None:
        raise OSError("synthetic diagnostic sink failure")

    if failure_site == "log":
        monkeypatch.setattr(logger, "log", failed_log)
    clock = failed_clock if failure_site == "clock" else lambda: 1
    assert diagnostic_timing_event(logger, "synthetic_timing", clock=clock) is None
    primary = ValueError("synthetic business failure")
    with pytest.raises(ValueError) as caught:
        try:
            raise primary
        finally:
            diagnostic_timing_event(logger, "synthetic_timing", clock=clock, primary_error=sys.exception())
    assert caught.value is primary


@pytest.mark.parametrize("failure_site", ("clock", "log"))
def test_timing_interruptions_preserve_the_existing_primary_exception_contract(
    monkeypatch: pytest.MonkeyPatch, failure_site: str
) -> None:
    class TimingInterrupt(BaseException):
        pass

    logger = get_logger("cadrumo.tests.timing_interrupt")
    interruption = TimingInterrupt()

    def interrupted_clock() -> int:
        raise interruption

    def interrupted_log(*_args: object, **_kwargs: object) -> None:
        raise interruption

    if failure_site == "log":
        monkeypatch.setattr(logger, "log", interrupted_log)
    clock = interrupted_clock if failure_site == "clock" else lambda: 1
    with pytest.raises(TimingInterrupt) as interrupted:
        diagnostic_timing_event(logger, "synthetic_timing", clock=clock)
    assert interrupted.value is interruption
    primary = ValueError("synthetic business failure")
    with pytest.raises(ValueError) as caught:
        try:
            raise primary
        finally:
            diagnostic_timing_event(logger, "synthetic_timing", clock=clock, primary_error=sys.exception())
    assert caught.value is primary


@pytest.mark.asyncio
async def test_timed_task_scopes_cross_threads_and_restore_the_parent_after_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = get_logger("cadrumo.tests.timed_context")
    identifiers: list[str] = []

    async def observe(index: int, *, fail: bool) -> str:
        with diagnostic_scope(new=True) as identifier:
            identifiers.append(identifier)
            diagnostic_timing_event(logger, "synthetic_timing", clock=lambda: index)
            await asyncio.sleep(0)
            await asyncio.to_thread(diagnostic_timing_event, logger, "synthetic_timing", clock=lambda: index + 10)
            if fail:
                raise ValueError("synthetic task failure")
            return identifier

    with caplog.at_level(logging.DEBUG, logger=logger.name), diagnostic_scope(new=True) as parent:
        results = await asyncio.gather(observe(1, fail=False), observe(2, fail=True), return_exceptions=True)
        diagnostic_timing_event(logger, "synthetic_timing", clock=lambda: 100)
        assert flush_logging(timeout=5)
    records = [record for record in caplog.records if record.name == logger.name]
    assert len(set(identifiers)) == 2 and parent not in identifiers
    assert results[0] == identifiers[0] and isinstance(results[1], ValueError)
    contexts = [_context(record)[1] for record in records]
    for index, identifier in enumerate(identifiers, start=1):
        assert [context["phase_monotonic_ns"] for context in contexts if context["diagnostic_id"] == identifier] == [
            index,
            index + 10,
        ]
    assert contexts[-1]["diagnostic_id"] == parent
    assert contexts[-1]["phase_monotonic_ns"] == 100


@pytest.mark.parametrize("requested", [None, logging.DEBUG, logging.INFO, logging.WARNING])
def test_declared_worker_failure_cannot_be_logged_below_error(
    caplog: pytest.LogCaptureFixture, requested: int | None
) -> None:
    logger = get_logger("cadrumo.tests.worker_levels")
    with caplog.at_level(logging.DEBUG, logger=logger.name):
        diagnostic_event(logger, "worker_lifecycle", fields={"outcome": "failed"}, level=requested)
        assert flush_logging(timeout=5)
    assert caplog.records[-1].levelno == logging.ERROR


def test_technical_event_defaults_to_debug_and_operator_info_is_preserved(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = get_logger("cadrumo.tests.worker_levels")
    with caplog.at_level(logging.DEBUG, logger=logger.name):
        diagnostic_event(logger, "worker_attestation_started")
        diagnostic_event(logger, "service_ready", level=logging.INFO)
        assert flush_logging(timeout=5)
    assert [record.levelno for record in caplog.records] == [logging.DEBUG, logging.INFO]
