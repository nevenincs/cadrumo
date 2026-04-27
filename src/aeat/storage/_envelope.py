"""Schema-version envelope for file-backed persistence.

The envelope is the single contract every file-backed persistence
consumer adheres to. It pins:

- the on-disk schema version (so per-domain migrators can roll forward
  legacy payloads);
- the timestamp of the write (timezone-aware datetime);
- the sensitivity classification (so the substrate can refuse to load
  a record if a consumer accidentally bypasses its repository);
- the payload itself (typed strict pydantic v2 model);
- optional encryption metadata (when the payload is at-rest ciphertext).

The :func:`save_envelope` and :func:`load_envelope` helpers atomically
write and read the envelope JSON via the project's standard
``tempfile.NamedTemporaryFile + os.replace`` pattern.

Per-domain migrators are not implemented at the substrate level — the
:class:`EnvelopeMigrator` protocol is the extension point consumers
register their own migrators against. The substrate simply refuses to
load a payload whose ``schema_version`` exceeds the consumer's
expected version, or which fails classification validation.
"""

from __future__ import annotations

import base64
import os
import tempfile
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..logging import get_logger
from ._classification import SensitivityClass
from ._crypto import EncryptedBlob
from .errors import (
    ClassificationError,
    EnvelopeVersionError,
)

_log = get_logger(__name__)
_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")


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
        associated_data_b64: Base64-encoded AAD bytes (may be empty).
    """

    model_config = _STRICT_FROZEN

    algorithm: AeadAlgorithm = Field(default=AeadAlgorithm.AES_256_GCM_V1)
    nonce_b64: str
    ciphertext_b64: str
    associated_data_b64: str = Field(default="")

    @classmethod
    def from_blob(cls, blob: EncryptedBlob, *, associated_data: bytes = b"") -> EncryptionMetadata:
        """Build encryption metadata from an :class:`EncryptedBlob`."""
        return cls(
            nonce_b64=base64.b64encode(blob.nonce).decode("ascii"),
            ciphertext_b64=base64.b64encode(blob.ciphertext).decode("ascii"),
            associated_data_b64=base64.b64encode(associated_data).decode("ascii"),
        )

    def to_blob(self) -> EncryptedBlob:
        """Reconstruct the :class:`EncryptedBlob` from encoded fields."""
        return EncryptedBlob(
            nonce=base64.b64decode(self.nonce_b64.encode("ascii"), validate=True),
            ciphertext=base64.b64decode(self.ciphertext_b64.encode("ascii"), validate=True),
        )

    def associated_data(self) -> bytes:
        """Decode the associated-data bytes."""
        return base64.b64decode(self.associated_data_b64.encode("ascii"), validate=True)


class Envelope[PayloadT: BaseModel](BaseModel):
    """Frozen pydantic v2 envelope wrapping a typed file-backed payload.

    Attributes:
        schema_version: Integer version that consumers compare to their
            expected version. Older versions are routed through the
            migrator chain; newer versions are refused.
        written_at: Timezone-aware datetime captured at write time.
        classification: The :class:`SensitivityClass` declared by the
            writer. Mismatches at load time raise
            :class:`ClassificationError`.
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
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("written_at must be timezone-aware")
        return value


@runtime_checkable
class EnvelopeMigrator[PayloadT: BaseModel](Protocol):
    """Pluggable forward-migrator for one envelope schema version transition."""

    source_version: int
    target_version: int

    def migrate(self, envelope: Envelope[PayloadT]) -> Envelope[PayloadT]:
        """Return the migrated envelope advanced to ``target_version``."""
        ...


def save_envelope(envelope: Envelope[Any], path: Path) -> None:
    """Atomically persist ``envelope`` as JSON to ``path``.

    Args:
        envelope: The envelope to write.
        path: Destination file. Parent directory is created if absent.
    """
    target = path.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = envelope.model_dump_json()
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=target.parent,
            prefix=f"{target.stem}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            tmp_path = Path(handle.name)
            handle.write(payload)
        os.replace(tmp_path, target)
    except OSError:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)
        raise


def load_envelope[PayloadT: BaseModel](
    path: Path,
    envelope_type: type[Envelope[PayloadT]],
    *,
    expected_class: SensitivityClass,
    max_supported_version: int,
    migrators: tuple[EnvelopeMigrator[PayloadT], ...] = (),
) -> Envelope[PayloadT]:
    """Load and validate an envelope from disk.

    Args:
        path: Source file (must exist).
        envelope_type: The parameterised envelope class
            (e.g. ``Envelope[MyPayloadV1]``). Pydantic uses this to
            validate the JSON against the typed payload.
        expected_class: The :class:`SensitivityClass` the consumer
            expects. Mismatch raises :class:`ClassificationError`.
        max_supported_version: The highest ``schema_version`` the
            consumer can handle. Newer versions raise
            :class:`EnvelopeVersionError`.
        migrators: Optional ordered tuple of forward migrators applied
            when the on-disk version is below ``max_supported_version``.
            Migrators are applied in their declared order; gaps raise
            :class:`EnvelopeVersionError`.

    Returns:
        The validated envelope at the consumer's expected version.

    Raises:
        ClassificationError: If the on-disk classification does not
            match ``expected_class``.
        EnvelopeVersionError: If the on-disk version exceeds
            ``max_supported_version`` or no migrator chain advances it
            to ``max_supported_version``.
    """
    raw = path.read_text(encoding="utf-8")
    envelope = envelope_type.model_validate_json(raw)
    if envelope.classification != expected_class:
        raise ClassificationError(
            f"envelope at {path} has classification {envelope.classification}; consumer expected {expected_class}",
        )
    if envelope.schema_version > max_supported_version:
        raise EnvelopeVersionError(
            f"envelope at {path} is at version {envelope.schema_version}; "
            f"consumer supports up to {max_supported_version}",
        )
    if envelope.schema_version < max_supported_version:
        envelope = _apply_migrators(envelope, max_supported_version, migrators)
    return envelope


def _apply_migrators[PayloadT: BaseModel](
    envelope: Envelope[PayloadT],
    target_version: int,
    migrators: tuple[EnvelopeMigrator[PayloadT], ...],
) -> Envelope[PayloadT]:
    """Apply the migrator chain in declared order until ``target_version``.

    Per-step debug logging records the attempted chain (vs-M-6); a
    monotonic-version assertion (sec-M-5) raises
    :class:`EnvelopeVersionError` if a migrator returns a non-monotonic
    schema version, defending against migrator chains that would
    otherwise be silent downgrade attacks.
    """
    current = envelope
    attempted: list[str] = []
    for migrator in migrators:
        if current.schema_version == target_version:
            break
        if migrator.source_version != current.schema_version:
            attempted.append(
                f"skip {type(migrator).__name__} ({migrator.source_version}->{migrator.target_version})",
            )
            continue
        previous_version = current.schema_version
        current = migrator.migrate(current)
        attempted.append(
            f"apply {type(migrator).__name__} ({previous_version}->{current.schema_version})",
        )
        if current.schema_version <= previous_version:
            raise EnvelopeVersionError(
                f"migrator {type(migrator).__name__} returned non-monotonic "
                f"schema_version: {previous_version} -> {current.schema_version}; "
                f"chain so far: {attempted}",
            )
        _log.debug(
            "envelope migrator %s advanced version %s -> %s",
            type(migrator).__name__,
            previous_version,
            current.schema_version,
        )
    if current.schema_version != target_version:
        raise EnvelopeVersionError(
            f"envelope is at version {current.schema_version}; no migrator chain "
            f"advances it to {target_version}; attempted chain: {attempted}",
        )
    return current


__all__ = [
    "EncryptionMetadata",
    "Envelope",
    "EnvelopeMigrator",
    "load_envelope",
    "save_envelope",
]
