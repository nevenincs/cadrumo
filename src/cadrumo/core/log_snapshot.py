"""Bounded snapshots of diagnostic records before asynchronous delivery."""

from __future__ import annotations

import logging
import re
from enum import Enum
from itertools import islice
from typing import cast

from .log_scrubbing import FORMAT_SIZE_RE

_MAX_NESTING = 6
_MAX_CAUSE_CHAIN = 8
_MAX_FORMAT_SIZE_DIGITS = 5


def snapshot_value(value: object, *, depth: int = 0, budget: list[int] | None = None) -> object:
    """Copy bounded builtin shapes without invoking application rendering hooks."""
    if budget is None:
        budget = [256, 65536]
    budget[0] -= 1
    if depth >= _MAX_NESTING or budget[0] < 0:
        return "<omitted:nesting>"
    if type(value) in (str, int, float, bool, bytes, bytearray) or value is None:
        return _snapshot_scalar(value, budget)
    return _snapshot_container(value, depth, budget)


def _snapshot_container(value: object, depth: int, budget: list[int]) -> object:
    if type(value) is dict:
        mapping = cast(dict[object, object], value)
        return {
            cast(str, snapshot_value(key, depth=depth + 1, budget=budget)): snapshot_value(
                item, depth=depth + 1, budget=budget
            )
            for key, item in islice(mapping.items(), 64)
            if type(key) is str and len(key) <= 256
        }
    if type(value) in (tuple, list):
        sequence = cast(tuple[object, ...] | list[object], value)
        return tuple(snapshot_value(item, depth=depth + 1, budget=budget) for item in sequence[:64])
    if issubclass(type(value), Enum):
        members = cast(dict[object, object], Enum.__dict__["__dict__"].__get__(value))
        return snapshot_value(dict[object, object].get(members, "_value_"), depth=depth + 1, budget=budget)
    # Opaque arguments may hide documents or execute arbitrary __str__/__repr__.
    return "<omitted:opaque-value>"


def _snapshot_scalar(value: object, budget: list[int]) -> object:
    if type(value) is str:
        if len(value) > 16384 or len(value) * 4 > budget[1]:
            return "<omitted:oversized-text>"
        budget[1] -= len(value) * 4
        return value
    if type(value) is int:
        integer = value
        return integer if integer.bit_length() <= 4096 else "<omitted:oversized-number>"
    if type(value) in (float, bool) or value is None:
        return value
    if type(value) in (bytes, bytearray):
        binary = cast(bytes | bytearray, value)
        return bytes(binary) if len(binary) <= 256 else "<redacted:payload>"
    return value


def snapshot_record(record: logging.LogRecord) -> logging.LogRecord:
    """Copy a record without retaining arbitrary application objects."""
    snapshot = logging.LogRecord.__new__(logging.LogRecord)
    budget = [256, 65536]
    snapshot.__dict__ = {
        key: None if key == "exc_info" else snapshot_value(value, budget=budget)
        for key, value in islice(record.__dict__.items(), 128)
        if type(key) is str and len(key) <= 256
    }
    if isinstance(record.exc_info, tuple) and isinstance(record.exc_info[1], BaseException):
        snapshot.__dict__["_cadrumo_exception_snapshot"] = _snapshot_exception(record.exc_info[1], budget)
    snapshot.__dict__["_cadrumo_snapshot_weight"] = 1024 + 65536 - budget[1] + (256 - budget[0]) * 32
    return snapshot


def _snapshot_exception(error: BaseException, budget: list[int]) -> tuple[object, ...]:
    """Keep bounded causal frames and builtin arguments without retaining live frames."""
    chain: list[object] = []
    seen: set[int] = set()
    while id(error) not in seen and len(chain) < _MAX_CAUSE_CHAIN:
        seen.add(id(error))
        name = snapshot_value(type.__dict__["__name__"].__get__(type(error)), budget=budget)
        arguments = snapshot_value(BaseException.__dict__["args"].__get__(error), budget=budget)
        frames: list[tuple[str, int, str]] = []
        traceback = BaseException.__dict__["__traceback__"].__get__(error)
        while traceback is not None and len(frames) < 32:
            code = traceback.tb_frame.f_code
            frames.append(
                (
                    str(snapshot_value(code.co_filename, budget=budget)),
                    traceback.tb_lineno,
                    str(snapshot_value(code.co_name, budget=budget)),
                )
            )
            traceback = traceback.tb_next
        cause = BaseException.__dict__["__cause__"].__get__(error)
        context = BaseException.__dict__["__context__"].__get__(error)
        suppressed = BaseException.__dict__["__suppress_context__"].__get__(error)
        following = cause if cause is not None else None if suppressed else context
        chain.append((name, arguments, tuple(frames), "cause" if cause is not None else "context"))
        if not isinstance(following, BaseException):
            break
        error = following
    return tuple(chain)


def bound_format(record: logging.LogRecord) -> None:
    """Reject allocation-sized printf requests before any formatter evaluates them."""
    if not bool(record.args) or not isinstance(record.msg, str):
        return
    for index, match in enumerate(FORMAT_SIZE_RE.finditer(record.msg)):
        oversized = _oversized_format(match, record.args)
        if index >= 64 or oversized:
            record.msg, record.args = "<omitted:oversized-format>", None
            return


def _oversized_format(match: re.Match[str], args: object) -> bool:
    sizes = (match.group("width"), match.group("precision"))
    if any(size and size != "*" and (len(size) > _MAX_FORMAT_SIZE_DIGITS or int(size) > 16384) for size in sizes):
        return True
    return (
        "*" in sizes
        and isinstance(args, tuple)
        and any(type(arg) is int and abs(arg) > 16384 for arg in cast(tuple[object, ...], args))
    )
