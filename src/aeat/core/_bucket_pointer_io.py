"""Atomic IO and selector resolution for the active-profile pointer file.

The pointer file lives at ``<aeat-root>/active-profile`` and is the on-disk
default after the per-invocation / per-shell override path. The CLI ``--profile``
flag is normalised into ``Settings.aeat_active_profile``, so this module's
runtime branches are settings override first and pointer file second. The write
path uses the write-then-rename pattern so a crashed switch never produces a
truncated pointer; the read path returns ``None`` only when the pointer is
absent.

The IO helpers serialise :class:`BucketPointer` records and feed
:func:`resolve_active_bucket_id`, the central core resolver consumed by storage
and CLI startup flows. The resolver returns the selected bucket id string; it
does not prove a ``buckets/<id>/manifest.toml`` exists, scan profile display
labels, or open encrypted state. Those registry/existence checks belong to
application-layer manifest scanners that return
:class:`~aeat.application.workflow.ProfileBucketPointer`.

Repository factories that need a hard bucket id use
:func:`resolve_repository_bucket_id` so each domain can raise its own error type
while sharing the same pointer precedence.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from . import BucketPointer

if TYPE_CHECKING:  # pragma: no cover — annotation-only import
    from .errors import AeatError

_POINTER_FILENAME = "active-profile"


def pointer_path(root: Path) -> Path:
    """Return the canonical ``active-profile`` pointer path under the AEAT root.

    Args:
        root: AEAT local storage root.

    Returns:
        ``root / "active-profile"`` without touching the filesystem.
    """
    return root / _POINTER_FILENAME


def read_pointer(root: Path) -> BucketPointer | None:
    """Read and strict-validate the pointer file.

    Present files are parsed by
    :meth:`~aeat.core._bucket_pointer.BucketPointer.from_toml`; invalid TOML,
    unknown keys, and invalid scalar values propagate instead of being
    reclassified as an absent pointer.

    Args:
        root: AEAT local storage root directory that contains the
            ``active-profile`` pointer file.

    Returns:
        The parsed :class:`BucketPointer`, or ``None`` when the pointer
        file is absent. The higher-level resolver treats ``None`` as
        "fall through to the next precedence rung".

    Raises:
        OSError: If the present pointer file cannot be read.
        tomllib.TOMLDecodeError: If the present file is not valid TOML.
        pydantic.ValidationError: If the present TOML violates the strict
            :class:`BucketPointer` schema.
    """
    target = pointer_path(root)
    if not target.is_file():
        return None
    text = target.read_text(encoding="utf-8")
    return BucketPointer.from_toml(text)


def resolve_active_bucket_id() -> str | None:
    """Resolve the active bucket id via the operator-facing precedence chain.

    Precedence, highest wins:

    1. ``Settings.aeat_active_profile`` — surfaced from the
       ``AEAT_ACTIVE_PROFILE`` environment variable (or an active
       :func:`~aeat.core.config.override_settings` block in tests).
       Per-shell override useful for CI, headless invocations, and the
       CLI ``--profile`` flag.
    2. ``<aeat-root>/active-profile`` plaintext pointer file written by
       ``profile create`` / ``config switch``. This is the canonical
       default for interactive sessions and resolves the chicken-and-egg
       defect where an encrypted state row could not be read without
       first knowing which bucket to unlock.

    The CLI ``--profile`` flag, when supplied per-invocation, runs the
    process under an :func:`~aeat.core.config.override_settings` block
    that sets ``aeat_active_profile`` so rung one handles it without a
    fourth precedence rung.

    This resolver lives in the core layer: it reads only the settings
    :class:`~aeat.core.config.Settings` object and the plaintext pointer file,
    both core-layer concerns. The
    at-rest crypto substrate (master-key provider) resolves the active
    bucket through this function, so it must sit at or below the adapter
    layer to keep the dependency direction acyclic.

    Returns:
        The selected active bucket id, or ``None`` when neither settings nor the
        pointer file selects one.
    """
    from .config import load_settings

    settings = load_settings()
    override = (settings.aeat_active_profile or "").strip()
    if override:
        return override
    pointer = read_pointer(settings.aeat_local_storage_root)
    if pointer is not None:
        return pointer.bucket_id
    return None


def require_active_bucket_id() -> str:
    """Resolve the active bucket id via the precedence chain, or raise.

    Companion to :func:`resolve_active_bucket_id` for call sites that require a
    selected profile rather than tolerating its absence. Operator-initiated auth
    session paths, the Cl@ve Móvil persistence path, the SEDE declarations-register
    profile name, and bucket-scoped repositories all sit on flows that require a
    profile to be selected; a missing profile is a genuine refusal, not a degraded
    read. Reads env var > pointer file; raises
    :class:`~aeat.core.errors.NoActiveProfileError` if neither rung resolves.

    Diagnostic surfaces (browser-connectivity probe, status flows) MUST NOT call
    this helper — they call :func:`resolve_active_bucket_id` and supply their own
    fallback label so a missing profile stays diagnosable.

    Returns:
        The selected active bucket id.

    Raises:
        aeat.core.errors.NoActiveProfileError: If neither settings nor the
            pointer file selects a bucket id.
    """
    from .errors import NoActiveProfileError

    bucket_id = resolve_active_bucket_id()
    if bucket_id is None:
        raise NoActiveProfileError(
            translated_message="application.workflow.errors.no_active_profile_bucket",
        )
    return bucket_id


def write_pointer(root: Path, pointer: BucketPointer) -> None:
    """Atomically write the pointer file via write-then-rename.

    The payload is staged at a ``.tmp`` sibling and renamed via
    :func:`os.replace`; a crashed process therefore leaves either the
    previous good pointer or the new good pointer on disk, never a torn
    intermediate. The payload comes from
    :meth:`~aeat.core._bucket_pointer.BucketPointer.to_toml`, and the AEAT root
    is created lazily if absent.

    Args:
        root: AEAT local storage root that will contain the pointer file.
        pointer: Validated pointer record to serialise.

    Raises:
        OSError: If the parent directory cannot be created, the temporary file
            cannot be written, or the atomic replacement fails.
    """
    target = pointer_path(root)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(pointer.to_toml(), encoding="utf-8")
    os.replace(tmp, target)


def resolve_repository_bucket_id(bucket_id: str | None, *, error_type: type[AeatError]) -> str:
    """Resolve an explicit-or-active profile bucket id for a runtime repository.

    Single canonical home for the per-domain repository bucket-id resolution
    that the ``domain.modelos``, ``domain.filing``, and ``application.filing``
    runtime-repository modules each previously copied verbatim, differing only
    in the domain error they raise. An explicit, non-blank ``bucket_id`` is
    returned trimmed; a blank explicit id or an absent active profile both
    raise ``error_type`` (the caller's domain error) carrying the shared
    ``no_active_profile_bucket`` message and a structured reason. This is the
    repository-facing companion to :func:`require_active_bucket_id`.

    Args:
        bucket_id: An explicit bucket id, or ``None`` to fall back to the
            active profile bucket.
        error_type: The caller's domain error class raised when no usable
            bucket id can be resolved.

    Returns:
        The resolved bucket id.

    Raises:
        AeatError: The supplied ``error_type`` when ``bucket_id`` is blank or no
            active profile bucket can be resolved.
    """
    if bucket_id is not None:
        trimmed = bucket_id.strip()
        if trimmed:
            return trimmed
        raise error_type(
            translated_message="application.workflow.errors.no_active_profile_bucket",
            context={"reason": "blank_explicit_bucket_id"},
        )
    active = resolve_active_bucket_id()
    if active is None:
        raise error_type(
            translated_message="application.workflow.errors.no_active_profile_bucket",
            context={"reason": "missing_active_profile_bucket"},
        )
    return active


__all__ = [
    "pointer_path",
    "read_pointer",
    "require_active_bucket_id",
    "resolve_active_bucket_id",
    "resolve_repository_bucket_id",
    "write_pointer",
]
