"""Master-key wrapping under a recovery-key-derived KEK.

This module wraps a single process-wide master key under an HKDF-SHA256
KEK seeded by a :class:`~adapters.persistence.storage.RecoveryKey`. It
belongs to the shared-master custody surface, which per-profile password
custody supersedes: a profile's own recovery envelope wraps that
profile's DEK under its own supervised Argon2id parameters and does not
route through here.

No caller in the tree currently invokes this half. It is not reachable
from a live unwrap path, and no code path writes ``master.recovery.key``,
so it guards no material this build can have produced. It stays with the
shared-master surface and follows it whenever that surface is retired.

The mnemonic codec that mints a recovery key is deliberately NOT here.
It is a pure codec over high-entropy bytes, bound to no custody
architecture, and per-profile recovery adopts it, so it lives one level
up at :mod:`adapters.persistence.storage._recovery_key` where it survives
this package's retirement rather than being swept away with the wrapping
half it once shared a file with.

This module exports the cryptographic primitives only; command wiring
must remain outside the storage substrate.

**Wipeable key material.** Every secret this module derives or recovers —
the recovery KEK and the unwrapped master key — is held in a
``bytearray`` rather than immutable ``bytes``, so the substrate's
:func:`zeroise` primitive can overwrite it in place. Functions that
derive a KEK zero it in a ``finally`` before returning; functions that
*return* key material hand back a buffer the caller is expected to zero
once it has finished with it.

The honest limit is unchanged from the one the session path already
discloses: passing a buffer to a ``bytes``-typed cryptographic primitive
materialises a transient immutable copy whose lifetime the garbage
collector owns. Those copies are bounded by a single call; what this
module does not do is hold the *only* copy of a secret in a form no wipe
primitive can reach.
"""

from __future__ import annotations

import base64
import binascii
from collections.abc import Buffer, Callable
from pathlib import Path
from typing import Final

from pydantic import BaseModel, Field, ValidationError

from .....core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from .....core.external_constants import UTF_8_ENCODING as _UTF_8_ENCODING
from .._recovery_key import RecoveryKey
from ..crypto import (
    KEY_SIZE,
    EncryptedBlob,
    decrypt_record,
    derive_key,
    encrypt_record,
)
from ..custody import zeroise as _zeroise
from ..errors import (
    EnvelopeVersionError,
)
from ..errors import (
    storage_validation_error as _storage_validation_error,
)

_RECOVERY_KEY_SIZE: Final[int] = 32
_HKDF_CONTEXT_RECOVERY: Final[bytes] = b"cadrumo.recovery-key.master-wrap.v1"
_RECOVERY_AAD: Final[bytes] = b"cadrumo.recovery-key.aad.v1"


WRAPPED_MASTER_KEY_SCHEMA_VERSION: Final[int] = 1
"""The one wrapped-recovery-master-key format version this build reads and writes.

Declared as a named constant so the version has one home, and compared
explicitly by :func:`unwrap_master_key` before the recovery key is touched.
A marker parsed into a field and then consulted by nobody is not a
compatibility mechanism; this file is the last route back to a bucket whose
master key is otherwise lost, so a format this build cannot interpret must
fail loudly rather than be fed to a decryption that can only produce garbage
or a misleading authentication failure.
"""


class WrappedMasterKey(BaseModel):
    """Frozen container for the recovery-key-wrapped master.key file.

    Persisted as JSON at ``<secret_store_dir>/master.recovery.key``.
    The operator's recovery key is the only material that can unwrap
    this file; the substrate's regular providers (keyring,
    file-fallback, unsecured) cannot consume it.

    The nonce and ciphertext are stored as base64 strings (rather than
    raw ``bytes``) so the JSON serialisation is portable across pydantic
    versions and operating systems. The ``to_blob`` / ``from_blob``
    helpers convert back to the in-memory :class:`EncryptedBlob` form.

    ``schema_version`` is required and carries no default. A default equal
    to the current version makes a stored file that omits the key hydrate AS
    current, so an exactness check reading the hydrated record can never see
    the omission and passes it through to the unwrap.
    """

    model_config = _STRICT_FROZEN

    schema_version: int = Field(ge=1)
    nonce_b64: str = Field(min_length=1)
    ciphertext_b64: str = Field(min_length=1)

    def to_blob(self) -> EncryptedBlob:
        """Decode the base64 fields into an :class:`EncryptedBlob`."""
        try:
            return EncryptedBlob(
                nonce=base64.b64decode(self.nonce_b64.encode("ascii"), validate=True),
                ciphertext=base64.b64decode(self.ciphertext_b64.encode("ascii"), validate=True),
            )
        except (ValueError, binascii.Error, ValidationError) as exc:
            raise _storage_validation_error("wrapped recovery master key is malformed") from exc

    @classmethod
    def from_blob(cls, blob: EncryptedBlob) -> WrappedMasterKey:
        """Build a :class:`WrappedMasterKey` from an in-memory blob."""
        return cls(
            schema_version=WRAPPED_MASTER_KEY_SCHEMA_VERSION,
            nonce_b64=base64.b64encode(blob.nonce).decode("ascii"),
            ciphertext_b64=base64.b64encode(blob.ciphertext).decode("ascii"),
        )


def _derive_recovery_kek(recovery_key_bytes: Buffer) -> bytearray:
    """Derive the 32-byte KEK that wraps the master key under the recovery key.

    Returns a wipeable ``bytearray``; every caller zeroes it once the wrap
    or unwrap it seeds has completed.
    """
    return bytearray(
        derive_key(
            key_material=bytes(recovery_key_bytes),
            salt=b"",  # The recovery-key bytes are themselves high-entropy.
            context=_HKDF_CONTEXT_RECOVERY,
            length=KEY_SIZE,
        ),
    )


def wrap_master_key(*, master_key: Buffer, recovery_key: RecoveryKey) -> WrappedMasterKey:
    """Wrap a 32-byte master key under a recovery-key-derived KEK.

    Args:
        master_key: The 32-byte master key to wrap. Accepts any buffer, so
            a wipeable ``bytearray`` need not be copied into immutable
            ``bytes`` by the caller.
        recovery_key: The recovery key whose bytes seed the wrapping KEK.

    Returns:
        A :class:`WrappedMasterKey` carrying the 12-byte nonce + the
        AES-256-GCM ciphertext. Serialise via ``model_dump_json()`` and
        persist to ``master.recovery.key``.

    Raises:
        StorageValidationError: When ``master_key`` is not exactly 32 bytes.
    """
    master_key_view = memoryview(master_key)
    if len(master_key_view) != KEY_SIZE:
        raise _storage_validation_error(
            f"master key must be exactly {KEY_SIZE} bytes; got {len(master_key_view)}",
        )
    kek = _derive_recovery_kek(recovery_key.raw)
    try:
        blob = encrypt_record(bytes(master_key_view), key=bytes(kek), associated_data=_RECOVERY_AAD)
    finally:
        _zeroise(kek)
    return WrappedMasterKey.from_blob(blob)


def unwrap_master_key(*, wrapped: WrappedMasterKey, recovery_key_bytes: Buffer) -> bytearray:
    """Recover the 32-byte master key from a wrapped record + the recovery-key bytes.

    Args:
        wrapped: The :class:`WrappedMasterKey` loaded from disk.
        recovery_key_bytes: The 32-byte recovery key (decoded via
            :func:`decode_mnemonic`).

    Returns:
        The 32-byte master key in a wipeable ``bytearray`` the caller is
        expected to :func:`zeroise` once it has re-minted custody from it.

    Raises:
        EnvelopeVersionError: When ``wrapped`` claims a format version other
            than :data:`WRAPPED_MASTER_KEY_SCHEMA_VERSION`. Checked first, so
            a record this build cannot interpret is refused before the
            recovery key is read and before a KEK is derived from it.
        StorageValidationError: When ``recovery_key_bytes`` is not exactly 32 bytes.
    """
    # Ahead of the recovery key entirely, not merely ahead of decrypt_record:
    # deriving the KEK spends the operator's recovery material, and a refusal
    # that arrives afterwards has already done the thing it exists to prevent.
    if wrapped.schema_version != WRAPPED_MASTER_KEY_SCHEMA_VERSION:
        raise EnvelopeVersionError(
            f"wrapped recovery master key is at version {wrapped.schema_version}; "
            f"consumer expects {WRAPPED_MASTER_KEY_SCHEMA_VERSION}",
        )
    recovery_view = memoryview(recovery_key_bytes)
    if len(recovery_view) != _RECOVERY_KEY_SIZE:
        raise _storage_validation_error(
            f"recovery key must be exactly {_RECOVERY_KEY_SIZE} bytes; got {len(recovery_view)}",
        )
    kek = _derive_recovery_kek(recovery_view)
    try:
        return bytearray(
            decrypt_record(wrapped.to_blob(), key=bytes(kek), associated_data=_RECOVERY_AAD),
        )
    finally:
        _zeroise(kek)


def save_wrapped_master_key(wrapped: WrappedMasterKey, path: Path) -> None:
    """Atomically persist a wrapped master key to ``path``.

    Uses the substrate's ``atomic_write_secure_bytes`` helper so the
    file lands restricted from creation (mode 0o600), the tempfile is
    fsynced before the ``os.replace`` swap, and the parent directory
    entry is fsynced after — durable across power loss on POSIX.
    """
    from ._master_key import atomic_write_secure_bytes

    payload = wrapped.model_dump_json().encode(_UTF_8_ENCODING)
    atomic_write_secure_bytes(path, payload)


def load_wrapped_master_key(path: Path) -> WrappedMasterKey:
    """Read and validate a wrapped-master-key file, returning a :class:`WrappedMasterKey`."""
    try:
        return WrappedMasterKey.model_validate_json(path.read_text(encoding=_UTF_8_ENCODING))
    except (OSError, ValueError, ValidationError) as exc:
        raise _storage_validation_error("wrapped recovery master key file is malformed") from exc


def atomically_install_verified_recovery(
    *,
    path: Path,
    payload: bytes,
    verify: Callable[[], None],
) -> None:
    """Persist ``payload`` to ``path`` only after ``verify`` passes.

    This is the single ordering guarantee behind recovery ``create`` and
    ``rotate``: the candidate recovery envelope must be *fully* verified — a
    real mnemonic unwrap / AES-GCM tag check, never a string comparison —
    before it may replace whatever is already on disk. ``verify`` MUST raise
    when the candidate is not valid; it returns ``None`` only when the
    candidate is proven good.

    Because the atomic write is not reached until ``verify`` returns without
    raising, a cancelled, mistyped, or corrupt candidate leaves any prior
    recovery envelope at ``path`` byte-for-byte untouched. The write itself
    goes through the substrate's ``atomic_write_secure_bytes`` (restrictive
    permissions from creation, fsync, ``os.replace``), so the replacement is
    all-or-nothing and never leaves a torn envelope.

    Args:
        path: Destination recovery-envelope path.
        payload: The serialized candidate envelope bytes to install.
        verify: A zero-argument callable that fully validates the candidate and
            raises on any failure.
    """
    verify()
    from ._master_key import atomic_write_secure_bytes

    atomic_write_secure_bytes(path, payload)


__all__ = [
    "WRAPPED_MASTER_KEY_SCHEMA_VERSION",
    "WrappedMasterKey",
    "atomically_install_verified_recovery",
    "load_wrapped_master_key",
    "save_wrapped_master_key",
    "unwrap_master_key",
    "wrap_master_key",
]
