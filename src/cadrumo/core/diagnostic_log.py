"""Bounded process diagnostics kept separate from operation audit and replay."""

from __future__ import annotations

import json
import logging
import math
import os
import time
from collections.abc import Callable, Generator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Literal, cast, override
from uuid import uuid4

from .errors.failure_report import failure_chain

type DiagnosticValue = str | int | float | bool | None
type DiagnosticProcessRole = Literal[
    "python", "tui", "runtime", "profile_worker", "extension_service", "external_client"
]

_DIAGNOSTIC_ID: ContextVar[str | None] = ContextVar("cadrumo_diagnostic_id", default=None)
_process_role: DiagnosticProcessRole = "python"
_MAX_CONTEXT_FIELDS = 32
_MAX_CONTEXT_TEXT = 512
_LIFECYCLE_FIELDS = tuple(
    sorted(
        {
            "action",
            "call_name",
            "handler_name",
            "held_call_name",
            "held_elapsed_seconds",
            "request_type",
            "operation_channel",
            "budget_seconds",
            "request_action",
            "kdf_cleanup_process_elapsed_ms",
            "kdf_cleanup_pipes_elapsed_ms",
            "kdf_cleanup_directory_elapsed_ms",
            "queue_seconds",
            "phase",
            "event",
            "service",
            "gateway_port",
            "worker_port",
            "port",
            "duration_ms",
            "elapsed_ms",
            "reason",
            "status",
            "trace_id",
            "span_id",
            "external_sequence",
            "diagnostic_rejected_count",
            "cleanup_incomplete",
            "cleanup_error_type",
            "cleanup_status",
            "drain_timeout_seconds",
            "elapsed_seconds",
            "error_chain",
            "error_code",
            "error_origin",
            "error_type",
            "failure_boundary",
            "invariant",
            "exit_code",
            "handoff_transferred",
            "headless",
            "inventory_complete",
            "inventory_elapsed_ms",
            "inventory_login_count",
            "inventory_state",
            "kdf_operation",
            "kdf_clean_exit_elapsed_ms",
            "kdf_cleanup_elapsed_ms",
            "kdf_ready_attestation_elapsed_ms",
            "kdf_ready_wait_elapsed_ms",
            "kdf_request_write_elapsed_ms",
            "kdf_result_wait_elapsed_ms",
            "kdf_start_elapsed_ms",
            "login_method",
            "observation_elapsed_ms",
            "observed_active_count",
            "observed_eligible_count",
            "observed_unknown_count",
            "outcome",
            "parent_process_id",
            "persist_receipt_requested",
            "phase_monotonic_ns",
            "profile_count",
            "profile_persisted",
            "reason_code",
            "refusal_check",
            "retained_peer_witness_count",
            "retirement_kind",
            "root_cause",
            "run_id",
            "runtime_admitted",
            "runtime_boot_id",
            "runtime_version",
            "session_kinds",
            "stage",
            "startup_phase",
            "step_id",
            "timeout_seconds",
            "transition",
        }
    )
)


@contextmanager
def diagnostic_process(role: DiagnosticProcessRole) -> Generator[None]:
    """Attribute records from every thread to this process's active entrypoint."""
    global _process_role
    previous = _process_role
    _process_role = role
    try:
        yield
    finally:
        _process_role = previous


@contextmanager
def diagnostic_scope(*, new: bool = False) -> Generator[str]:
    """Correlate nested diagnostics without creating an audit or replay run."""
    identifier = None if new else _DIAGNOSTIC_ID.get()
    identifier = identifier or uuid4().hex
    token = _DIAGNOSTIC_ID.set(identifier)
    try:
        yield identifier
    finally:
        _DIAGNOSTIC_ID.reset(token)


def stamp_diagnostic_record(record: logging.LogRecord) -> None:
    """Capture context when a record is made, including deferred records."""
    import asyncio

    record.__dict__["_cadrumo_process_role"] = _process_role
    record.__dict__["_cadrumo_diagnostic_id"] = _DIAGNOSTIC_ID.get()
    try:
        task = asyncio.current_task()
    except RuntimeError:
        task = None
    record.__dict__["_cadrumo_task_id"] = id(task) if task is not None else None
    record.__dict__["_cadrumo_task_name"] = task.get_name() if task is not None else None


def stamp_diagnostic_scalar_fields(record: logging.LogRecord) -> None:
    """Remember scalar extras before scrubbing can render an opaque argument."""
    if "_cadrumo_scalar_fields" in record.__dict__:
        return
    record.__dict__["_cadrumo_scalar_fields"] = tuple(
        key
        for key in _LIFECYCLE_FIELDS
        if key in record.__dict__
        and (isinstance(record.__dict__[key], str | int | float | bool) or record.__dict__[key] is None)
    )


def diagnostic_event(
    logger: logging.Logger,
    event: str,
    *,
    fields: Mapping[str, DiagnosticValue] | None = None,
    level: int | None = None,
    primary_error: BaseException | None = None,
) -> None:
    """Emit safe scalar diagnostics without displacing an existing primary."""
    try:
        outcome = fields.get("outcome") if fields is not None else None
        failed = isinstance(outcome, str) and outcome in {"failed", "error", "unconfirmed"}
        failed = failed or event.endswith(("_failed", " failed"))
        if failed and (level is None or level < logging.ERROR):
            level = logging.ERROR
        elif level is None:
            level = logging.DEBUG
        logger.log(level, event, extra=dict(fields or {}))
    except Exception:
        return
    except BaseException:
        if primary_error is None:
            raise


def diagnostic_timing_event(
    logger: logging.Logger,
    event: str,
    *,
    fields: Mapping[str, DiagnosticValue] | None = None,
    clock: Callable[[], int] | None = None,
    primary_error: BaseException | None = None,
) -> None:
    """Stamp one bounded monotonic observation without changing a business clock.

    Ordinary clock and sink failures omit the observation. Nonordinary
    interruptions retain the existing diagnostic-event behavior: they propagate
    on success, but never replace an exception already unwinding.
    """
    try:
        observed = clock() if clock is not None else time.monotonic_ns()
        if type(observed) is not int or not 0 <= observed <= (1 << 63) - 1:
            return
        diagnostic_event(
            logger,
            event,
            fields={**(fields or {}), "phase_monotonic_ns": observed},
            level=logging.DEBUG,
            primary_error=primary_error,
        )
    except Exception:
        return
    except BaseException:
        if primary_error is None:
            raise


def diagnostic_error_fields(error: BaseException) -> dict[str, DiagnosticValue]:
    """Name an error, its originating frame and its identifier-only cause chain, never its message or locals."""
    fields: dict[str, DiagnosticValue] = {"error_type": type(error).__name__}
    trace = error.__traceback__
    if trace is not None:
        while trace.tb_next is not None:
            trace = trace.tb_next
        code = trace.tb_frame.f_code
        fields["error_origin"] = f"{code.co_filename}:{trace.tb_lineno}:{code.co_name}"
    links = failure_chain(error)
    reason = next((link.reason for link in links if link.reason is not None), None)
    if reason is not None:
        fields["reason"] = reason
    if len(links) > 1:
        # A wrapper names the symptom; the operator needs the refusal or failure it wraps.
        fields["error_chain"] = " <- ".join(link.render() for link in links)
        fields["root_cause"] = links[-1].render()
    return fields


def _scalar(value: object) -> DiagnosticValue:
    if isinstance(value, str):
        return value[:_MAX_CONTEXT_TEXT]
    if isinstance(value, bool | int) or value is None:
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    return None


class DiagnosticFormatter(logging.Formatter):
    """Format scrubbed records with UTC time and a bounded JSON scalar suffix."""

    @override
    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        # Keep the logging override's keyword contract; diagnostics always use UTC ISO time.
        del datefmt
        return datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")

    @override
    def format(self, record: logging.LogRecord) -> str:
        context: dict[str, DiagnosticValue] = {
            "process_id": record.process or os.getpid(),
            "process_role": _scalar(record.__dict__.get("_cadrumo_process_role", _process_role)),
        }
        # Foreign-process records are forwarded by a reader thread; its identity
        # is not the emitting child's worker identity.
        if record.process == os.getpid():
            context["thread_id"] = record.thread
            context["thread_name"] = _scalar(record.threadName)
            for key in ("task_id", "task_name"):
                value = record.__dict__.get(f"_cadrumo_{key}")
                if value is not None:
                    context[key] = _scalar(value)
        identifier = record.__dict__.get("_cadrumo_diagnostic_id")
        if isinstance(identifier, str) and identifier:
            context["diagnostic_id"] = _scalar(identifier)
        scalar_fields = cast("tuple[str, ...] | None", record.__dict__.get("_cadrumo_scalar_fields"))
        for key in _LIFECYCLE_FIELDS:
            if key not in record.__dict__:
                continue
            value = record.__dict__[key]
            if (key in {"run_id", "step_id"} and not value) or (scalar_fields is not None and key not in scalar_fields):
                continue
            if not isinstance(value, str | int | float | bool) and value is not None:
                continue
            if len(context) >= _MAX_CONTEXT_FIELDS:
                break
            context[key[:_MAX_CONTEXT_TEXT]] = _scalar(value)
        record.__dict__["diagnostic_context"] = json.dumps(
            context, ensure_ascii=True, sort_keys=True, separators=(",", ":")
        )
        return super().format(record)

    @override
    def formatMessage(self, record: logging.LogRecord) -> str:
        message = record.message
        first_line, separator, continuation = message.partition("\n")
        if not separator:
            return super().formatMessage(record)
        record.message = first_line
        try:
            header = super().formatMessage(record)
        finally:
            record.message = message
        return header + "\n" + continuation
