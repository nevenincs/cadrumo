"""Typed TOML, JSON, and mapping helpers shared by the binding audit stages."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path

from cadrumo.core.toml import TomlDecodeError
from cadrumo.core.toml import load_toml as parse_toml_stream


def mapping(value: object) -> Mapping[str, object] | None:
    """Narrow a runtime mapping to the string-keyed shape TOML and JSON use."""
    if not isinstance(value, Mapping):
        return None
    result: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            return None
        result[key] = item
    return result


def required_mapping(value: object, *, context: str) -> Mapping[str, object]:
    """Require a string-keyed mapping at an internal typed boundary."""
    result = mapping(value)
    if result is None:
        raise TypeError(f"{context} must be a mapping with string keys")
    return result


def json_value(value: object) -> object:
    """Convert nested model and path values into stable JSON-compatible shapes."""
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, Mapping):
        return {str(key): json_value(item) for key, item in value.items()}
    if isinstance(value, (set, frozenset, tuple, list)):
        return [json_value(item) for item in value]
    return value


def stable_dump(path: Path, payload: Mapping[str, object]) -> None:
    """Write a deterministic UTF-8 JSON artifact, creating its parent first."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(json_value(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def relative(path: Path, root: Path) -> str:
    """Render a repository-relative path where possible."""
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def load_toml(path: Path) -> tuple[dict[str, object] | None, str | None]:
    """Load one source fragment and return failures as stable diagnostics."""
    try:
        with path.open("rb") as stream:
            return dict(required_mapping(parse_toml_stream(stream), context=str(path))), None
    except (OSError, TomlDecodeError) as exc:
        return None, f"{type(exc).__name__}: {exc}"


def revision_table(data: Mapping[str, object], revision_id: str) -> Mapping[str, object]:
    """Return one revision's raw table when both parent mappings are valid."""
    revisions = data.get("revisions")
    if not isinstance(revisions, Mapping):
        return {}
    revision = mapping(revisions.get(revision_id))
    return revision if revision is not None else {}


def rows(value: object) -> tuple[Mapping[str, object], ...]:
    """Return only well-formed string-keyed rows from a TOML array."""
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return ()
    result: list[Mapping[str, object]] = []
    for item in value:
        row = mapping(item)
        if row is not None:
            result.append(row)
    return tuple(result)


def string_values(value: object) -> tuple[str, ...]:
    """Read a scalar or array of string tokens without coercing other values."""
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return tuple(item for item in value if isinstance(item, str))
    return ()


def model_dump(value: object) -> dict[str, object]:
    """Convert a pydantic-like model to a string-keyed JSON-mode mapping."""
    dump = getattr(value, "model_dump", None)
    if not callable(dump):
        return {}
    result = mapping(dump(mode="json"))
    return dict(result) if result is not None else {}
