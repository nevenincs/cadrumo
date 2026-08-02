"""Canonical bucket identity for the master-key cryptographic boundary.

Every master-key surface that binds a bucket into AEAD additional-authenticated
data, a document key, or a keychain lookup must agree with the storage layer on
what a bucket identity *is*. :data:`~core.identity.BucketId` is that authority:
surrounding whitespace stripped, blank refused, 128 characters at most.

Binding a raw string instead lets the cryptographic identity and the storage
ownership identity disagree. Two consequences follow, and both are real rather
than theoretical: a value the storage layer would refuse outright (blank, or
overlength) still produces valid ciphertext, and a whitespace-wrapped spelling
of a *valid* id produces ciphertext that cannot be opened under the canonical
spelling of the very same bucket -- the AAD is byte-compared, so the two
spellings are two different buckets to AES-GCM and one identical bucket to
every other layer.

Normalizing here, once, means the cryptographic boundary inherits the storage
boundary's answer rather than restating it.
"""

from __future__ import annotations

from pydantic import TypeAdapter, ValidationError

from .....core.identity import BucketId

_BUCKET_ID_ADAPTER: TypeAdapter[str] = TypeAdapter(BucketId)


def canonical_bucket_id(bucket_id: str) -> str:
    """Return the canonical spelling of ``bucket_id``.

    Args:
        bucket_id: A bucket identity as supplied by a caller, in any
            spelling.

    Returns:
        The value normalized through :data:`~core.identity.BucketId`, so two
        spellings of one bucket compose byte-identical associated data.

    Raises:
        ValueError: When the value is not a valid bucket identity. Callers
            translate this into their own typed storage error, which is why
            the shared helper raises the plain builtin rather than picking one
            surface's error class for every caller.
    """
    try:
        return _BUCKET_ID_ADAPTER.validate_python(bucket_id)
    except ValidationError as exc:
        raise ValueError("bucket_id is not a canonical bucket identity") from exc


__all__ = ["canonical_bucket_id"]
