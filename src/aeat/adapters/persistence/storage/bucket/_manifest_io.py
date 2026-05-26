"""Atomic read/write IO for the plaintext bucket manifest.

The manifest sits at ``<bucket-dir>/manifest.toml``. Writes use the
write-then-rename pattern (tmp sibling, ``os.replace``) so a crash mid-write
can never surface as a torn read; reads round-trip through the strict
pydantic v2 :class:`BucketManifest` record so an unknown key or a torn
payload fails closed at the boundary.
"""

from __future__ import annotations

import base64
import os
import tomllib
from datetime import datetime
from pathlib import Path

from ..errors import StorageValidationError
from ._layout import BucketPaths
from ._manifest import BucketManifest

_MANIFEST_FILENAME = "manifest.toml"


def manifest_path(paths: BucketPaths) -> Path:
    """Return the canonical manifest path for the bucket."""

    return paths.bucket_dir / _MANIFEST_FILENAME


def _format_scalar(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, datetime):
        # RFC 3339 offset datetime is the TOML-native representation.
        text = value.isoformat()
        # Python emits ``+00:00`` for UTC; TOML accepts both ``Z`` and the
        # offset form so we keep the offset form for byte-stable serialise/
        # parse round-trips.
        return text
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    raise TypeError(f"unsupported TOML scalar type: {type(value)!r}")


def _serialise_manifest(manifest: BucketManifest) -> str:
    """Render the manifest as deterministic single-document TOML.

    Hand-formatted to keep the dependency footprint minimal (Python's stdlib
    provides ``tomllib`` for parsing but no writer); the schema is fixed at a
    small set of scalar keys plus the nested ``[kdf_params]`` table, so a
    hand-rolled emitter is bounded and reviewable.
    """

    kdf = manifest.kdf_params
    lines: list[str] = []
    lines.append(f"bucket_id = {_format_scalar(manifest.bucket_id)}")
    lines.append(f"label = {_format_scalar(manifest.label)}")
    lines.append(f"created_at = {_format_scalar(manifest.created_at)}")
    if manifest.last_unlocked_at is None:
        lines.append("last_unlocked_at =")
    else:
        lines.append(f"last_unlocked_at = {_format_scalar(manifest.last_unlocked_at)}")
    lines.append(f"recovery_enrolled = {_format_scalar(manifest.recovery_enrolled)}")
    if manifest.idle_lock_minutes is not None:
        lines.append(f"idle_lock_minutes = {_format_scalar(manifest.idle_lock_minutes)}")
    lines.append(f"key_schedule = {_format_scalar(manifest.key_schedule.value)}")
    lines.append(f"schema_version = {_format_scalar(manifest.schema_version)}")
    lines.append(f"status = {_format_scalar(manifest.status.value)}")
    lines.append("")
    lines.append("[kdf_params]")
    lines.append(f"algorithm = {_format_scalar(kdf.algorithm)}")
    lines.append(f"version = {_format_scalar(kdf.version)}")
    lines.append(f"memory_cost = {_format_scalar(kdf.memory_cost)}")
    lines.append(f"time_cost = {_format_scalar(kdf.time_cost)}")
    lines.append(f"parallelism = {_format_scalar(kdf.parallelism)}")
    salt_b64 = base64.b64encode(kdf.salt).decode("ascii")
    lines.append(f"salt = {_format_scalar(salt_b64)}")
    lines.append(f"output_length = {_format_scalar(kdf.output_length)}")

    # TOML accepts a missing value for an optional key only via omission, not
    # ``key =`` syntax; encode ``last_unlocked_at = None`` by simply omitting
    # the key. Replace the placeholder line we emitted above.
    rendered = "\n".join(line for line in lines if line != "last_unlocked_at =") + "\n"
    return rendered


def write_manifest(paths: BucketPaths, manifest: BucketManifest) -> None:
    """Atomically write the manifest under ``<bucket-dir>/manifest.toml``.

    Uses a write-then-rename pattern: the payload is staged under a
    ``.tmp`` sibling and renamed in place via :func:`os.replace`, so a
    crash mid-write leaves either the previous good manifest or the new
    good manifest, never a torn intermediate.
    """

    target = manifest_path(paths)
    tmp = target.with_suffix(target.suffix + ".tmp")
    payload = _serialise_manifest(manifest)
    tmp.write_text(payload, encoding="utf-8")
    os.replace(tmp, target)


def read_manifest(paths: BucketPaths) -> BucketManifest:
    """Read and strict-validate the manifest from ``<bucket-dir>/manifest.toml``.

    Raises:
        FileNotFoundError: If the manifest is absent.
        pydantic.ValidationError: If the manifest carries an unknown key,
            a wrong type, or a malformed structure.
        tomllib.TOMLDecodeError: If the TOML is unparsable.
    """

    target = manifest_path(paths)
    text = target.read_text(encoding="utf-8")
    # ``tomllib.loads`` is typed ``dict[str, Any]`` upstream by stdlib
    # convention; we narrow to ``dict[str, object]`` here so the
    # ``Any`` lasts a single expression and never escapes this
    # function. The dict is handed straight to a strict pydantic
    # model on the next line, so the boundary is one line wide.
    payload: dict[str, object] = dict(tomllib.loads(text))
    # TOML carries no native null; an absent ``last_unlocked_at`` key on disk
    # signals "never unlocked" and is hydrated to ``None`` at the boundary so
    # the strict pydantic model still rejects unknown keys.
    payload.setdefault("last_unlocked_at", None)
    if "status" not in payload:
        raise StorageValidationError("bucket manifest is missing required lifecycle status")
    return BucketManifest.model_validate(payload)


__all__ = ["manifest_path", "read_manifest", "write_manifest"]
