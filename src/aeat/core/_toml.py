"""Canonical TOML read + freeze helpers shared across loaders.

Multiple committed-TOML loaders (registry definitions, the user-profile
schema) need the same two operations: parse a TOML file with errors
re-raised as a domain-specific exception, and recursively freeze the
parsed mapping so list values become tuples. These helpers are the
single source of that behaviour.
"""

from __future__ import annotations

import tomllib
from collections.abc import Callable
from pathlib import Path


def read_toml(path: Path, *, error_factory: Callable[[str], Exception]) -> dict[str, object]:
    """Parse a TOML file, re-raising failures via ``error_factory``.

    Args:
        path: Path of the TOML file to read.
        error_factory: Callable that builds the domain-specific
            exception from a message. Invoked on decode and OS errors
            so each loader keeps its own error type.

    Returns:
        The parsed top-level TOML mapping.
    """
    try:
        with path.open("rb") as fh:
            return tomllib.load(fh)
    except tomllib.TOMLDecodeError as exc:
        raise error_factory(f"{path}: invalid TOML: {exc}") from exc
    except OSError as exc:
        raise error_factory(f"{path}: cannot read TOML: {exc}") from exc


def freeze_toml_value(value: object) -> object:
    """Recursively freeze one parsed TOML value, turning lists into tuples."""
    if isinstance(value, list):
        return tuple(freeze_toml_value(item) for item in value)
    if isinstance(value, dict):
        return {key: freeze_toml_value(item) for key, item in value.items()}
    return value


def freeze_toml(data: dict[str, object]) -> dict[str, object]:
    """Recursively freeze a parsed TOML mapping (lists become tuples)."""
    return {key: freeze_toml_value(value) for key, value in data.items()}
