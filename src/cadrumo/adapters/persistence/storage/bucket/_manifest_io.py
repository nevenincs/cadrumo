"""Atomic read/write IO for the plaintext bucket manifest.

The manifest sits at ``<bucket-dir>/manifest.toml``. Writes go through
:func:`~cadrumo.core.atomic_write.atomic_write_text` (standard tier) so a
crash mid-write can never surface as a torn read; reads round-trip through
the strict pydantic v2 :class:`BucketManifest` record so an unknown key or a
torn payload fails closed at the boundary.
"""

from __future__ import annotations

import base64
from datetime import datetime
from pathlib import Path

from pydantic import ValidationError

from .....core import parse_toml_text
from .....core.atomic_write import atomic_write_text
from .....core.external_constants import UTF_8_ENCODING as _UTF_8_ENCODING
from .._namespace_registry import BUCKET_MANIFEST_FILENAME
from ..errors import StorageValidationError
from ._errors import BucketValidationError
from ._layout import BucketPaths
from ._manifest import (
    BUCKET_MANIFEST_DURABILITY_FLOOR,
    BUCKET_MANIFEST_SCHEMA_VERSION,
    BucketManifest,
)

MISSING_BUCKET_MANIFEST_MESSAGE = "bucket manifest is missing"
_BUCKET_VALIDATION_MESSAGE_KEY = "errors.integrity.integrity_storage_bucket_validation"


def manifest_path(paths: BucketPaths) -> Path:
    """Return the canonical manifest path for the bucket."""
    return paths.bucket_dir / BUCKET_MANIFEST_FILENAME


def manifest_validation_error(message: str) -> StorageValidationError:
    """Build the typed, localized :class:`StorageValidationError` used by manifest I/O."""
    return StorageValidationError(message, translated_message=_BUCKET_VALIDATION_MESSAGE_KEY)


def ensure_manifest_schema_readable(schema_version: int) -> None:
    """Refuse a bucket-manifest version this application cannot read.

    A ceiling with a durability floor, matching the sealed-archive tier rather
    than the secure-object tier: the manifest carries no upgrade dispatch, so
    there is nothing to transform an older layout and the two ends of the range
    are the whole contract. Under ``PRE_RELEASE`` the floor equals the current
    version, which makes this an equality today; it widens to a real range at
    the checkpoint without a second edit.

    The two directions are distinguished deliberately. Above the ceiling is
    "upgrade the application" and is recoverable by the operator; below the floor
    is "this bucket predates the guarantee" and is not. Collapsing them into one
    message would tell an operator with a newer bucket that their data is too
    old, which is both wrong and alarming.

    Raises:
        StorageValidationError: When the version is above the current version or
            below the durability floor.
    """
    if schema_version > BUCKET_MANIFEST_SCHEMA_VERSION:
        raise StorageValidationError(
            f"bucket manifest is at schema version {schema_version}; this application supports up to "
            f"{BUCKET_MANIFEST_SCHEMA_VERSION}",
            translated_message="errors.integrity.integrity_storage_bucket_manifest_version_from_future",
            context={
                "schema_version": str(schema_version),
                "max_supported": str(BUCKET_MANIFEST_SCHEMA_VERSION),
            },
        )
    if schema_version < BUCKET_MANIFEST_DURABILITY_FLOOR:
        raise StorageValidationError(
            f"bucket manifest is at schema version {schema_version}; this application reads no lower than "
            f"{BUCKET_MANIFEST_DURABILITY_FLOOR}",
            translated_message="errors.integrity.integrity_storage_bucket_manifest_version_below_floor",
            context={
                "schema_version": str(schema_version),
                "durability_floor": str(BUCKET_MANIFEST_DURABILITY_FLOOR),
            },
        )


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
    if manifest.session_absolute_minutes is not None:
        lines.append(f"session_absolute_minutes = {_format_scalar(manifest.session_absolute_minutes)}")
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

    Delegates to :func:`~cadrumo.core.atomic_write.atomic_write_text`
    (standard tier): the payload is staged at a tempfile sibling, ``fsync``-ed,
    and renamed in place via :func:`os.replace`, after which the parent
    directory is ``fsync``-ed too. A crash mid-write leaves either the
    previous good manifest or the new good manifest, never a torn
    intermediate; the ``fsync`` pair makes that guarantee survive a hard
    power loss, so a half-flushed tempfile can no longer become a zero-length
    manifest on reboot.

    A missing bucket directory is refused rather than silently created --
    the atomic-write helper creates its target's parent directory by
    default, but ``write_manifest`` must never provision an un-provisioned
    bucket; :func:`~cadrumo.application.user_profile` (or the equivalent
    bucket-provisioning call site) owns directory creation.

    The instance is re-validated before a byte is serialised, making this
    the single validating write ingress symmetric to
    :func:`read_manifest`'s validating read ingress. That symmetry is not
    decoration: several writers mutate a manifest through
    ``model_copy(update=...)``, which SKIPS validation, so without this
    check a constraint-violating value reaches disk and is refused only on
    the next read. On this format a deferred refusal is not "caught later"
    -- the bucket-scan path swallows manifest read failures, so the profile
    would simply vanish from the operator's listing with no signal. Refusing
    at write time surfaces the fault inside the operation that caused it.
    """
    target = manifest_path(paths)
    try:
        BucketManifest.model_validate(manifest.model_dump(mode="python"))
    except ValidationError as exc:
        raise manifest_validation_error("bucket manifest is not valid and was not written") from exc
    payload = _serialise_manifest(manifest)
    try:
        if not target.parent.is_dir():
            raise FileNotFoundError(target.parent)
        atomic_write_text(target, payload, encoding=_UTF_8_ENCODING)
    except OSError as exc:
        raise manifest_validation_error("bucket manifest cannot be written") from exc


def read_manifest(paths: BucketPaths) -> BucketManifest:
    """Read and strict-validate the manifest from ``<bucket-dir>/manifest.toml``.

    Args:
        paths: The resolved bucket paths providing the manifest file location.

    Returns:
        A strict-validated :class:`BucketManifest`.

    The version is range-gated before the manifest is returned: a version above
    the current one was written by a newer application, and a version below the
    durability floor predates what this build can read. Until now the manifest
    was the only persisted format with a ``schema_version`` field and no gate of
    any kind on it, so a foreign version was accepted silently and flowed into
    the key-schedule discriminator and the plaintext lifecycle mirror.

    Raises:
        StorageValidationError: When the manifest cannot be read, cannot be
            parsed, is missing the lifecycle status key, or carries a schema
            version outside the readable range.
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
    payload.setdefault("session_absolute_minutes", None)
    if "status" not in payload:
        raise manifest_validation_error("bucket manifest is missing required lifecycle status")
    manifest = BucketManifest.model_validate(payload)
    ensure_manifest_schema_readable(manifest.schema_version)
    return manifest


__all__ = [
    "MISSING_BUCKET_MANIFEST_MESSAGE",
    "ensure_manifest_schema_readable",
    "manifest_path",
    "manifest_validation_error",
    "read_manifest",
    "write_manifest",
]
