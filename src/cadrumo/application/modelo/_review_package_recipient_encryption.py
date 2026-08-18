"""Encrypt-for-recipient transport for review packages (X25519 ECIES).

This module adds a CONFIDENTIALITY layer on top of the review-package
checksum-integrity (:mod:`~application.modelo._review_package`) and
authenticity (:mod:`~application.modelo._review_package_signing`,
:mod:`~application.modelo._review_package_counter_sign`) layers: a
review package sealed with :func:`encrypt_review_package_for_recipient`
can be opened only by the holder of the matching X25519 private key --
unlike ``sign``/``counter-sign``, which leave the archive itself in
plaintext ZIP form.

Construction (ECIES over the primitives already vetted and already
shipped by this project -- no new dependency):

1. A fresh EPHEMERAL X25519 keypair is generated for this one message
   (``cryptography.hazmat.primitives.asymmetric.x25519.X25519PrivateKey.generate()``).
2. ECDH is performed between the ephemeral private key and the
   recipient's long-term public key
   (:class:`~application.modelo.RecipientFingerprintRecord`),
   producing a 32-byte shared secret.
3. The shared secret is NEVER used directly as an AEAD key. It is run
   through :func:`~adapters.persistence.storage.crypto.derive_key`
   (HKDF-SHA256), with the HKDF ``salt`` set to the ephemeral public key
   and the ``context`` (HKDF ``info``) bound to a fixed domain-separation
   string PLUS the recipient's public key -- so a derived key can never
   be reused across a different ephemeral sender key or a different
   recipient.
4. The package bytes are AEAD-encrypted via
   :func:`~adapters.persistence.storage.crypto.encrypt_record`
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
:class:`~application.modelo.RecipientFingerprintRegistryRepository`);
the ephemeral sender private key exists only for the duration of one
call and is never persisted.

Expiry and replay defence: every envelope carries an
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
  :class:`~application.modelo.RecipientReplayGuardRepository` (a
  persisted, bucket-scoped consumed-nonce ledger) before or after calling
  :func:`decrypt_review_package_for_recipient` -- this module mints and
  carries the nonce but performs no persistence itself (this is the
  ``aeat-architecture-boundaries`` boundary: encryption and
  decryption stay pure in-memory primitives, and the CLI decrypt-side
  composition owns the ledger check).
* **Review-only mode** (``review_only=True``) asserts the sealed package
  carries no filing authority: the recipient may read and verify it, but it
  is NOT evidence that the underlying revision has been (or will be) filed
  with AEAT. :func:`decrypt_review_package_for_recipient` returns a typed
  :class:`RecipientDecryptedPackage` (bytes plus the ``review_only`` flag)
  rather than bare ``bytes``, so a downstream consumer cannot lose the flag
  and mistake a review-only handoff for a filing artefact.

Recipient's own keypair (mint-or-load, symmetric to
:func:`~application.modelo.ensure_review_package_signing_keypair`): a
recipient (the accountant running :func:`decrypt_review_package_for_recipient`
against a package sealed for them) needs their OWN X25519 private key, matching
the public key a taxpayer registered via
:class:`~application.modelo.RecipientFingerprintRegistryRepository`.
:func:`ensure_recipient_encryption_keypair` mints one on first use and persists
it -- private key included -- ONLY as ciphertext through a
:class:`~adapters.persistence.storage.SecureObjectRepository`, at
:class:`~adapters.persistence.storage.SensitivityClass` ``SECRET``
(:data:`~adapters.persistence.storage.MODELO_REVIEW_PACKAGE_RECIPIENT_ENCRYPTION_KEY_NAMESPACE`),
exactly as the Ed25519 signing keypair is minted and stored. It is never
logged, never written to a plaintext file, and never leaves this module as raw
bytes except transiently in process memory to decrypt. The exportable public
half (:func:`recipient_encryption_public_key`) is what a taxpayer registers via
the fingerprint registry -- never the private key.

See Also:
    :mod:`~application.modelo._review_package_recipient_registry`
        Where a recipient's trusted public key is registered and looked
        up before calling this module.
    :mod:`~application.modelo._review_package_recipient_replay_guard`
        The consumed-nonce ledger a caller composes around
        :func:`decrypt_review_package_for_recipient` for replay defence.
    :mod:`~application.modelo._review_package`
        Builds and integrity-verifies the review package this module
        encrypts.
    :func:`~application.modelo.ensure_review_package_signing_keypair`
        The Ed25519 signing-keypair primitive this module's
        :func:`ensure_recipient_encryption_keypair` mirrors exactly (mint-once,
        persist-as-ciphertext, idempotent-reuse), for a distinct purpose
        (encryption, never signing -- a key is never reused across
        purposes).
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey,
    X25519PublicKey,
)
from pydantic import BaseModel, Field, field_serializer, field_validator, model_validator

from ...adapters.persistence.storage import (
    MODELO_REVIEW_PACKAGE_RECIPIENT_ENCRYPTION_KEY_NAMESPACE as _NAMESPACE,
)
from ...adapters.persistence.storage import (
    DecryptionError,
)
from ...adapters.persistence.storage.crypto import EncryptedBlob, decrypt_record, derive_key, encrypt_record
from ...core import HEX_PATTERN_64 as _HEX_PATTERN_64
from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.errors import CadrumoError
from ...core.identity import BucketId, canonical_bucket_id
from ...core.time import UtcInstant
from ...core.time import now as _utc_now
from ._review_package_keypair import ensure_singleton_keypair

if TYPE_CHECKING:
    from ...adapters.persistence.storage import SecureObjectRepository

#: Wire-format version of the recipient-encryption envelope. Bumped when
#: the envelope schema changes shape.
_RECIPIENT_ENCRYPTION_ENVELOPE_VERSION = 1

#: HKDF domain-separation context. Distinct from any other HKDF context
#: string used elsewhere in the codebase (e.g. secure-object row keys,
#: DEK wrapping) so a key derived here can never collide with a key
#: derived for an unrelated purpose even if the same shared secret were
#: (incorrectly) reused.
_HKDF_CONTEXT_PREFIX = b"cadrumo.review_package.recipient_encryption.v1"

#: Byte length of the replay-detection nonce (independent of, and never
#: reused as, the AEAD nonce embedded inside ``ciphertext``).
_REPLAY_NONCE_BYTES = 32


class RecipientEncryptionError(CadrumoError):
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


class RecipientEncryptionKeyNotFoundError(RecipientEncryptionError):
    """Raised when no encryption keypair has been minted for a bucket yet.

    Callers should mint one via :func:`ensure_recipient_encryption_keypair`
    before loading it explicitly.
    """


class RecipientEncryptionKeypair(BaseModel):
    """A bucket's X25519 encryption keypair, private key included.

    This model is the PLAINTEXT in-memory shape used only transiently around
    generation, persistence, and decryption; :meth:`private_key` /
    :meth:`public_key` reconstruct live ``cryptography`` key objects from the
    stored raw hex bytes. The caller (:func:`ensure_recipient_encryption_keypair`)
    is responsible for persisting it only through
    :class:`~adapters.persistence.storage.SecureObjectRepository`, mirroring
    :class:`~application.modelo.ReviewPackageSigningKeypair` exactly --
    a distinct keypair, for a distinct purpose (encryption, never signing).
    """

    model_config = _STRICT_FROZEN

    bucket_id: BucketId
    private_key_hex: str = Field(pattern=_HEX_PATTERN_64)
    public_key_hex: str = Field(pattern=_HEX_PATTERN_64)
    created_at: UtcInstant

    def private_key(self) -> X25519PrivateKey:
        """Reconstruct the live :class:`X25519PrivateKey` from stored raw bytes."""
        return X25519PrivateKey.from_private_bytes(bytes.fromhex(self.private_key_hex))

    def public_key(self) -> X25519PublicKey:
        """Reconstruct the live :class:`X25519PublicKey` from stored raw bytes."""
        return X25519PublicKey.from_public_bytes(bytes.fromhex(self.public_key_hex))


class RecipientEncryptionPublicKey(BaseModel):
    """The exportable, non-secret half of a bucket's encryption keypair.

    Safe to hand to a taxpayer so they can register it via
    :class:`~application.modelo.RecipientFingerprintRegistryRepository`.
    Carries no secrecy requirement -- unlike :class:`RecipientEncryptionKeypair`,
    this model is fine to print, write to a plaintext file, or read aloud for
    out-of-band fingerprint verification.
    """

    model_config = _STRICT_FROZEN

    bucket_id: BucketId
    public_key_hex: str = Field(pattern=_HEX_PATTERN_64)
    created_at: UtcInstant


def _recipient_encryption_key_object_key(bucket_id: str) -> str:
    """Return the natural :class:`~adapters.persistence.storage.SecureObjectRepository` key for ``bucket_id``'s keypair.

    Matches the namespace's declared
    ``object_key_grammar="review-package-recipient-encryption-key:{bucket_id}"``.
    """
    return f"review-package-recipient-encryption-key:{canonical_bucket_id(bucket_id)}"


def _keypair_from_repository_payload(payload: bytes, *, bucket_id: str) -> RecipientEncryptionKeypair:
    """Load a keypair only when its encrypted payload agrees with its storage key.

    The natural object key binds the record to ``bucket_id``.  The encrypted
    payload repeats that identity so a foreign keypair re-keyed under this
    bucket cannot silently become this recipient's private key.  Exact rather
    than normalized equality also refuses legacy whitespace spellings: those
    would otherwise address the canonical key while preserving a second,
    ambiguous payload identity.
    """
    keypair = RecipientEncryptionKeypair.model_validate_json(payload)
    if keypair.bucket_id != bucket_id:
        raise RecipientEncryptionError(
            "stored recipient encryption keypair does not belong to the bucket it was read from",
        )
    return keypair


def ensure_recipient_encryption_keypair(
    *,
    bucket_id: str,
    repository: SecureObjectRepository,
    generated_at: datetime | None = None,
) -> RecipientEncryptionKeypair:
    """Return the bucket's X25519 encryption keypair, minting one on first use.

    Composes :func:`~application.modelo._review_package_keypair.ensure_singleton_keypair`
    for the mint-or-load-winner mechanic shared with
    :func:`~application.modelo.ensure_review_package_signing_keypair`
    (that function's Ed25519 counterpart): loads the existing keypair from
    :data:`~adapters.persistence.storage.MODELO_REVIEW_PACKAGE_RECIPIENT_ENCRYPTION_KEY_NAMESPACE`
    when present; otherwise generates a fresh keypair via
    ``X25519PrivateKey.generate()``, persists it (private key included) as
    ciphertext, and returns it. Idempotent: a second call against the same
    bucket returns the SAME keypair rather than rotating it, so a package
    sealed for the recipient's public key today still decrypts next week.

    Args:
        bucket_id: The bucket this keypair is scoped to (the recipient's own
            profile bucket, resolved the same way the signing keypair is).
        repository: The bucket's
            :class:`~adapters.persistence.storage.SecureObjectRepository`.
        generated_at: Optional override for the keypair's ``created_at``
            timestamp (tests only); defaults to the current UTC time.
    """
    normalised_bucket_id = canonical_bucket_id(bucket_id)
    object_key = _recipient_encryption_key_object_key(normalised_bucket_id)

    def _generate() -> RecipientEncryptionKeypair:
        private_key = X25519PrivateKey.generate()
        public_key = private_key.public_key()
        return RecipientEncryptionKeypair(
            bucket_id=normalised_bucket_id,
            private_key_hex=private_key.private_bytes_raw().hex(),
            public_key_hex=public_key.public_bytes_raw().hex(),
            created_at=generated_at or _utc_now(),
        )

    def _mismatch_error() -> RecipientEncryptionError:
        return RecipientEncryptionError(
            "stored recipient encryption keypair does not belong to the bucket it was read from",
        )

    return ensure_singleton_keypair(
        repository=repository,
        namespace=_NAMESPACE,
        object_key=object_key,
        model_type=RecipientEncryptionKeypair,
        generate=_generate,
        bucket_id_of=lambda keypair: keypair.bucket_id,
        created_at_of=lambda keypair: keypair.created_at,
        expected_bucket_id=normalised_bucket_id,
        mismatch_error=_mismatch_error,
        write_provenance="application.modelo.review_package_recipient_encryption.ensure_keypair",
    )


def load_recipient_encryption_keypair(
    *,
    bucket_id: str,
    repository: SecureObjectRepository,
) -> RecipientEncryptionKeypair:
    """Load the bucket's existing X25519 encryption keypair.

    Args:
        bucket_id: The bucket this keypair is scoped to.
        repository: The bucket's
            :class:`~adapters.persistence.storage.SecureObjectRepository`.

    Raises:
        RecipientEncryptionKeyNotFoundError: If no keypair has been minted yet
            for ``bucket_id``. Call :func:`ensure_recipient_encryption_keypair`
            first.
    """
    normalised_bucket_id = canonical_bucket_id(bucket_id)
    object_key = _recipient_encryption_key_object_key(normalised_bucket_id)
    record = repository.load(
        _NAMESPACE.namespace,
        object_key,
        expected_class=_NAMESPACE.sensitivity,
        max_supported_version=_NAMESPACE.schema_version,
    )
    if record is None:
        raise RecipientEncryptionKeyNotFoundError(
            translated_message="application.modelo.errors.recipient_encryption_key_not_found",
            context={"bucket_id": normalised_bucket_id},
        )
    return _keypair_from_repository_payload(record.payload, bucket_id=normalised_bucket_id)


def recipient_encryption_public_key(
    keypair: RecipientEncryptionKeypair,
) -> RecipientEncryptionPublicKey:
    """Project the exportable public half out of a full keypair.

    The projection never touches ``private_key_hex``; the returned model is
    safe to hand to a taxpayer to register via the fingerprint registry.
    """
    return RecipientEncryptionPublicKey(
        bucket_id=keypair.bucket_id,
        public_key_hex=keypair.public_key_hex,
        created_at=keypair.created_at,
    )


class RecipientEncryptedPackage(BaseModel):
    """Wire envelope for a review package encrypted for one recipient.

    ``ephemeral_public_key_hex`` and ``recipient_public_key_hex`` are
    both raw 32-byte X25519 public keys, hex-encoded. ``ciphertext``
    is the AEAD wire form (``nonce || ciphertext_with_tag``) produced by
    :func:`~adapters.persistence.storage.crypto.encrypt_record`, held
    as raw ``bytes`` on the Python object (matching every in-process caller
    in this module) but hex-encoded on the JSON boundary
    (:meth:`model_dump_json` / ``model_dump(mode="json")``) -- pydantic's
    default JSON encoding for ``bytes`` assumes valid UTF-8, which arbitrary
    AEAD ciphertext is not, so a bare ``bytes`` field would raise
    ``PydanticSerializationError`` the first time a caller (e.g. the CLI
    ``encrypt-for-recipient`` verb) writes the envelope to disk as JSON.
    :meth:`model_validate_json` accepts the hex form it produced; the
    plain-Python constructor still accepts raw ``bytes`` directly.

    ``envelope_nonce_hex`` is a replay-detection token, independent of the
    AEAD nonce embedded in ``ciphertext``: a caller checks it against
    :class:`~application.modelo.RecipientReplayGuardRepository` to
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
    issued_at: UtcInstant
    valid_until: UtcInstant | None = Field(default=None)
    review_only: bool = Field(default=False)

    @field_validator("ciphertext", mode="before")
    @classmethod
    def _ciphertext_accepts_hex_or_raw_bytes(cls, value: object) -> object:
        if isinstance(value, str):
            return bytes.fromhex(value)
        return value

    @field_serializer("ciphertext", when_used="json")
    def _ciphertext_as_hex_for_json(self, value: bytes) -> str:
        return value.hex()

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
    return b"cadrumo.review_package.recipient:" + recipient_public_key_hex.encode("ascii")


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
            :class:`~application.modelo.RecipientFingerprintRecord`).
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
    cryptographic failure may catch this subclass specifically, though
    failures are deliberately undifferentiated: the rendered message is
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
    (``aeat-architecture-boundaries``). A caller that needs
    replay defence composes
    :class:`~application.modelo.RecipientReplayGuardRepository` around
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
    "RecipientEncryptionKeyNotFoundError",
    "RecipientEncryptionKeypair",
    "RecipientEncryptionPublicKey",
    "RecipientPackageExpiredError",
    "decrypt_review_package_for_recipient",
    "encrypt_review_package_for_recipient",
    "ensure_recipient_encryption_keypair",
    "load_recipient_encryption_keypair",
    "recipient_encryption_public_key",
]
