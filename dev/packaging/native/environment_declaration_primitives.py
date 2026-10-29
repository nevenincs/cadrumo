"""Shared validation primitives for environment declarations."""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

DECLARATION = Path("native/application-environment.toml")


class ApplicationEnvironmentError(ValueError):
    """The declaration violates its schema; generation stops."""


def _fail(message: str) -> ApplicationEnvironmentError:
    return ApplicationEnvironmentError(f"{DECLARATION.as_posix()}: {message}")


def _table(value: object, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _fail(f"{where} must be a table")
    return value


def _strings(value: object, where: str, pattern: re.Pattern[str] | None = None) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise _fail(f"{where} must be a list of non-empty strings")
    if pattern is not None:
        for item in value:
            if not pattern.fullmatch(item):
                raise _fail(f"{where} has a malformed entry: {item!r}")
    items = tuple(str(item) for item in value)
    if len(set(items)) != len(items):
        raise _fail(f"{where} repeats an entry")
    return items


def _keys(
    table: Mapping[str, Any], where: str, required: set[str], optional: frozenset[str] | set[str] = frozenset()
) -> None:
    missing, unknown = required - set(table), set(table) - required - optional
    if missing or unknown:
        raise _fail(f"{where} must declare {sorted(required)}; missing {sorted(missing)}, unknown {sorted(unknown)}")


def _list(value: object, where: str) -> list[Any]:
    if not isinstance(value, list):
        raise _fail(f"{where} must be a list")
    return value


def _relative(value: object, where: str) -> str:
    if not isinstance(value, str) or not value or value.startswith("/") or "\\" in value:
        raise _fail(f"{where} must be a relative path with forward slashes")
    if any(part in {"", ".", ".."} for part in value.split("/")):
        raise _fail(f"{where} must not hold empty, current or parent components")
    return value


def _integer(value: object, where: str, *, minimum: int = 1) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise _fail(f"{where} must be an integer of at least {minimum}")
    return value
