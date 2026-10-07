"""Bounded process diagnostics kept separate from operation audit and replay."""

from __future__ import annotations

import json
import logging
import math
import os
from collections.abc import Generator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Literal, cast, override
from uuid import uuid4

type DiagnosticValue = str | int | float | bool | None
type DiagnosticProcessRole = Literal["python", "tui", "runtime", "profile_worker"]

_DIAGNOSTIC_ID: ContextVar[str | None] = ContextVar("cadrumo_diagnostic_id", default=None)
_process_role: DiagnosticProcessRole = "python"
_MAX_CONTEXT_FIELDS = 32
_MAX_CONTEXT_TEXT = 512
_LIFECYCLE_FIELDS = tuple(
    sorted(
        {
            "cleanup_incomplete",
            "drain_timeout_seconds",
            "elapsed_seconds",
            "error_origin",
            "error_type",
            "exit_code",
            "handoff_transferred",
            "headless",
            "inventory_state",
            "login_method",
            "outcome",
            "parent_process_id",
            "persist_receipt_requested",
            "profile_count",
            "profile_persisted",
            "reason_code",
            "run_id",
            "runtime_admitted",
            "runtime_boot_id",
            "runtime_version",
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
    record.__dict__["_cadrumo_process_role"] = _process_role
    record.__dict__["_cadrumo_diagnostic_id"] = _DIAGNOSTIC_ID.get()


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
    level: int = logging.INFO,
    primary_error: BaseException | None = None,
) -> None:
    """Emit safe scalar diagnostics without displacing an existing primary."""
    try:
        logger.log(level, event, extra=dict(fields or {}))
    except Exception:
        return
    except BaseException:
        if primary_error is None:
            raise


def diagnostic_error_fields(error: BaseException) -> dict[str, DiagnosticValue]:
    """Name an error and its originating frame without its message or locals."""
    fields: dict[str, DiagnosticValue] = {"error_type": type(error).__name__}
    trace = error.__traceback__
    if trace is not None:
        while trace.tb_next is not None:
            trace = trace.tb_next
        code = trace.tb_frame.f_code
        fields["error_origin"] = f"{code.co_filename}:{trace.tb_lineno}:{code.co_name}"
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
        return datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")

    @override
    def format(self, record: logging.LogRecord) -> str:
        context: dict[str, DiagnosticValue] = {
            "process_id": record.process or os.getpid(),
            "process_role": _scalar(record.__dict__.get("_cadrumo_process_role", _process_role)),
        }
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
