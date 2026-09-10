"""Canonical TOML read, freeze and render helpers.

Multiple committed-TOML loaders (registry definitions, the user-profile
schema) need the same two operations: parse a TOML file with errors
re-raised as a domain-specific exception, and recursively freeze the
parsed mapping so list values become tuples. These helpers are the
single source of that behaviour. :func:`render_toml` is the inverse used to
present a parsed document back to a reader: its output parses to a value
equal to the one it was given.

:func:`read_toml` and :func:`freeze_toml` are used by the registry
loader in :mod:`domain.calculations.registry._loader` and the
user-profile schema loader in :mod:`domain.user_profile.loader`.
:func:`to_str_keyed_dict` is the narrow bridge from loosely typed
parsed TOML mappings into strict schema models that require string keys.

The parse is backed by the Python standard-library :mod:`tomllib` module,
available throughout Cadrumo's supported Python range. It returns the native
Python types defined by TOML for every value shape
(str/int/float/bool/list/dict/date/datetime/time); it does not produce a
:class:`decimal.Decimal` (TOML has no native decimal type), so registry money
and rate values continue to arrive as plain TOML strings, coerced to
``Decimal`` downstream by pydantic field validators exactly as before.
"""

from __future__ import annotations

import math
import re
import tomllib
from collections.abc import Callable, Mapping, Sequence
from datetime import date, datetime, time
from pathlib import Path

from .type_guards import is_object_dict, is_object_list

#: A table's position in a rendered document: its keys, with the index of the
#: element for each array of tables it sits in.
type TomlTablePath = tuple[str | int, ...]

_BARE_KEY = re.compile(r"^[A-Za-z0-9_-]+$")
_STRING_ESCAPES = {'"': '\\"', "\\": "\\\\", "\b": "\\b", "\t": "\\t", "\n": "\\n", "\f": "\\f", "\r": "\\r"}


def read_toml(path: Path, *, error_factory: Callable[[str], Exception]) -> dict[str, object]:
    """Parse a TOML file, re-raising failures via ``error_factory``.

    Args:
        path: Path of the TOML file to read.
        error_factory: Callable that builds the domain-specific
            exception from a message. Invoked on decode and OS errors
            so each loader keeps its own error type.

    Returns:
        The parsed top-level TOML mapping.

    Raises:
        Exception: The exception built by ``error_factory`` when the file
            cannot be read (``OSError``) or contains invalid TOML
            (``tomllib.TOMLDecodeError``).
    """
    try:
        with path.open("rb") as handle:
            loaded = tomllib.load(handle)
        if not isinstance(loaded, Mapping):
            raise error_factory(f"{path}: TOML root must be a mapping")
        return to_str_keyed_dict(loaded, error_factory=error_factory)
    except tomllib.TOMLDecodeError as exc:
        raise error_factory(f"{path}: invalid TOML: {exc}") from exc
    except UnicodeDecodeError as exc:
        raise error_factory(f"{path}: invalid TOML: {exc}") from exc
    except OSError as exc:
        raise error_factory(f"{path}: cannot read TOML: {exc}") from exc


def to_str_keyed_dict[KeyT](
    raw: Mapping[KeyT, object], *, error_factory: Callable[[str], Exception]
) -> dict[str, object]:
    """Convert a parsed TOML mapping to a str-keyed dict, rejecting non-string keys.

    Args:
        raw: Parsed mapping whose keys may not all be strings.
        error_factory: Builds the domain-specific exception raised when a
            key is not a ``str``, so each loader keeps its own error type.

    Returns:
        A new dict with the same items and string keys.

    Raises:
        Exception: The exception built by ``error_factory`` when any key is
            not a ``str``.
    """
    result: dict[str, object] = {}
    for key, value in raw.items():
        if not isinstance(key, str):
            raise error_factory("TOML table keys must be strings")
        result[key] = value
    return result


def freeze_toml_value(value: object) -> object:
    """Recursively freeze one parsed TOML value, turning lists into tuples.

    The TOML parser returns mutable Python lists for TOML arrays. Registry and
    profile-schema models use strict frozen contracts, so loader boundaries call
    this helper before validating nested payloads. Mappings stay mappings with
    their values frozen recursively; scalar TOML values are returned unchanged.
    """
    if is_object_list(value):
        return tuple(freeze_toml_value(item) for item in value)
    if is_object_dict(value):
        return {key: freeze_toml_value(item) for key, item in value.items()}
    return value


def freeze_toml(data: dict[str, object]) -> dict[str, object]:
    """Recursively freeze a parsed TOML mapping (lists become tuples).

    This is the mapping-level companion to :func:`freeze_toml_value`, used after
    :func:`read_toml` when a committed TOML document is about to be validated as
    a frozen registry, category, IVA, or user-profile schema object.
    """
    return {key: freeze_toml_value(value) for key, value in data.items()}


def render_toml(document: Mapping[str, object], *, comments: Mapping[TomlTablePath, str] | None = None) -> str:
    """Render a parsed TOML document as TOML text that parses back to an equal value.

    Nested tables become ``[a.b]`` headers and a non-empty array whose every
    element is a table becomes ``[[a.b]]`` blocks, so a registry table renders
    in the shape its source files take; every other value is written inline.
    Within a table, plain values precede its sub-tables because TOML binds a
    key to the most recent header. Sequences may be lists or the tuples
    :func:`freeze_toml` produces.

    Args:
        document: The value to render, as :mod:`tomllib` would return it.
        comments: Comment text written above the table at each path; the empty
            path is the document itself. Each line of the text becomes one
            ``#`` comment line, so a parser drops it.

    Raises:
        TypeError: When a key is not a string or a value has no TOML form.
    """
    lines: list[str] = []
    _render_table(document, (), (), comments or {}, lines, header=False)
    return "\n".join(lines).strip("\n") + "\n"


def _render_table(
    table: Mapping[str, object],
    keys: tuple[str, ...],
    path: TomlTablePath,
    comments: Mapping[TomlTablePath, str],
    lines: list[str],
    *,
    header: bool,
    array_element: bool = False,
) -> None:
    plain: list[tuple[str, object]] = []
    nested: list[tuple[str, object]] = []
    for raw_key, value in table.items():
        key = _table_key(raw_key)
        (nested if isinstance(value, Mapping) or _is_table_array(value) else plain).append((key, value))
    comment = comments.get(path)
    if comment is not None:
        if lines and lines[-1]:
            lines.append("")
        lines.extend(f"# {line}".rstrip() for line in comment.splitlines())
    # A table holding only sub-tables is created implicitly by their headers,
    # which is how the source files declare it.
    if header and (array_element or plain or not nested or comment is not None):
        if lines and lines[-1] and not lines[-1].startswith("#"):
            lines.append("")
        dotted = ".".join(_render_key(key) for key in keys)
        lines.append(f"[[{dotted}]]" if array_element else f"[{dotted}]")
    lines.extend(f"{_render_key(key)} = {_render_inline(value)}" for key, value in plain)
    for key, value in nested:
        if isinstance(value, Mapping):
            _render_table(value, (*keys, key), (*path, key), comments, lines, header=True)
            continue
        for index, element in enumerate(_as_sequence(value)):
            if isinstance(element, Mapping):
                _render_table(
                    element, (*keys, key), (*path, key, index), comments, lines, header=True, array_element=True
                )


def _is_table_array(value: object) -> bool:
    elements = _as_sequence(value)
    return bool(elements) and all(isinstance(element, Mapping) for element in elements)


def _as_sequence(value: object) -> Sequence[object]:
    return value if isinstance(value, list | tuple) else ()


def _table_key(key: object) -> str:
    if not isinstance(key, str):
        raise TypeError(f"TOML table keys must be strings, got {key!r}")
    return key


def _render_key(key: str) -> str:
    return key if _BARE_KEY.fullmatch(key) else _render_string(key)


def _render_string(value: str) -> str:
    escaped = "".join(
        _STRING_ESCAPES.get(character)
        or (f"\\u{ord(character):04x}" if ord(character) < 0x20 or ord(character) == 0x7F else character)
        for character in value
    )
    return f'"{escaped}"'


def _render_inline(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if math.isnan(value):
            return "nan"
        if math.isinf(value):
            return "inf" if value > 0 else "-inf"
        return repr(value)
    if isinstance(value, str):
        return _render_string(value)
    if isinstance(value, datetime | date | time):
        return value.isoformat()
    if isinstance(value, Mapping):
        items = ", ".join(f"{_render_key(_table_key(key))} = {_render_inline(item)}" for key, item in value.items())
        return f"{{ {items} }}" if items else "{}"
    if isinstance(value, list | tuple):
        return "[" + ", ".join(_render_inline(item) for item in value) + "]"
    raise TypeError(f"value of type {type(value).__name__} has no TOML form")
