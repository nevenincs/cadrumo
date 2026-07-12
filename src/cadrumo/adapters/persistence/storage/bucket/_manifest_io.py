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
from datetime import datetime
from pathlib import Path

from .....core import parse_toml_text
from .....core.external_constants import UTF_8_ENCODING as _UTF_8_ENCODING
from .....core.locks import fsync_parent_dir
from .....core.logging import get_logger
from .._namespace_registry import BUCKET_MANIFEST_FILENAME
from ..errors import StorageValidationError
from ._errors import BucketValidationError
from ._layout import BucketPaths
from ._manifest import BucketManifest

MISSING_BUCKET_MANIFEST_MESSAGE = "bucket manifest is missing"
_BUCKET_VALIDATION_MESSAGE_KEY = "errors.integrity.integrity_storage_bucket_validation"
_log = get_logger(__name__)


def manifest_path(paths: BucketPaths) -> Path:
    """Return the canonical manifest path for the bucket."""
    return paths.bucket_dir / BUCKET_MANIFEST_FILENAME


def manifest_validation_error(message: str) -> StorageValidationError:
    """Build the typed, localized :class:`StorageValidationError` used by manifest I/O."""
    return StorageValidationError(message, translated_message=_BUCKET_VALIDATION_MESSAGE_KEY)


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
    raise BucketValidationError(f"unsupported TOML scalar type: {type(value)!r}")


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
    ``.tmp`` sibling, ``fsync``-ed, and renamed in place via
    :func:`os.replace`, after which the parent directory is ``fsync``-ed too.
    A crash mid-write leaves either the previous good manifest or the new good
    manifest, never a torn intermediate; the ``fsync`` pair makes that
    guarantee survive a hard power loss (matching the rotation atomic-write
    path), so a half-flushed tmp file can no longer become a zero-length
    manifest on reboot.
    """
    target = manifest_path(paths)
    tmp = target.with_suffix(target.suffix + ".tmp")
    payload = _serialise_manifest(manifest)
    try:
        with open(tmp, "w", encoding=_UTF_8_ENCODING) as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, target)
        fsync_parent_dir(target)
    except OSError as exc:
        _unlink_tmp_manifest(tmp)
        raise manifest_validation_error("bucket manifest cannot be written") from exc


def read_manifest(paths: BucketPaths) -> BucketManifest:
    """Read and strict-validate the manifest from ``<bucket-dir>/manifest.toml``.

    Args:
        paths: The resolved bucket paths providing the manifest file location.

    Returns:
        A strict-validated :class:`BucketManifest`.

    Raises:
        StorageValidationError: When the manifest cannot be read, cannot be parsed, or
            is missing the lifecycle status key.
    """
    target = manifest_path(paths)
    try:
        text = target.read_text(encoding=_UTF_8_ENCODING)
    except FileNotFoundError as exc:
        raise manifest_validation_error(MISSING_BUCKET_MANIFEST_MESSAGE) from exc
    except OSError as exc:
        raise manifest_validation_error("bucket manifest cannot be read") from exc
    payload: dict[str, object] = parse_toml_text(text, error_factory=manifest_validation_error)
    # TOML carries no native null; an absent ``last_unlocked_at`` key on disk
    # signals "never unlocked" and is hydrated to ``None`` at the boundary so
    # the strict pydantic model still rejects unknown keys.
    payload.setdefault("last_unlocked_at", None)
    payload.setdefault("idle_lock_minutes", None)
    if "status" not in payload:
        raise manifest_validation_error("bucket manifest is missing required lifecycle status")
    return BucketManifest.model_validate(payload)


def _unlink_tmp_manifest(tmp: Path) -> None:
    try:
        tmp.unlink()
    except FileNotFoundError:
        _log.debug("bucket manifest temp cleanup skipped because temp file is absent")
    except OSError as exc:
        _log.debug("bucket manifest temp cleanup failed error_type=%s", type(exc).__name__)


__all__ = [
    "MISSING_BUCKET_MANIFEST_MESSAGE",
    "manifest_path",
    "manifest_validation_error",
    "read_manifest",
    "write_manifest",
]
