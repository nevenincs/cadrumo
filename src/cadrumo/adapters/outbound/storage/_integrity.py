"""Shared content-hash integrity verification for outbound storage backends.

Both
:class:`adapters.outbound.storage._local.LocalFileSystemProvider` and
:class:`adapters.outbound.storage._google_drive.GoogleDriveProvider`
persist a ``content_hash`` (optionally ``sha256-``-prefixed) alongside each
object and re-check it on read. This module centralises the
:func:`strip_sha256_prefix` convention and the :func:`verify_content_hash`
compare-and-raise kernel so the two backends share one integrity contract; each
backend keeps its own message, context, and verification policy.

One duty is applied by ONE backend only, and it is declared here rather than
left to be re-derived as an oversight. :func:`require_full_sha256_content_hash`
is called by the Drive backend and not by the local one, so Drive refuses
metadata that does not carry a full valid SHA-256 while local does not check
the digest's SHAPE at all -- it compares whatever non-empty digest the sidecar
holds, and :func:`verify_content_hash` is a documented no-op on an empty one.

Measured rather than assumed, when the asymmetry was reviewed: ``put`` refuses
a blank ``content_hash`` on both backends, so the application cannot create an
unverifiable object through its own write path; the malformed-but-non-empty
values ``put`` does accept already raise on read for both; and the local read
path now refuses a sidecar carrying no digest outright rather than inventing
one. What remains uncovered on local is a sidecar whose digest is present,
non-empty and structurally wrong in a way that still matches the payload --
which requires an editor who could equally rewrite the digest to match, so the
check would not stop them either.

The residue is therefore "local does not detect sidecar CORRUPTION by digest
shape", worth catching only if that case becomes real rather than
hypothetical. Deliberately not closed by tightening local, because doing so is
a behaviour change against a hole the application cannot open. Revisit if a
corruption report ever arrives.
"""

from __future__ import annotations

from ....application.operator_actions import no_action_precondition_verdict
from ....core import ActionEvidenceProvenance, NoRecoveryOutcome
from .errors import OutboundStorageIntegrityError

_SHA256_PREFIX = "sha256-"
_SHA256_HEX_LENGTH = 64
_HEX_DIGITS = frozenset("0123456789abcdef")


def strip_sha256_prefix(stored_hash: str) -> str:
    """Return the bare hex digest from a possibly ``sha256-``-prefixed stored hash.

    Used by :func:`verify_content_hash` before comparing a stored provider
    digest with a caller-supplied :func:`core.hashing.sha256_hex` value.
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
    (:class:`adapters.outbound.storage._google_drive.GoogleDriveProvider`
    policy); without it any non-empty stripped digest is compared against
    ``actual_hash``
    (:class:`adapters.outbound.storage._local.LocalFileSystemProvider`
    policy). ``actual_hash`` is supplied by the caller because the local backend
    reuses it to stamp the written sidecar.
    """
    if not stored_hash:
        return
    stripped = strip_sha256_prefix(stored_hash)
    if not stripped or (require_full_digest and len(stripped) != _SHA256_HEX_LENGTH):
        return
    if stripped != actual_hash:
        raise OutboundStorageIntegrityError(
            message,
            context=context,
            translated_message=translated_message,
            precondition_verdict=no_action_precondition_verdict(
                condition_id="storage.integrity.content_hash_matches",
                facts=context,
                provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                outcome=NoRecoveryOutcome.SAFETY,
            ),
        )


def require_full_sha256_content_hash(
    stored_hash: str,
    *,
    message: str,
    context: dict[str, str],
    translated_message: str,
) -> str:
    """Return a canonical SHA-256 digest or refuse unverified provider metadata."""
    digest = strip_sha256_prefix(stored_hash)
    if len(digest) != _SHA256_HEX_LENGTH or not all(character in _HEX_DIGITS for character in digest):
        raise OutboundStorageIntegrityError(
            message,
            context={**context, "stored_hash": stored_hash},
            translated_message=translated_message,
            precondition_verdict=no_action_precondition_verdict(
                condition_id="storage.integrity.sha256_digest_valid",
                facts={**context, "stored_hash": stored_hash},
                provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                outcome=NoRecoveryOutcome.SAFETY,
            ),
        )
    return digest


def verify_payload_byte_length(
    payload: bytes,
    stored_byte_length: int,
    *,
    message: str,
    context: dict[str, str],
    translated_message: str,
) -> None:
    """Raise when provider metadata does not describe the returned payload bytes.

    Both local sidecars and Drive file metadata declare the size of opaque
    stored bytes. The declaration is an integrity assertion, not display-only
    metadata: callers must never receive payload bytes paired with a different
    claimed size.

    Args:
        payload: Downloaded opaque provider bytes.
        stored_byte_length: Validated byte length declared by the provider.
        message: Human-readable provider-specific error message.
        context: Non-sensitive diagnostic context for the error envelope.
        translated_message: Localisation key for the provider-specific error.

    Raises:
        OutboundStorageIntegrityError: When the declared and actual lengths differ.
    """
    actual_byte_length = len(payload)
    if stored_byte_length != actual_byte_length:
        raise OutboundStorageIntegrityError(
            message,
            context={
                **context,
                "stored_byte_length": str(stored_byte_length),
                "actual_byte_length": str(actual_byte_length),
            },
            translated_message=translated_message,
            precondition_verdict=no_action_precondition_verdict(
                condition_id="storage.integrity.payload_byte_length_matches",
                facts={
                    **context,
                    "stored_byte_length": str(stored_byte_length),
                    "actual_byte_length": str(actual_byte_length),
                },
                provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                outcome=NoRecoveryOutcome.SAFETY,
            ),
        )
