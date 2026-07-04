"""Encrypt-for-recipient transport for review packages (X25519 ECIES).

This module adds a CONFIDENTIALITY layer on top of the review-package
checksum-integrity (:mod:`aeat.application.modelo._review_package`) and
authenticity (:mod:`aeat.application.modelo._review_package_signing`,
:mod:`aeat.application.modelo._review_package_counter_sign`) layers: a
review package sealed with :func:`encrypt_review_package_for_recipient`
can be opened only by the holder of the matching X25519 private key --
unlike ``sign``/``counter-sign``, which leave the archive itself in
plaintext ZIP form.

Construction (ECIES over the primitives already vetted and already
shipped by this project -- no new dependency, see
``2026-07-04-recipient-encryption-adr``):

1. A fresh EPHEMERAL X25519 keypair is generated for this one message
   (``cryptography.hazmat.primitives.asymmetric.x25519.X25519PrivateKey.generate()``).
2. ECDH is performed between the ephemeral private key and the
   recipient's long-term public key
   (:class:`~aeat.application.modelo.RecipientFingerprintRecord`),
   producing a 32-byte shared secret.
3. The shared secret is NEVER used directly as an AEAD key. It is run
   through :func:`~aeat.adapters.persistence.storage.crypto.derive_key`
   (HKDF-SHA256), with the HKDF ``salt`` set to the ephemeral public key
   and the ``context`` (HKDF ``info``) bound to a fixed domain-separation
   string PLUS the recipient's public key -- so a derived key can never
   be reused across a different ephemeral sender key or a different
   recipient.
4. The package bytes are AEAD-encrypted via
   :func:`~aeat.adapters.persistence.storage.crypto.encrypt_record`
   (AES-256-GCM), with the recipient's public key bound into the
   associated data -- so a ciphertext cannot be silently re-targeted at
   a different recipient's key without the AEAD tag failing to verify.
5. The returned :class:`RecipientEncryptedPackage` envelope carries the
   ephemeral public key, the recipient's public key, and the AEAD wire
   bytes -- everything the recipient needs to reverse the ECDH and
   decrypt, and nothing that identifies the sender (no long-term sender
   keypair is required or persisted for this direction).

Key custody (``sensitive-financial-data-secure-storage-only``): the
review-package bytes are read into memory, encrypted in memory, and the
CIPHERTEXT envelope is the only artefact this module returns to the
caller; the caller is responsible for writing the envelope bytes to its
requested output path. Nothing is staged to a temp file. The recipient's
public key carries no secrecy requirement (it is looked up from
:class:`~aeat.application.modelo.RecipientFingerprintRegistryRepository`);
the ephemeral sender private key exists only for the duration of one
call and is never persisted.

Expiry and replay defence (``2026-07-04-recipient-encryption-adr``, the
review-only/expiry/replay follow-up slice): every envelope carries an
``issued_at`` timestamp, an optional ``valid_until`` deadline, a random
``envelope_nonce_hex`` (independent of the AEAD nonce embedded in
``ciphertext``, minted purely as a replay-detection token), and a
``review_only`` flag.

* **Expiry** is checked entirely inside :func:`decrypt_review_package_for_recipient`
  against an explicit, caller-supplied ``now`` (never the wall clock read
  directly by this module, so the check is deterministic and testable): a
  package presented after its ``valid_until`` deadline is refused before AEAD
  decryption is even attempted. A ``valid_until=None`` envelope never expires.
* **Replay defence** is a TWO-PARTY contract this module only half-owns: the
  envelope's ``envelope_nonce_hex`` is the token a caller checks against
  :class:`~aeat.application.modelo.RecipientReplayGuardRepository` (a
  persisted, bucket-scoped consumed-nonce ledger) before or after calling
  :func:`decrypt_review_package_for_recipient` -- this module mints and
  carries the nonce but performs no persistence itself (this is the
  ``composition-service-no-parallel-write-path`` boundary: encryption and
  decryption stay pure in-memory primitives, and the CLI decrypt-side
  composition owns the ledger check).
* **Review-only mode** (``review_only=True``) asserts the sealed package
  carries no filing authority: the recipient may read and verify it, but it
  is NOT evidence that the underlying revision has been (or will be) filed
  with AEAT. :func:`decrypt_review_package_for_recipient` returns a typed
  :class:`RecipientDecryptedPackage` (bytes plus the ``review_only`` flag)
  rather than bare ``bytes``, so a downstream consumer cannot lose the flag
  and mistake a review-only handoff for a filing artefact.

See Also:
    :mod:`aeat.application.modelo._review_package_recipient_registry`
        Where a recipient's trusted public key is registered and looked
        up before calling this module.
    :mod:`aeat.application.modelo._review_package_recipient_replay_guard`
        The consumed-nonce ledger a caller composes around
        :func:`decrypt_review_package_for_recipient` for replay defence.
    :mod:`aeat.application.modelo._review_package`
        Builds and integrity-verifies the review package this module
        encrypts.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta

from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey,
    X25519PublicKey,
)
from pydantic import BaseModel, Field, model_validator

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.errors import AeatError
from ...core.time import now as _utc_now

#: Wire-format version of the recipient-encryption envelope. Bumped when
#: the envelope schema changes shape.
_RECIPIENT_ENCRYPTION_ENVELOPE_VERSION = 1

#: HKDF domain-separation context. Distinct from any other HKDF context
#: string used elsewhere in the codebase (e.g. secure-object row keys,
#: DEK wrapping) so a key derived here can never collide with a key
#: derived for an unrelated purpose even if the same shared secret were
#: (incorrectly) reused.
_HKDF_CONTEXT_PREFIX = b"aeat.review_package.recipient_encryption.v1"

_HEX_PATTERN_64 = r"^[0-9a-f]{64}$"

#: Byte length of the replay-detection nonce (independent of, and never
#: reused as, the AEAD nonce embedded inside ``ciphertext``).
_REPLAY_NONCE_BYTES = 32


class RecipientEncryptionError(AeatError):
    """Base error for review-package recipient-encryption failures."""


class RecipientDecryptionError(RecipientEncryptionError):
    """Raised when a recipient-encrypted package fails to decrypt.

    Covers cryptographic AEAD-tag failure (tampered ciphertext or wrong
    private key), a mismatched recipient public key (the caller's private
    key does not correspond to the envelope's declared recipient public
    key), and an expired ``valid_until`` deadline -- never distinguished
    further, so an attacker cannot use error content to learn which check
    failed.
    """


class RecipientEncryptedPackage(BaseModel):
    """Wire envelope for a review package encrypted for one recipient.

    ``ephemeral_public_key_hex`` and ``recipient_public_key_hex`` are
    both raw 32-byte X25519 public keys, hex-encoded. ``ciphertext``
    is the AEAD wire form (``nonce || ciphertext_with_tag``) produced by
    :func:`~aeat.adapters.persistence.storage.crypto.encrypt_record`.

    ``envelope_nonce_hex`` is a replay-detection token, independent of the
    AEAD nonce embedded in ``ciphertext``: a caller checks it against
    :class:`~aeat.application.modelo.RecipientReplayGuardRepository` to
    refuse a package presented more than once. ``issued_at`` /
    ``valid_until`` bound the envelope's validity window (``valid_until``
    of ``None`` means the envelope never expires); the deadline is checked
    inside :func:`decrypt_review_package_for_recipient` against an explicit
    caller-supplied ``now``, never the wall clock read by this module.
    ``review_only`` asserts the sealed package carries no filing authority
    -- see the module docstring.
    """

    model_config = _STRICT_FROZEN

    envelope_version: int = Field(default=_RECIPIENT_ENCRYPTION_ENVELOPE_VERSION, ge=1)
    ephemeral_public_key_hex: str = Field(pattern=_HEX_PATTERN_64)
    recipient_public_key_hex: str = Field(pattern=_HEX_PATTERN_64)
    ciphertext: bytes = Field(min_length=1)
    envelope_nonce_hex: str = Field(pattern=_HEX_PATTERN_64)
    issued_at: datetime
    valid_until: datetime | None = Field(default=None)
    review_only: bool = Field(default=False)

    @model_validator(mode="after")
    def _valid_until_is_after_issued_at(self) -> RecipientEncryptedPackage:
        if self.valid_until is not None and self.valid_until <= self.issued_at:
            raise ValueError("valid_until must be strictly after issued_at")
        return self


def _hkdf_context(recipient_public_key_hex: str) -> bytes:
    """Return the HKDF ``info`` bytes binding a derived key to one recipient.

    Domain-separates the derived AEAD key from any other HKDF use in the
    codebase, and from a derivation for a *different* recipient's public
    key, so the same ephemeral keypair could never (even by caller
    error) yield the same derived key for two different recipients.
    """
    return _HKDF_CONTEXT_PREFIX + b":" + recipient_public_key_hex.encode("ascii")


def _associated_data(recipient_public_key_hex: str) -> bytes:
    """Return the AEAD associated data binding ciphertext to one recipient.

    Any attempt to present this ciphertext as encrypted for a different
    recipient's public key fails AEAD authentication, because the
    associated data would no longer match.
    """
    return b"aeat.review_package.recipient:" + recipient_public_key_hex.encode("ascii")


def encrypt_review_package_for_recipient(
    package_bytes: bytes,
    *,
    recipient_public_key_hex: str,
    review_only: bool = False,
    valid_for: timedelta | None = None,
    issued_at: datetime | None = None,
) -> RecipientEncryptedPackage:
    """Seal ``package_bytes`` so only ``recipient_public_key_hex``'s holder can open it.

    Generates a fresh ephemeral X25519 keypair, performs ECDH against the
    recipient's public key, derives a per-message AES-256-GCM key via
    HKDF-SHA256, and encrypts. See the module docstring for the full
    construction. Never writes ``package_bytes`` or the derived key to
    disk; the caller is responsible for persisting the returned
    envelope's bytes.

    Args:
        package_bytes: The plaintext review-package archive bytes to
            seal (read into memory by the caller; this function performs
            no filesystem I/O).
        recipient_public_key_hex: The recipient's raw 32-byte X25519
            public key, hex-encoded (see
            :class:`~aeat.application.modelo.RecipientFingerprintRecord`).
        review_only: When ``True``, marks the sealed package as carrying
            no filing authority -- see the module docstring. Defaults to
            ``False`` (a normal filing-grade handoff).
        valid_for: Optional validity window measured from ``issued_at``.
            When supplied, the envelope's ``valid_until`` is
            ``issued_at + valid_for`` and
            :func:`decrypt_review_package_for_recipient` refuses the
            package once that deadline has passed. ``None`` (the default)
            produces an envelope that never expires.
        issued_at: Optional override for the envelope's ``issued_at``
            timestamp (tests only); defaults to the current UTC time.

    Raises:
        RecipientEncryptionError: If ``recipient_public_key_hex`` is not
            a well-formed X25519 public key, or if ``valid_for`` is not a
            strictly positive duration.
    """
    from ...adapters.persistence.storage.crypto import derive_key, encrypt_record

    try:
        recipient_public_key = X25519PublicKey.from_public_bytes(bytes.fromhex(recipient_public_key_hex))
    except (ValueError, TypeError) as exc:
        raise RecipientEncryptionError(
            "recipient_public_key_hex is not a well-formed X25519 public key",
            translated_message="application.modelo.errors.recipient_encryption_invalid_key",
        ) from exc

    if valid_for is not None and valid_for <= timedelta(0):
        raise RecipientEncryptionError(
            "valid_for must be a strictly positive duration",
            translated_message="application.modelo.errors.recipient_encryption_invalid_key",
        )

    ephemeral_private_key = X25519PrivateKey.generate()
    ephemeral_public_key = ephemeral_private_key.public_key()
    ephemeral_public_key_hex = ephemeral_public_key.public_bytes_raw().hex()

    shared_secret = ephemeral_private_key.exchange(recipient_public_key)
    derived_key = derive_key(
        key_material=shared_secret,
        salt=ephemeral_public_key.public_bytes_raw(),
        context=_hkdf_context(recipient_public_key_hex),
    )
    encrypted = encrypt_record(
        package_bytes,
        key=derived_key,
        associated_data=_associated_data(recipient_public_key_hex),
    )

    envelope_issued_at = issued_at or _utc_now()
    envelope_valid_until = envelope_issued_at + valid_for if valid_for is not None else None

    return RecipientEncryptedPackage(
        ephemeral_public_key_hex=ephemeral_public_key_hex,
        recipient_public_key_hex=recipient_public_key_hex,
        ciphertext=encrypted.to_wire(),
        envelope_nonce_hex=secrets.token_hex(_REPLAY_NONCE_BYTES),
        issued_at=envelope_issued_at,
        valid_until=envelope_valid_until,
        review_only=review_only,
    )


class RecipientPackageExpiredError(RecipientDecryptionError):
    """Raised when a recipient-encrypted package is presented past its ``valid_until`` deadline.

    A subclass of :class:`RecipientDecryptionError` (rather than a sibling)
    so an existing ``except RecipientDecryptionError`` catch-all keeps
    working verbatim; callers that need to distinguish expiry from a
    cryptographic failure may catch this subclass specifically, though the
    ADR's undifferentiated-failure posture means the rendered message is
    identical either way.
    """


class RecipientDecryptedPackage(BaseModel):
    """Recovered plaintext bytes plus the envelope's carried disposition flags.

    Returned by :func:`decrypt_review_package_for_recipient` instead of
    bare ``bytes`` so a downstream consumer cannot lose the ``review_only``
    flag and mistake a review-only handoff for a filing-grade artefact.
    """

    model_config = _STRICT_FROZEN

    package_bytes: bytes = Field(min_length=1)
    review_only: bool


def decrypt_review_package_for_recipient(
    envelope: RecipientEncryptedPackage,
    *,
    recipient_private_key: X25519PrivateKey,
    now: datetime | None = None,
) -> RecipientDecryptedPackage:
    """Reverse :func:`encrypt_review_package_for_recipient` and return the package bytes.

    Reconstructs the same derived AEAD key by performing ECDH between
    ``recipient_private_key`` and the envelope's ephemeral public key,
    then decrypts and authenticates. A wrong ``recipient_private_key`` (or
    any tampering of ``envelope.ciphertext`` or the declared public keys)
    fails AEAD authentication. Before any cryptographic work, the envelope's
    ``valid_until`` deadline (when set) is checked against ``now``; an
    expired envelope is refused without attempting decryption.

    Replay defence is NOT performed here: this function is a pure
    encrypt/decrypt primitive with no persistence dependency
    (``composition-service-no-parallel-write-path``). A caller that needs
    replay defence composes
    :class:`~aeat.application.modelo.RecipientReplayGuardRepository` around
    this call, keyed on ``envelope.envelope_nonce_hex``.

    Args:
        envelope: The :class:`RecipientEncryptedPackage` produced by
            :func:`encrypt_review_package_for_recipient`.
        recipient_private_key: The recipient's own X25519 private key.
        now: The instant to evaluate ``envelope.valid_until`` against.
            Defaults to the current UTC time; tests inject an explicit
            value rather than relying on the wall clock.

    Returns:
        A :class:`RecipientDecryptedPackage` carrying the original
        plaintext review-package archive bytes and the envelope's
        ``review_only`` disposition.

    Raises:
        RecipientPackageExpiredError: If ``envelope.valid_until`` is set
            and ``now`` is at or past that deadline.
        RecipientDecryptionError: If ``recipient_private_key`` does not
            match the envelope's declared recipient public key, or the
            ciphertext fails AEAD authentication for any reason
            (tampering, corruption, wrong key).
    """
    from ...adapters.persistence.storage import DecryptionError
    from ...adapters.persistence.storage.crypto import EncryptedBlob, decrypt_record, derive_key

    evaluated_at = now or _utc_now()
    if envelope.valid_until is not None and evaluated_at >= envelope.valid_until:
        raise RecipientPackageExpiredError(
            "recipient-encrypted package has expired; the recipient must request a fresh package",
            translated_message="application.modelo.errors.recipient_decryption_failed",
        )

    recipient_public_key_hex = recipient_private_key.public_key().public_bytes_raw().hex()
    if recipient_public_key_hex != envelope.recipient_public_key_hex:
        raise RecipientDecryptionError(
            "recipient_private_key does not match the envelope's declared recipient public key",
            translated_message="application.modelo.errors.recipient_decryption_failed",
        )

    ephemeral_public_key = X25519PublicKey.from_public_bytes(bytes.fromhex(envelope.ephemeral_public_key_hex))
    shared_secret = recipient_private_key.exchange(ephemeral_public_key)
    derived_key = derive_key(
        key_material=shared_secret,
        salt=bytes.fromhex(envelope.ephemeral_public_key_hex),
        context=_hkdf_context(envelope.recipient_public_key_hex),
    )
    try:
        recovered = decrypt_record(
            EncryptedBlob.from_wire(envelope.ciphertext),
            key=derived_key,
            associated_data=_associated_data(envelope.recipient_public_key_hex),
        )
    except DecryptionError as exc:
        raise RecipientDecryptionError(
            "recipient-encrypted package failed AEAD authentication",
            translated_message="application.modelo.errors.recipient_decryption_failed",
        ) from exc

    return RecipientDecryptedPackage(package_bytes=recovered, review_only=envelope.review_only)


__all__ = [
    "RecipientDecryptedPackage",
    "RecipientDecryptionError",
    "RecipientEncryptedPackage",
    "RecipientEncryptionError",
    "RecipientPackageExpiredError",
    "decrypt_review_package_for_recipient",
    "encrypt_review_package_for_recipient",
]
