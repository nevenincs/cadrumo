"""Atomic IO and selector resolution for the active-profile pointer file.

The pointer file lives at ``<cadrumo-root>/active-profile`` and is the on-disk
default after the per-invocation / per-shell override path. The CLI ``--profile``
flag is normalised into ``Settings.cadrumo_active_profile``, so this module's
runtime branches are settings override first and pointer file second. The write
path uses the write-then-rename pattern so a crashed switch never produces a
truncated pointer; the read path returns ``None`` only when the pointer is
absent.

The IO helpers serialise :class:`BucketPointer` records, capture and restore
the pointer's exact bytes without parsing them, and feed
:func:`resolve_active_bucket_id`, the central core resolver consumed by storage
and CLI startup flows. The resolver returns the selected bucket id string; it
does not prove a ``buckets/<id>/manifest.toml`` exists, scan profile display
labels, or open encrypted state. Those registry/existence checks belong to
application-layer manifest scanners that return
:class:`~application.workflow.ProfileBucketPointer`.

Repository factories that need a hard bucket id use
:func:`resolve_repository_bucket_id` so each domain can raise its own error type
while sharing the same pointer precedence.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

# Imported from its owning submodule, not the ``cadrumo.core`` facade: the
# facade serves this name through a PEP 562 ``__getattr__`` defined near the end
# of ``core/__init__``, so a facade import here fails for any caller reached
# while that package is still executing its own body. This module sits on the
# active-profile resolution path, which settings validation reaches, so it must
# stay importable from the earliest point in core's own initialisation.
from ._bucket_pointer import BucketPointer
from ._fsync import fsync_parent_dir

if TYPE_CHECKING:  # pragma: no cover — annotation-only import
    from .errors import CadrumoError


def pointer_path(root: Path) -> Path:
    """Return the canonical ``active-profile`` pointer path under the Cadrumo root.

    Args:
        root: Cadrumo local storage root.

    Returns:
        ``root / "active-profile"`` without touching the filesystem.
    """
    # Deferred for the same reason ``restore_pointer`` defers ``atomic_write``
    # below: this module is read during Settings() bootstrap
    # (core.config._resolve_database_url_for_active_profile imports
    # pointer_path/read_pointer from here before Settings exists). A
    # module-level import here would run at that same early point; deferring
    # to call time keeps the taxonomy import off the bootstrap path even
    # though ``_storage_taxonomy`` itself does not import ``.config``.
    from ._storage_taxonomy import StorageCategory, storage_location

    return root / storage_location(StorageCategory.ACTIVE_PROFILE_POINTER).relative_path()


_POINTER_READ_RETRY_SECONDS = 1.0
"""Budget for waiting out a concurrent writer's replace/clear of the pointer.

A peer's handle on the pointer lives microseconds; a denying ACL does not
clear at all. As in :mod:`core._lockfile_unlink`, the budget is the
discriminator rather than the error code -- and here it has to be, because the
read side carries no ``winerror`` to test.
"""

_POINTER_READ_POLL_SECONDS = 0.02


def _read_pointer_bytes(target: Path) -> bytes | None:
    """Read ``target``, tolerating a concurrent writer's replace or clear.

    The pointer is rewritten by :func:`restore_pointer` (write-then-rename) and
    removed by :func:`clear_pointer`, and this read sits on the ``Settings()``
    bootstrap path -- so any process starting up while another switches profile
    reads a file that is being replaced underneath it. Two failures follow, both
    measured on Windows under concurrent access:

    - The file vanishes between the caller's ``is_file()`` and the open, which
      raised :exc:`FileNotFoundError` from a function documented to answer
      ``None`` for an absent pointer.
    - The open is refused while a writer holds the file, as
      :exc:`PermissionError`. Unlike the removal path in
      :mod:`core._lockfile_unlink`, this one arrives with ``winerror`` unset,
      so contention cannot be told from a denying ACL by inspection; a bounded
      wait separates them instead, and a genuine denial outlasts it and raises.

    Retried on Windows only. POSIX has no sharing-violation class, so an
    ``EACCES`` there is genuine and propagates on the first attempt.

    Args:
        target: The pointer file to read.

    Returns:
        The file's bytes, or ``None`` when it is absent.

    Raises:
        OSError: For any read failure that is not a concurrent writer, and for
            a refusal that outlasts :data:`_POINTER_READ_RETRY_SECONDS`.
    """
    deadline = time.monotonic() + (_POINTER_READ_RETRY_SECONDS if sys.platform == "win32" else 0.0)
    while True:
        try:
            return target.read_bytes()
        except FileNotFoundError:
            return None
        except PermissionError:
            if sys.platform != "win32" or time.monotonic() >= deadline:
                raise
            time.sleep(_POINTER_READ_POLL_SECONDS)


def read_pointer(root: Path) -> BucketPointer | None:
    """Read and strict-validate the pointer file.

    Present files are parsed by
    :meth:`~core._bucket_pointer.BucketPointer.from_toml`; invalid TOML,
    unknown keys, and invalid scalar values propagate instead of being
    reclassified as an absent pointer.

    Args:
        root: Cadrumo local storage root directory that contains the
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
    raw = _read_pointer_bytes(target)
    if raw is None:
        return None
    return BucketPointer.from_toml(raw.decode("utf-8"))


def capture_pointer(root: Path) -> bytes | None:
    """Capture the active-profile pointer as exact bytes.

    Args:
        root: Cadrumo local storage root containing ``active-profile``.

    Returns:
        The file's unmodified bytes, or ``None`` when the pointer is absent.

    Raises:
        OSError: If the pointer exists but cannot be read.
    """
    return _read_pointer_bytes(pointer_path(root))


def clear_pointer(root: Path) -> None:
    """Clear the active-profile pointer idempotently.

    An absent pointer is already clear. After a successful unlink, the parent
    directory is synchronised on a best-effort basis where supported.

    Args:
        root: Cadrumo local storage root containing ``active-profile``.

    Raises:
        OSError: If an existing pointer cannot be removed.
    """
    target = pointer_path(root)
    try:
        target.unlink()
    except FileNotFoundError:
        return

    fsync_parent_dir(target)


def restore_pointer(root: Path, captured: bytes | None) -> None:
    """Restore an exact-byte active-profile pointer capture.

    A ``None`` capture clears the pointer. A byte capture is written through
    the hardened atomic byte path without parsing, decoding, or normalisation.

    Args:
        root: Cadrumo local storage root containing ``active-profile``.
        captured: Exact captured bytes, or ``None`` for an absent pointer.

    Raises:
        OSError: If clearing or atomically restoring the pointer fails.
    """
    if captured is None:
        clear_pointer(root)
        return

    # Deferred to avoid recreating the Settings bootstrap cycle described by
    # ``write_pointer`` below.
    from .atomic_write import atomic_write_hardened_bytes

    atomic_write_hardened_bytes(pointer_path(root), captured)


def resolve_active_bucket_id() -> str | None:
    """Resolve the active bucket id via the operator-facing precedence chain.

    Precedence, highest wins:

    1. ``Settings.cadrumo_active_profile`` — the in-process override
       written by the CLI ``--profile`` flag, or by an active
       :func:`~core.config.override_settings` block in tests. No
       environment variable populates it: profile selection belongs to
       the pointer file.
    2. ``<cadrumo-root>/active-profile`` plaintext pointer file written by
       ``profile create`` / ``config login``. This is the canonical
       default for interactive sessions and resolves the chicken-and-egg
       defect where an encrypted state row could not be read without
       first knowing which bucket to unlock.

    The CLI ``--profile`` flag, when supplied per-invocation, runs the
    process under an :func:`~core.config.override_settings` block
    that sets ``cadrumo_active_profile`` so rung one handles it without a
    fourth precedence rung.

    This resolver lives in the core layer: it reads only the settings
    :class:`~core.config.Settings` object and the plaintext pointer file,
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
    override = (settings.cadrumo_active_profile or "").strip()
    if override:
        return override
    pointer = read_pointer(settings.cadrumo_local_storage_root)
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
    :class:`~core.errors.NoActiveProfileError` if neither rung resolves.

    Diagnostic surfaces (browser-connectivity probe, status flows) MUST NOT call
    this helper — they call :func:`resolve_active_bucket_id` and supply their own
    fallback label so a missing profile stays diagnosable.

    Returns:
        The selected active bucket id.

    Raises:
        cadrumo.core.errors.NoActiveProfileError: If neither settings nor the
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
    """Serialise and atomically persist an active-profile pointer.

    Uses deterministic :class:`BucketPointer` TOML serialisation and the
    hardened atomic byte path. Persisting the selection does not validate the
    selected profile's manifest, registration, or lifecycle state.

    Args:
        root: Cadrumo local storage root that will contain the pointer file.
        pointer: Validated pointer record to serialise.

    Raises:
        OSError: If the parent directory cannot be created, the temporary file
            cannot be written, or the atomic replacement fails.
    """
    # ``restore_pointer`` defers the atomic-writer import: this module is read
    # during Settings() bootstrap
    # (core.config._resolve_database_url_for_active_profile imports
    # pointer_path/read_pointer from here before Settings exists), and
    # core.atomic_write transitively imports core.logging.get_logger,
    # which configures logging via load_settings() -- a module-level
    # import here would recreate the exact circular-bootstrap failure
    # pointer_path/read_pointer exist to avoid. Deferring to call time
    # (after Settings is already constructed in every real invocation)
    # breaks the cycle without reintroducing it.
    restore_pointer(root, pointer.to_toml().encode("utf-8"))


def resolve_repository_bucket_id(bucket_id: str | None, *, error_type: type[CadrumoError]) -> str:
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
        CadrumoError: The supplied ``error_type`` when ``bucket_id`` is blank or no
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
    "capture_pointer",
    "clear_pointer",
    "pointer_path",
    "read_pointer",
    "require_active_bucket_id",
    "resolve_active_bucket_id",
    "resolve_repository_bucket_id",
    "restore_pointer",
    "write_pointer",
]
