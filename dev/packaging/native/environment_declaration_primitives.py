"""Shared validation primitives for environment declarations."""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

DECLARATION = Path("native/application-environment.toml")


class ApplicationEnvironmentError(ValueError):
    """The declaration violates its schema; generation stops."""


def fail(message: str) -> ApplicationEnvironmentError:
    """Build the application environment error for a declaration problem."""
    return ApplicationEnvironmentError(f"{DECLARATION.as_posix()}: {message}")


def environment_declaration_primitives_table(value: object, where: str) -> dict[str, Any]:
    """Return the value if it is a table or refuse naming its location."""
    if not isinstance(value, dict):
        raise fail(f"{where} must be a table")
    return value


def strings(value: object, where: str, pattern: re.Pattern[str] | None = None) -> tuple[str, ...]:
    """Return a list of unique non-empty strings, optionally matching a pattern, or refuse."""
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise fail(f"{where} must be a list of non-empty strings")
    if pattern is not None:
        for item in value:
            if not pattern.fullmatch(item):
                raise fail(f"{where} has a malformed entry: {item!r}")
    items = tuple(str(item) for item in value)
    if len(set(items)) != len(items):
        raise fail(f"{where} repeats an entry")
    return items


def keys(
    table: Mapping[str, Any], where: str, required: set[str], optional: frozenset[str] | set[str] = frozenset()
) -> None:
    """Refuse a table whose keys are missing required ones or hold unknown ones."""
    missing, unknown = required - set(table), set(table) - required - optional
    if missing or unknown:
        raise fail(f"{where} must declare {sorted(required)}; missing {sorted(missing)}, unknown {sorted(unknown)}")


def environment_declaration_primitives_list(value: object, where: str) -> list[Any]:
    """Return ``value`` when it is a list, otherwise refuse naming ``where``."""
    if not isinstance(value, list):
        raise fail(f"{where} must be a list")
    return value


def relative(value: object, where: str) -> str:
    """Return a relative forward-slash path with no empty, current or parent parts."""
    if not isinstance(value, str) or not value or value.startswith("/") or "\\" in value:
        raise fail(f"{where} must be a relative path with forward slashes")
    if any(part in {"", ".", ".."} for part in value.split("/")):
        raise fail(f"{where} must not hold empty, current or parent components")
    return value


def integer(value: object, where: str, *, minimum: int = 1) -> int:
    """Return the value if it is an integer at or above a minimum, else refuse."""
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise fail(f"{where} must be an integer of at least {minimum}")
    return value
