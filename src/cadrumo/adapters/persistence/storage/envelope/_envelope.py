"""Schema-version envelope for file-backed persistence.

The envelope is the single contract every file-backed persistence
consumer adheres to. It pins:

- the on-disk schema version, which must match the consumer's current
  schema exactly;
- the timestamp of the write (timezone-aware datetime);
- the sensitivity classification (so the substrate can refuse to load
  a record if a consumer accidentally bypasses its repository);
- the payload itself (typed strict pydantic v2 model);
- optional encryption metadata (when the payload is at-rest ciphertext).

The :func:`~adapters.persistence.storage.save_envelope` and
:func:`~adapters.persistence.storage.load_envelope` helpers atomically
write and read the envelope JSON via
:func:`~cadrumo.core.atomic_write.atomic_write_text` (standard tier).
Encrypted envelopes
require an explicit
:class:`~adapters.persistence.storage.MasterKeyProvider` and HKDF context;
the helpers derive a per-consumer key via HKDF-SHA256 and do not resolve an
ambient provider themselves.

The substrate refuses any payload whose ``schema_version`` differs from
the consumer's expected version, or which fails classification validation.
Migrated sensitive repositories should use
:class:`~adapters.persistence.storage.SecureBoundRepository`, which stores
the same envelope payload shape in encrypted SQL secure objects rather than
plain files.
"""

from __future__ import annotations

import base64
import binascii
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Final, cast

from pydantic import BaseModel, Field, ValidationError, field_validator

from .....core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from .....core.atomic_write import atomic_write_text
from .....core.classification import SensitivityClass
from .....core.errors import CoreValidationError
from .....core.external_constants import UTF_8_ENCODING as _UTF_8_ENCODING
from .....core.logging import get_logger
from .....core.time import validate_utc_aware
from .._schema_lineage import inner_envelope_classification_is_expected
from ..crypto.aead import EncryptedBlob, decrypt_record, derive_key, encrypt_record
from ..errors import (
    ClassificationError,
    DecryptionError,
    EnvelopeVersionError,
    StorageValidationError,
)
from ..errors import (
    storage_validation_error as _storage_validation_error,
)
from ..master_key import MasterKeyProvider

_log = get_logger(__name__)


def _read_envelope_text(path: Path) -> str:
    try:
        return path.read_text(encoding=_UTF_8_ENCODING)
    except (OSError, UnicodeDecodeError) as exc:
        _log.debug("envelope read failed error_type=%s", type(exc).__name__)
        raise _storage_validation_error("envelope cannot be read") from exc


def _parse_model_json[T: BaseModel](model_type: type[T], raw: str, *, label: str) -> T:
    try:
        return model_type.model_validate_json(raw)
    except (ValidationError, ValueError) as exc:
        _log.debug("envelope JSON validation failed label=%s error_type=%s", label, type(exc).__name__)
        raise _storage_validation_error(f"{label} envelope JSON is not valid") from exc


class AeadAlgorithm(StrEnum):
    """Closed catalogue of AEAD identifiers recognised by the substrate.

    Members:
        AES_256_GCM_V1: AES-256 Galois Counter Mode, version 1 wire
            format (12-byte nonce, 16-byte tag). The only algorithm
            shipping today.
    """

    AES_256_GCM_V1 = "aes-256-gcm-v1"


class EncryptionMetadata(BaseModel):
    """Encryption envelope describing how the payload was encrypted.

    Attributes:
        algorithm: Stable identifier for the AEAD primitive used.
            Today only ``aes-256-gcm-v1`` is defined; future primitives
            register their own identifier.
        nonce_b64: Base64-encoded 12-byte nonce.
        ciphertext_b64: Base64-encoded ``ciphertext_with_tag``.
        associated_data_b64: Base64-encoded AAD bytes. The field is
            required so persisted metadata distinguishes an explicitly
            empty AAD from malformed metadata where the AAD
            member is missing.
    """

    model_config = _STRICT_FROZEN

    algorithm: AeadAlgorithm = Field(default=AeadAlgorithm.AES_256_GCM_V1)
    nonce_b64: str
    ciphertext_b64: str
    associated_data_b64: str

    @classmethod
    def from_blob(cls, blob: EncryptedBlob, *, associated_data: bytes = b"") -> EncryptionMetadata:
        """Build metadata from an encrypted blob.

        Returns:
            :class:`~adapters.persistence.storage.EncryptionMetadata`
            derived from an
            :class:`~adapters.persistence.storage.EncryptedBlob`.
        """
        return cls(
            nonce_b64=base64.b64encode(blob.nonce).decode("ascii"),
            ciphertext_b64=base64.b64encode(blob.ciphertext).decode("ascii"),
            associated_data_b64=base64.b64encode(associated_data).decode("ascii"),
        )

    def to_blob(self) -> EncryptedBlob:
        """Reconstruct the :class:`~adapters.persistence.storage.EncryptedBlob` from encoded fields."""
        try:
            return EncryptedBlob(
                nonce=base64.b64decode(self.nonce_b64.encode("ascii"), validate=True),
                ciphertext=base64.b64decode(self.ciphertext_b64.encode("ascii"), validate=True),
            )
        except (binascii.Error, UnicodeEncodeError, ValidationError, ValueError) as exc:
            raise DecryptionError("cipher envelope encryption metadata is not valid") from exc

    def associated_data(self) -> bytes:
        """Decode the associated-data bytes."""
        try:
            return base64.b64decode(self.associated_data_b64.encode("ascii"), validate=True)
        except (binascii.Error, UnicodeEncodeError, ValueError) as exc:
            raise DecryptionError("cipher envelope associated data is not valid") from exc


class Envelope[PayloadT: BaseModel](BaseModel):
    """Frozen pydantic v2 envelope wrapping a typed file-backed payload.

    Attributes:
        schema_version: Integer version that consumers compare to their
            expected version. Older and newer versions are refused.
        written_at: Timezone-aware datetime captured at write time.
        classification: The
            :class:`~adapters.persistence.storage.SensitivityClass` declared by the
            writer. Mismatches at load time raise
            :class:`~adapters.persistence.storage.ClassificationError`.
        payload: The typed payload. Plaintext is stored when
            ``encryption`` is ``None``; ciphertext lives in
            ``encryption.ciphertext_b64`` when present, and ``payload``
            is then a placeholder consumer-typed value.
        encryption: Optional encryption metadata. ``None`` for
            plaintext envelopes.
    """

    model_config = _STRICT_FROZEN

    schema_version: int = Field(ge=1)
    written_at: datetime
    classification: SensitivityClass
    payload: PayloadT
    encryption: EncryptionMetadata | None = None

    @field_validator("written_at")
    @classmethod
    def _require_aware(cls, value: datetime) -> datetime:
        try:
            return validate_utc_aware(value)
        except CoreValidationError as exc:
            raise _storage_validation_error(str(exc)) from exc

    @classmethod
    def for_payload_type(cls, payload_cls: type[PayloadT]) -> type[Envelope[PayloadT]]:
        """Return the :class:`~adapters.persistence.storage.Envelope` parameterised for ``payload_cls``.

        This typed factory avoids a bare ``cast(Any, Envelope).__class_getitem__(...)``
        at call sites. The returned class is the concrete generic alias Pydantic
        needs at the JSON validation boundary. The cast to ``type[Envelope[PayloadT]]``
        is safe because ``__class_getitem__`` on a PEP-695 generic model returns
        exactly the parameterised subtype; Pydantic registers it as a model class
        whose ``payload`` field is constrained to ``payload_cls``.
        """
        # CAST-RATIONALE-GENERIC-CLASSGETITEM: __class_getitem__ on a pydantic
        # generic model returns type[Envelope[PayloadT]] at runtime; the stub
        # annotates it as type[Self], so make the runtime contract explicit.
        return _parameterized_envelope_type(payload_cls, envelope_cls=cls)


def _parameterized_envelope_type[PayloadT: BaseModel](
    payload_cls: type[PayloadT],
    *,
    envelope_cls: type[Envelope[PayloadT]] = Envelope,
) -> type[Envelope[PayloadT]]:
    """Return the runtime Pydantic generic class for one payload type.

    Keeping the dynamic ``__class_getitem__`` operation behind a free generic
    function gives callers a type-inferable boundary; Ty cannot propagate the
    payload variable through the generic model's classmethod receiver.
    """
    return cast("type[Envelope[PayloadT]]", envelope_cls.__class_getitem__(payload_cls))


def save_envelope[T: BaseModel](envelope: Envelope[T], path: Path) -> None:
    """Atomically persist ``envelope`` as JSON to ``path``.

    Args:
        envelope: The :class:`~adapters.persistence.storage.Envelope` to write.
        path: Destination file. Parent directory is created if absent.

    Raises:
        StorageValidationError: When the temporary file or atomic replace operation fails.
    """
    target = path.resolve()
    payload = envelope.model_dump_json()
    try:
        atomic_write_text(target, payload, encoding=_UTF_8_ENCODING)
    except OSError as exc:
        _log.error("envelope atomic write failed error_type=%s", type(exc).__name__)
        raise _storage_validation_error("envelope cannot be written") from exc


def load_envelope[PayloadT: BaseModel](
    path: Path,
    envelope_type: type[Envelope[PayloadT]],
    *,
    expected_class: SensitivityClass,
    max_supported_version: int,
) -> Envelope[PayloadT]:
    """Load and validate an envelope from disk.

    Args:
        path: Source file (must exist).
        envelope_type: The parameterised envelope class
            (e.g. ``Envelope[MyPayloadV1]``). Pydantic uses this to
            validate the JSON against the typed payload.
        expected_class: The
            :class:`~adapters.persistence.storage.SensitivityClass` the consumer
            expects. Mismatch raises
            :class:`~adapters.persistence.storage.ClassificationError`.
        max_supported_version: The current ``schema_version`` the
            consumer expects. Any different version raises
            :class:`~adapters.persistence.storage.EnvelopeVersionError`.

    Returns:
        The validated :class:`~adapters.persistence.storage.Envelope` at the consumer's expected version.

    Raises:
        ClassificationError: If the on-disk classification does not
            match ``expected_class``.
        EnvelopeVersionError: If the on-disk version differs from
            ``max_supported_version``.
    """
    raw = _read_envelope_text(path)
    envelope = _parse_model_json(envelope_type, raw, label="plaintext")
    if not inner_envelope_classification_is_expected(envelope.classification, expected_class):
        raise ClassificationError(
            f"envelope classification {envelope.classification}; consumer expected {expected_class}",
        )
    if envelope.schema_version != max_supported_version:
        raise EnvelopeVersionError(
            f"envelope is at version {envelope.schema_version}; consumer expects {max_supported_version}",
        )
    return envelope


_HKDF_CONTEXT_ENVELOPE_PAYLOAD = b"cadrumo.envelope.payload.v1"
_CIPHER_ENVELOPE_AAD_PREFIX = b"cadrumo.envelope.cipher.v1::"

CIPHER_ENVELOPE_SCHEMA_VERSION: Final[int] = 1
"""The one outer cipher-envelope wire version this build reads and writes.

The outer version was parsed into a model field and then consulted by nobody:
:func:`load_encrypted_envelope` gated only the *inner* envelope's version, so a
cipher envelope claiming any version at all was accepted and decrypted. A
version marker that no reader compares against anything is not a
compatibility mechanism, it is a comment -- and the first real format change
would have been read by a build that had no idea it could not understand the
bytes.

One declared value, checked before the master key is consulted, is what makes
the field load-bearing. That check is also why the version is deliberately NOT
bound into the AEAD associated data: with exactly one accepted value gated
ahead of key use, rewriting the field can only produce a refusal, so it steers
nothing an attacker could exploit. Should a second version ever ship, the
version becomes a real routing input and must be bound then.
"""


class CipherEnvelope(BaseModel):
    """On-disk wire form for ciphertext-at-rest envelopes.

    A :class:`~adapters.persistence.storage.CipherEnvelope` is
    structurally distinct from
    :class:`~adapters.persistence.storage.Envelope` — it carries no typed
    payload field, only the encryption metadata and the same classification
    gate. The plaintext :class:`~adapters.persistence.storage.Envelope`
    (with payload) is JSON-serialised, encrypted with AES-256-GCM, and the
    ciphertext lives inside ``encryption.ciphertext_b64``.

    Attributes:
        cipher_schema_version: Wire-format version of the cipher
            envelope itself (independent of the inner plaintext
            envelope's :attr:`Envelope.schema_version`). Required and
            stamped explicitly by the writer, then gated against
            :data:`CIPHER_ENVELOPE_SCHEMA_VERSION` on load, before the
            master key is consulted. It carries no default: a default
            equal to the current version makes a stored document that
            omits the key hydrate AS current, which the equality gate
            then passes -- enforcement that reads as present while the
            one payload it most needs to catch walks through it.
        written_at: Timezone-aware datetime captured at write time.
        classification: The
            :class:`~adapters.persistence.storage.SensitivityClass` of the inner
            payload. Replicated at the cipher layer so a load can
            reject foreign-class ciphertext before the master key is
            consulted (defense in depth).
        encryption: Required encryption metadata.
    """

    model_config = _STRICT_FROZEN

    cipher_schema_version: int = Field(ge=1)
    written_at: datetime
    classification: SensitivityClass
    encryption: EncryptionMetadata

    @field_validator("written_at")
    @classmethod
    def _require_aware(cls, value: datetime) -> datetime:
        try:
            return validate_utc_aware(value)
        except CoreValidationError as exc:
            raise _storage_validation_error(str(exc)) from exc


def build_aad(classification: SensitivityClass, hkdf_context: bytes) -> bytes:
    """Build the AEAD associated-data binding for a cipher envelope.

    The AAD authenticates both the :class:`SensitivityClass` classification
    and the consumer's HKDF context, so an attacker cannot relabel
    ciphertext as a different sensitivity class or graft a payload from
    one consumer onto another.
    """
    return _CIPHER_ENVELOPE_AAD_PREFIX + classification.value.encode("ascii") + b"::" + hkdf_context


def derive_envelope_key(
    *,
    master_key: bytes,
    hkdf_context: bytes,
) -> bytes:
    """Derive a per-consumer 32-byte key from the master key via HKDF-SHA256."""
    return derive_key(
        key_material=master_key,
        salt=_HKDF_CONTEXT_ENVELOPE_PAYLOAD,
        context=hkdf_context,
    )


def save_encrypted_envelope[T: BaseModel](
    envelope: Envelope[T],
    path: Path,
    *,
    master_key_provider: MasterKeyProvider,
    hkdf_context: bytes,
) -> None:
    """Atomically persist ``envelope`` as an AES-256-GCM ciphertext on disk.

    The plaintext :class:`~adapters.persistence.storage.Envelope` is
    JSON-serialised, encrypted with AES-256-GCM under a per-consumer key
    derived from the master key via HKDF-SHA256, and written to ``path`` as a
    :class:`~adapters.persistence.storage.CipherEnvelope` wire form. The
    classification and HKDF context are bound to the ciphertext via AAD so an
    attacker cannot relabel or cross-consumer-graft.

    The caller supplies ``master_key_provider`` explicitly. Tests can
    pass :class:`~cadrumo.tests.master_key.EphemeralMasterKeyProvider`;
    production callers pass the provider selected by the custody flow.
    This helper does not resolve settings, active sessions, or default
    key providers on its own.

    Args:
        envelope: The plaintext envelope to encrypt and persist.
        path: Destination file. Parent directory is created if absent.
        master_key_provider:
            :class:`~adapters.persistence.storage.MasterKeyProvider`
            supplying the master key used to derive the per-consumer encryption
            key via HKDF-SHA256.
        hkdf_context: Per-consumer context bytes (e.g.
            ``b"cadrumo.domain.transactions.v1"``). Different
            consumers MUST use distinct contexts so cross-consumer
            ciphertext substitution fails.

    Raises:
        StorageValidationError: When the temporary file or atomic replace operation fails.
    """
    target = path.resolve()
    plaintext = envelope.model_dump_json().encode(_UTF_8_ENCODING)
    aad = build_aad(envelope.classification, hkdf_context)
    derived_key = derive_envelope_key(
        master_key=master_key_provider.get_master_key(),
        hkdf_context=hkdf_context,
    )
    blob = encrypt_record(plaintext, key=derived_key, associated_data=aad)
    cipher_envelope = CipherEnvelope(
        cipher_schema_version=CIPHER_ENVELOPE_SCHEMA_VERSION,
        written_at=envelope.written_at,
        classification=envelope.classification,
        encryption=EncryptionMetadata.from_blob(blob, associated_data=aad),
    )
    serialised = cipher_envelope.model_dump_json()
    try:
        atomic_write_text(target, serialised, encoding=_UTF_8_ENCODING)
    except OSError as exc:
        _log.error("envelope encrypted atomic write failed error_type=%s", type(exc).__name__)
        raise _storage_validation_error("encrypted envelope cannot be written") from exc


def load_encrypted_envelope[PayloadT: BaseModel](
    path: Path,
    envelope_type: type[Envelope[PayloadT]],
    *,
    expected_class: SensitivityClass,
    master_key_provider: MasterKeyProvider,
    hkdf_context: bytes,
    max_supported_version: int,
) -> Envelope[PayloadT]:
    """Load and decrypt an at-rest-ciphertext envelope.

    The on-disk shape MUST be a
    :class:`~adapters.persistence.storage.CipherEnvelope`. The
    classification gate is enforced *before* the master key is
    consulted — a foreign-class ciphertext is rejected without any
    crypto attempt (defense in depth). After decryption, the inner
    plaintext is parsed back into the typed
    :class:`~adapters.persistence.storage.Envelope`, classification-checked
    again, and version-checked.

    Args:
        path: Source file (must exist).
        envelope_type: The parameterised envelope class.
        expected_class: The
            :class:`~adapters.persistence.storage.SensitivityClass` the consumer
            expects. Mismatch raises
            :class:`~adapters.persistence.storage.ClassificationError`
            before any crypto attempt.
        master_key_provider:
            :class:`~adapters.persistence.storage.MasterKeyProvider`
            supplying the master key used to derive the per-consumer decryption
            key via HKDF-SHA256.
        hkdf_context: Per-consumer context bytes; MUST match the
            value supplied at save time.
        max_supported_version: Current inner-envelope schema version
            the consumer expects.

    Returns:
        The decrypted and version-checked inner
        :class:`~adapters.persistence.storage.Envelope`.

    Raises:
        ClassificationError: If the cipher envelope's class differs
            from ``expected_class``, or if the inner plaintext envelope's
            class drifts from the cipher layer (which would indicate
            tampering since the AAD binds them).
        DecryptionError: If the AEAD tag fails to verify.
        EnvelopeVersionError: If the inner plaintext envelope's
            schema version differs from ``max_supported_version``.
    """
    raw = _read_envelope_text(path)
    cipher_envelope = _parse_model_json(CipherEnvelope, raw, label="cipher")
    if not inner_envelope_classification_is_expected(cipher_envelope.classification, expected_class):
        raise ClassificationError(
            f"cipher envelope classification {cipher_envelope.classification}; consumer expected {expected_class}",
        )
    # Beside the classification gate, and for the same reason: an outer-format
    # version this build cannot interpret is refused before the master key is
    # consulted, rather than being parsed and then ignored while the payload is
    # decrypted anyway.
    if cipher_envelope.cipher_schema_version != CIPHER_ENVELOPE_SCHEMA_VERSION:
        raise EnvelopeVersionError(
            f"cipher envelope is at version {cipher_envelope.cipher_schema_version}; "
            f"consumer expects {CIPHER_ENVELOPE_SCHEMA_VERSION}",
        )
    blob = cipher_envelope.encryption.to_blob()
    aad = build_aad(cipher_envelope.classification, hkdf_context)
    if cipher_envelope.encryption.associated_data() != aad:
        raise DecryptionError(
            "cipher envelope AAD mismatch (classification or HKDF-context drift)",
        )
    derived_key = derive_envelope_key(
        master_key=master_key_provider.get_master_key(),
        hkdf_context=hkdf_context,
    )
    plaintext = decrypt_record(blob, key=derived_key, associated_data=aad)
    try:
        inner = envelope_type.model_validate_json(plaintext.decode(_UTF_8_ENCODING))
    except (UnicodeDecodeError, ValidationError, ValueError) as exc:
        raise DecryptionError("inner envelope plaintext is not valid JSON") from exc
    if not inner_envelope_classification_is_expected(inner.classification, expected_class):
        raise ClassificationError(
            f"inner envelope drifted to {inner.classification}; consumer expected {expected_class}",
        )
    if inner.schema_version != max_supported_version:
        raise EnvelopeVersionError(
            f"inner envelope is at version {inner.schema_version}; consumer expects {max_supported_version}",
        )
    return inner


def reencrypt_envelope_file[PayloadT: BaseModel](
    path: Path,
    envelope_type: type[Envelope[PayloadT]],
    *,
    expected_class: SensitivityClass,
    master_key_provider: MasterKeyProvider,
    hkdf_context: bytes,
    max_supported_version: int,
) -> bool:
    """Re-encrypt a single plaintext envelope file in place.

    Read once: if ``path`` is already a
    :class:`~adapters.persistence.storage.CipherEnvelope`, return
    ``False`` (already ciphertext, nothing to do). Otherwise parse as
    a plaintext :class:`~adapters.persistence.storage.Envelope` and
    re-write through
    :func:`~adapters.persistence.storage.save_encrypted_envelope`.

    Returns ``True`` iff the file was re-encrypted, ``False`` if the
    file was already ciphertext or did not exist. The atomic-replace
    pattern from
    :func:`~adapters.persistence.storage.save_encrypted_envelope` governs
    the on-disk rewrite: a crash mid-rewrite leaves either the plaintext OR the
    ciphertext on disk, never a torn write.

    Repository load paths are strict ciphertext-only; this function
    is the only sanctioned path that touches plaintext envelopes.

    Args:
        path: Target file to re-encrypt in place.
        envelope_type: The parameterised envelope class.
        expected_class: The
            :class:`~adapters.persistence.storage.SensitivityClass` the consumer
            expects.
        master_key_provider:
            :class:`~adapters.persistence.storage.MasterKeyProvider`
            supplying the master key used to derive the per-consumer encryption
            key via HKDF-SHA256.
        hkdf_context: Per-consumer context bytes; MUST match those used
            for subsequent load calls.
        max_supported_version: Current inner-envelope schema version
            the consumer expects.
    """
    if not path.exists():
        return False
    try:
        raw = _read_envelope_text(path)
    except StorageValidationError as exc:
        if isinstance(exc.__cause__, FileNotFoundError):
            _log.debug("envelope reencrypt skipped because source file disappeared")
            return False
        raise
    # If the file already round-trips as a CipherEnvelope, it is
    # already ciphertext-at-rest; nothing to do.
    try:
        CipherEnvelope.model_validate_json(raw)
    except (ValidationError, ValueError) as exc:
        _log.debug("envelope reencrypt source is not cipher JSON error_type=%s", type(exc).__name__)
        # Any parse failure (bad JSON, schema mismatch) means "not yet ciphertext".
    else:
        return False
    plaintext_envelope = _parse_model_json(envelope_type, raw, label="plaintext")
    if not inner_envelope_classification_is_expected(plaintext_envelope.classification, expected_class):
        raise ClassificationError(
            f"plaintext envelope classification {plaintext_envelope.classification}; "
            f"consumer expected {expected_class}",
        )
    if plaintext_envelope.schema_version != max_supported_version:
        raise EnvelopeVersionError(
            f"plaintext envelope is at version {plaintext_envelope.schema_version}; "
            f"consumer expects {max_supported_version}",
        )
    save_encrypted_envelope(
        plaintext_envelope,
        path,
        master_key_provider=master_key_provider,
        hkdf_context=hkdf_context,
    )
    return True


__all__ = [
    "CIPHER_ENVELOPE_SCHEMA_VERSION",
    "CipherEnvelope",
    "EncryptionMetadata",
    "Envelope",
    "build_aad",
    "derive_envelope_key",
    "load_encrypted_envelope",
    "load_envelope",
    "reencrypt_envelope_file",
    "save_encrypted_envelope",
    "save_envelope",
]
