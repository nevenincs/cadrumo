"""Shared content-hash integrity verification for outbound storage backends.

Both
:class:`aeat.adapters.outbound.storage._local.LocalFileSystemProvider` and
:class:`aeat.adapters.outbound.storage._google_drive.GoogleDriveProvider`
persist a ``content_hash`` (optionally ``sha256-``-prefixed) alongside each
object and re-check it on read. This module centralises the
:func:`strip_sha256_prefix` convention and the :func:`verify_content_hash`
compare-and-raise kernel so the two backends share one integrity contract; each
backend keeps its own message, context, and verification policy.
"""

from __future__ import annotations

from ._errors import OutboundStorageIntegrityError

_SHA256_PREFIX = "sha256-"
_SHA256_HEX_LENGTH = 64


def strip_sha256_prefix(stored_hash: str) -> str:
    """Return the bare hex digest from a possibly ``sha256-``-prefixed stored hash.

    Used by :func:`verify_content_hash` before comparing a stored provider
    digest with a caller-supplied :func:`aeat.core.hashing.sha256_hex` value.
    """
    if stored_hash.startswith(_SHA256_PREFIX):
        return stored_hash.split("-", 1)[1]
    return stored_hash


def verify_content_hash(
    actual_hash: str,
    stored_hash: str,
    *,
    message: str,
    context: dict[str, str],
    translated_message: str,
    require_full_digest: bool = False,
) -> None:
    """Raise :class:`OutboundStorageIntegrityError` when a stored hash disagrees.

    A no-op when ``stored_hash`` is empty or carries no digest. With
    ``require_full_digest`` the check is skipped unless the stripped digest is a
    full 64-character hex string
    (:class:`aeat.adapters.outbound.storage._google_drive.GoogleDriveProvider`
    policy); without it any non-empty stripped digest is compared against
    ``actual_hash``
    (:class:`aeat.adapters.outbound.storage._local.LocalFileSystemProvider`
    policy). ``actual_hash`` is supplied by the caller because the local backend
    reuses it to stamp the written sidecar.
    """
    if not stored_hash:
        return
    stripped = strip_sha256_prefix(stored_hash)
    if not stripped or (require_full_digest and len(stripped) != _SHA256_HEX_LENGTH):
        return
    if stripped != actual_hash:
        raise OutboundStorageIntegrityError(message, context=context, translated_message=translated_message)
