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
write and read non-sensitive envelope JSON via
:func:`~cadrumo.core.atomic_write.atomic_write_text` (standard tier).

The substrate refuses any payload whose ``schema_version`` differs from
the consumer's expected version, or which fails classification validation.
Sensitive repositories use
:class:`~adapters.persistence.storage.SecureBoundRepository`, which stores
the envelope payload shape in encrypted SQL secure objects rather than files.
"""

from __future__ import annotations

import base64
import binascii
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import cast

from pydantic import BaseModel, Field, ValidationError, field_validator

from .....core.atomic_write import atomic_write_text
from .....core.classification.policies import SensitivityClass
from .....core.errors.hierarchy import CoreValidationError
from .....core.external_constants import UTF_8_ENCODING as _UTF_8_ENCODING
from .....core.logging import get_logger
from .....core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from .....core.time.utc import validate_utc_aware
from ..crypto.aead import EncryptedBlob
from ..errors import (
    ClassificationError,
    DecryptionError,
    EnvelopeVersionError,
)
from ..errors import (
    storage_validation_error as _storage_validation_error,
)
from ..schema_lineage import inner_envelope_classification_is_expected

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
        return parameterized_envelope_type(payload_cls, envelope_cls=cls)


def parameterized_envelope_type[PayloadT: BaseModel](
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


__all__ = [
    "EncryptionMetadata",
    "Envelope",
    "load_envelope",
    "save_envelope",
]
