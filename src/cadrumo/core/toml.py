"""Canonical TOML read + freeze helpers shared across loaders.

Multiple committed-TOML loaders (registry definitions, the user-profile
schema) need the same two operations: parse a TOML file with errors
re-raised as a domain-specific exception, and recursively freeze the
parsed mapping so list values become tuples. These helpers are the
single source of that behaviour.

:func:`read_toml` and :func:`freeze_toml` are used by the registry
loader in :mod:`domain.calculations.registry._loader` and the
user-profile schema loader in :mod:`domain.user_profile.loader`.
:func:`parse_toml_text` gives the same decode-error wrapping to callers that
already hold a TOML payload in memory, such as the secure bucket manifest
reader. :func:`to_str_keyed_dict` is the narrow bridge from loosely typed
parsed TOML mappings into strict schema models that require string keys.

The parse itself is backed by :mod:`rtoml` (a Rust-extension TOML parser),
not stdlib :mod:`tomllib`: ~2.4x faster on the registry's ~16k-fragment tree,
with output proven
byte-identical to :mod:`tomllib` across every fragment the registry ships.
Both parsers return the same native Python types for every TOML value shape
(str/int/float/bool/list/dict/date/datetime/time); neither ever produces a
:class:`decimal.Decimal` (TOML has no native decimal type), so registry money
and rate values continue to arrive as plain TOML strings, coerced to
``Decimal`` downstream by pydantic field validators exactly as before.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path

import rtoml


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
            (``rtoml.TomlParsingError``).
    """
    try:
        loaded = rtoml.load(path)
        if not isinstance(loaded, Mapping):
            raise error_factory(f"{path}: TOML root must be a mapping")
        raw: dict[object, object] = {}
        for key, value in loaded.items():
            raw[key] = value
        return to_str_keyed_dict(raw, error_factory=error_factory)
    except rtoml.TomlParsingError as exc:
        raise error_factory(f"{path}: invalid TOML: {exc}") from exc
    except OSError as exc:
        raise error_factory(f"{path}: cannot read TOML: {exc}") from exc


def parse_toml_text(text: str, *, error_factory: Callable[[str], Exception]) -> dict[str, object]:
    """Parse an in-memory TOML string, re-raising decode failures via ``error_factory``.

    The text-input sibling to :func:`read_toml` for callers that have
    already loaded the bytes (e.g. through
    :meth:`pathlib.Path.read_text`, secure-object payload decoding, or
    in-memory test fixtures) and need consistent error wrapping
    without the file-open layer.

    Args:
        text: TOML payload to decode.
        error_factory: Callable that builds the domain-specific
            exception from a message; invoked on
            ``rtoml.TomlParsingError``.

    Returns:
        The parsed top-level TOML mapping.

    Raises:
        Exception: The exception built by ``error_factory`` when the
            payload is not valid TOML.
    """
    try:
        return dict(rtoml.loads(text))
    except rtoml.TomlParsingError as exc:
        raise error_factory(f"invalid TOML: {exc}") from exc


def to_str_keyed_dict(raw: Mapping[object, object], *, error_factory: Callable[[str], Exception]) -> dict[str, object]:
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
    if isinstance(value, list):
        return tuple(freeze_toml_value(item) for item in value)
    if isinstance(value, dict):
        return {key: freeze_toml_value(item) for key, item in value.items()}
    return value


def freeze_toml(data: dict[str, object]) -> dict[str, object]:
    """Recursively freeze a parsed TOML mapping (lists become tuples).

    This is the mapping-level companion to :func:`freeze_toml_value`, used after
    :func:`read_toml` when a committed TOML document is about to be validated as
    a frozen registry, category, IVA, or user-profile schema object.
    """
    return {key: freeze_toml_value(value) for key, value in data.items()}
