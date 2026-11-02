"""Validate and project the single declaration of native operational settings."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any

from .environment_declaration_primitives import _fail, _keys, _table


def parse_settings(raw: object) -> dict[str, dict[str, Any]]:
    """Reject malformed settings before generating any consumer projection."""
    settings: dict[str, dict[str, Any]] = {}
    for name, value in _table(raw, "settings").items():
        where = f"settings.{name}"
        if not re.fullmatch(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*", name):
            raise _fail(f"{where} must have a lower_snake_case name")
        entry = _table(value, where)
        _keys(entry, where, {"default", "minimum", "maximum", "unit", "description"})
        for field in ("default", "minimum", "maximum"):
            number = entry[field]
            if type(number) is not int or not 0 <= number <= 2**31 - 1:
                raise _fail(f"{where}.{field} must be a nonnegative signed 32-bit integer")
        if not entry["minimum"] <= entry["default"] <= entry["maximum"]:
            raise _fail(f"{where} must satisfy minimum <= default <= maximum")
        if entry["unit"] not in ("milliseconds", "count", "bytes"):
            raise _fail(f"{where}.unit is unsupported")
        if not isinstance(entry["description"], str) or not entry["description"].strip():
            raise _fail(f"{where}.description must be nonempty")
        settings[name] = dict(entry)
    return settings


def defaults(settings: Mapping[str, Mapping[str, Any]]) -> dict[str, int]:
    """Project validated defaults without reproducing declaration literals."""
    return {name: entry["default"] for name, entry in settings.items()}


def rust_settings(settings: Mapping[str, Mapping[str, Any]]) -> list[str]:
    """Emit typed Rust constants from the same defaults as the JSON projection."""
    return [f"pub const SETTING_{name.upper()}: u64 = {value};" for name, value in defaults(settings).items()]


def typescript_settings(settings: Mapping[str, Mapping[str, Any]]) -> str:
    """Emit a typed frontend projection without publisher provisioning."""
    return (
        "// Generated from native/application-environment.toml.\n"
        + "export default "
        + json.dumps(defaults(settings), indent=2)
        + " as const;\n"
    )
