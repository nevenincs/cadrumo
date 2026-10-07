"""Diagnostic metadata preserves UTC, context ownership and private-data bounds."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import tracemalloc
from io import StringIO
from threading import Barrier
from typing import cast, override

import pytest

from ..diagnostic_log import (
    DiagnosticFormatter,
    diagnostic_process,
    diagnostic_scope,
    stamp_diagnostic_record,
    stamp_diagnostic_scalar_fields,
)
from ..logging import LOG_FILE_FORMAT, SecretScrubbingFilter, get_logger

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

    assert context == {"process_id": os.getpid(), "process_role": "python", **fields}
    assert "canary" not in record.__dict__["diagnostic_context"]

    record.__dict__["observed_unknown_count"] = {"private": "synthetic-private-canary"}
    record.__dict__["inventory_elapsed_ms"] = object()
    _, context = _context(record)
    assert "observed_unknown_count" not in context and "inventory_elapsed_ms" not in context


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
