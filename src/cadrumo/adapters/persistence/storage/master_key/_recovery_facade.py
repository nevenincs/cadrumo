"""Typed BIP-39 recovery facade for the per-bucket unlock pipeline.

The substrate's BIP-39 mnemonic encoding, HKDF-derived recovery KEK, and
AES-256-GCM wrap of the master DEK live in `_recovery.py`. This module
exposes a typed boundary over those primitives so callers consume and
produce the strict pydantic v2 records (`RecoveryRecord` for the
on-disk envelope, `BucketSession` for the live in-memory state)
without reaching into the substrate. The internals never leave
`_recovery.py`.

`mint_recovery_envelope` is called at enrollment: it generates a fresh
24-word BIP-39 mnemonic, derives the recovery KEK from the entropy,
wraps the supplied DEK under that KEK, and returns the `RecoveryRecord`
+ the plaintext mnemonic (the only in-memory copy; the caller arranges
for the operator to copy it down).

`unwrap_recovery_envelope` is called at recovery: it accepts the
mnemonic the operator typed, decodes the entropy, derives the recovery
KEK, and decrypts the wrapped DEK from the `RecoveryRecord`. The
plaintext mnemonic is never persisted.

`open_session_from_recovery` composes `unwrap_recovery_envelope` with
`BucketSession.open` so the recovery-flow CLI verb yields a live
session the wizard can re-wrap under a fresh passphrase-derived KEK.
"""

from __future__ import annotations

import base64
import binascii
from collections.abc import Buffer, Callable
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Self

from pydantic import BaseModel, ValidationError

from .....core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from .....core.external_constants import UTF_8_ENCODING as _UTF_8_ENCODING
from ..bucket import RecoveryVerificationError
from ..crypto import EncryptedBlob
from ..errors import DecryptionError, SecretStoreError, StorageValidationError
from ._bucket_session import BucketSession
from ._recovery import (
    RecoveryKey,
    WrappedMasterKey,
    atomically_install_verified_recovery,
    decode_mnemonic,
    generate_recovery_key,
    unwrap_master_key,
    wrap_master_key,
)
from ._recovery_record import RecoveryRecord
from ._zeroise import zeroise as _zeroise

if TYPE_CHECKING:
    from ._master_key import FileFallbackMasterKeyProvider, MasterKeyProvider

_GCM_TAG_BYTES = 16
_HKDF_INFO = "cadrumo.recovery-key.master-wrap.v1"


class MintedRecovery:
    """In-memory result of a recovery enrollment.

    The mnemonic is the only handle on the recovery KEK; the caller
    arranges for the operator to copy it, then calls :meth:`wipe`.

    Held in a wipeable ``bytearray`` rather than an immutable ``str``,
    and deliberately not a pydantic model, for the reasons
    :class:`RecoveryKey` documents: an enrollment carries this value
    across the operator's interactive confirmation, and a model with a
    ``model_dump_json`` is one careless call away from serialising the
    recovery code the envelope exists to keep off disk.

    The ``envelope`` is public ciphertext and stays a strict pydantic
    record — it is exactly the part that *is* meant to be serialised.
    """

    __slots__ = ("_mnemonic_buffer", "envelope")

    def __init__(self, *, envelope: RecoveryRecord, mnemonic: str) -> None:
        self.envelope = envelope
        self._mnemonic_buffer = bytearray(mnemonic.encode(_UTF_8_ENCODING))

    @property
    def mnemonic(self) -> str:
        """Return the 24-word mnemonic, decoded from its wipeable buffer."""
        return self._mnemonic_buffer.decode(_UTF_8_ENCODING)

    def wipe(self) -> None:
        """Overwrite the mnemonic buffer with zero bytes. Idempotent."""
        _zeroise(self._mnemonic_buffer)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.wipe()


def _envelope_from_blob(blob: EncryptedBlob, created_at: datetime) -> RecoveryRecord:
    """Split the GCM wire shape into the `RecoveryRecord` field set."""
    ciphertext_with_tag = blob.ciphertext
    ciphertext = ciphertext_with_tag[:-_GCM_TAG_BYTES]
    tag = ciphertext_with_tag[-_GCM_TAG_BYTES:]
    return RecoveryRecord(
        wrapped_dek_b64=base64.b64encode(ciphertext).decode("ascii"),
        nonce_b64=base64.b64encode(blob.nonce).decode("ascii"),
        tag_b64=base64.b64encode(tag).decode("ascii"),
        mnemonic_word_count=24,
        hkdf_info=_HKDF_INFO,
        created_at=created_at,
    )


def _blob_from_envelope(envelope: RecoveryRecord) -> EncryptedBlob:
    """Re-assemble an `EncryptedBlob` from the typed envelope fields."""
    try:
        nonce = base64.b64decode(envelope.nonce_b64.encode("ascii"), validate=True)
        ciphertext = base64.b64decode(envelope.wrapped_dek_b64.encode("ascii"), validate=True)
        tag = base64.b64decode(envelope.tag_b64.encode("ascii"), validate=True)
        return EncryptedBlob(nonce=nonce, ciphertext=ciphertext + tag)
    except (ValueError, binascii.Error, ValidationError) as exc:
        raise RecoveryVerificationError("recovery envelope is malformed") from exc


def mint_recovery_envelope(*, dek: Buffer, created_at: datetime) -> MintedRecovery:
    """Mint a fresh :class:`MintedRecovery` envelope wrapping ``dek``.

    Returns a :class:`MintedRecovery` carrying the typed ``RecoveryRecord`` and
    the 24-word mnemonic the operator must record. The mnemonic is the
    only handle on the recovery KEK; this function does NOT persist it.

    The intermediate :class:`RecoveryKey` is wiped before returning: the
    minted record takes its own copy of the mnemonic, so the entropy and
    the generator's copy of the words do not outlive this call.
    """
    recovery_key: RecoveryKey = generate_recovery_key()
    try:
        wrapped: WrappedMasterKey = wrap_master_key(master_key=dek, recovery_key=recovery_key)
        blob = wrapped.to_blob()
        envelope = _envelope_from_blob(blob, created_at=created_at)
        return MintedRecovery(envelope=envelope, mnemonic=recovery_key.mnemonic)
    finally:
        recovery_key.wipe()


def unwrap_recovery_envelope(
    *,
    envelope: RecoveryRecord,
    mnemonic: str,
    decoder: Callable[[str], Buffer] | None = None,
) -> bytearray:
    """Decode ``mnemonic`` and unwrap ``envelope`` to recover the 32-byte DEK.

    Args:
        envelope: The persisted :class:`RecoveryRecord` to unwrap.
        mnemonic: The 24-word BIP-39 mnemonic supplied by the operator.
        decoder: Optional override for mnemonic decoding; production callers omit it.

    Returns:
        The recovered 32-byte data-encryption key, in a wipeable
        ``bytearray`` the caller is expected to :func:`zeroise` once it has
        opened a session or re-minted custody from it.

    Raises:
        RecoveryVerificationError: When the mnemonic does not decode or the AEAD tag
            check fails.
    """
    resolved_decoder = decoder or decode_mnemonic
    try:
        entropy = bytearray(resolved_decoder(mnemonic))
    except StorageValidationError as exc:
        raise RecoveryVerificationError(str(exc)) from exc

    try:
        blob = _blob_from_envelope(envelope)
        wrapped = WrappedMasterKey.from_blob(blob)
        return unwrap_master_key(wrapped=wrapped, recovery_key_bytes=entropy)
    except (DecryptionError, StorageValidationError) as exc:
        raise RecoveryVerificationError(
            "recovery envelope did not decrypt under the supplied mnemonic",
        ) from exc
    finally:
        # The decoded entropy is the recovery key itself; it has served its
        # purpose the moment the KEK is derived, whether or not that succeeded.
        _zeroise(entropy)


def verify_recovery_mnemonic(*, envelope: RecoveryRecord, mnemonic: str) -> bool:
    """Return True iff the mnemonic correctly unwraps the envelope.

    Used by the `aeat config recovery verify` periodic-custody-test
    verb. Catches `RecoveryVerificationError` and surfaces a boolean
    so the CLI renders the outcome without leaking detail.

    A successful check unwraps the real DEK purely to prove the AEAD tag
    verifies, so the recovered buffer is zeroed before returning. This verb
    is the one an operator is told to run *periodically*, which would
    otherwise make it the most frequently repeated plaintext-DEK exposure
    on the whole recovery surface.
    """
    try:
        dek = unwrap_recovery_envelope(envelope=envelope, mnemonic=mnemonic)
    except RecoveryVerificationError:
        return False
    _zeroise(dek)
    return True


def save_recovery_envelope(envelope: RecoveryRecord, path: Path) -> None:
    """Atomically persist a typed recovery envelope."""
    from ._master_key import atomic_write_secure_bytes

    atomic_write_secure_bytes(path, envelope.model_dump_json().encode(_UTF_8_ENCODING))


def load_recovery_envelope(path: Path) -> RecoveryRecord:
    """Read, validate, and return a :class:`RecoveryRecord` from ``path``."""
    try:
        return RecoveryRecord.model_validate_json(path.read_text(encoding=_UTF_8_ENCODING))
    except (OSError, ValueError, ValidationError) as exc:
        raise RecoveryVerificationError("recovery envelope file is malformed") from exc


def open_session_from_recovery(
    *,
    bucket_id: str,
    envelope: RecoveryRecord,
    mnemonic: str,
    kek: bytes,
    idle_minutes: int,
    opened_at: datetime,
    storage_root: Path | None = None,
) -> BucketSession:
    """Compose mnemonic-unwrap with `BucketSession.open` and return a :class:`BucketSession`.

    The caller supplies the freshly-derived passphrase KEK (the
    operator's new passphrase, run through Argon2id under a fresh salt);
    the function unwraps the DEK from the recovery envelope and yields
    a live session bound to `bucket_id`.

    ``BucketSession.open`` copies the DEK into its own wipeable session
    buffer, so the unwrapped copy here is zeroed once the session owns it;
    from that point the session's ``close`` is the wipe authority.
    """
    dek = unwrap_recovery_envelope(envelope=envelope, mnemonic=mnemonic)
    try:
        return BucketSession.open(
            bucket_id=bucket_id,
            kek=kek,
            dek=bytes(dek),
            idle_minutes=idle_minutes,
            opened_at=opened_at,
            storage_root=storage_root,
        )
    finally:
        _zeroise(dek)


# ---------------------------------------------------------------------------
# Recovery lifecycle operations
#
# The typed operations below are the single authority for the operator-facing
# recovery lifecycle (status, create, rotate, verify, recover). They enforce
# three invariants the low-level primitives above do not:
#
#   * file custody only — mnemonic recovery rewraps the master key, which is a
#     file-backend concept; keyring and unsecured custody refuse;
#   * create refuses an existing enrollment and rotate requires one;
#   * a candidate mnemonic is fully verified before the prior envelope is ever
#     replaced (via ``atomically_install_verified_recovery``).
#
# None of these operations serialize the mnemonic or the master key: their
# result records carry only the non-secret recovery fingerprint and booleans.
# ---------------------------------------------------------------------------


class RecoveryEnrollmentMode(StrEnum):
    """Whether an enrollment operation creates a first envelope or rotates one."""

    CREATE = "create"
    ROTATE = "rotate"


class RecoveryLifecycleStatus(BaseModel):
    """Read-only recovery enrollment status for a secret store."""

    model_config = _STRICT_FROZEN

    enrolled: bool
    recovery_fingerprint: str | None = None


class RecoveryEnrollmentOutcome(BaseModel):
    """Result of a committed recovery ``create`` or ``rotate``.

    Carries only the non-secret fingerprint of the freshly installed envelope
    and whether the operation replaced a prior enrollment. The staged mnemonic
    is never returned here; the caller displayed it during confirmation.
    """

    model_config = _STRICT_FROZEN

    recovery_fingerprint: str
    rotated: bool


class RecoveryVerifyOutcome(BaseModel):
    """Result of checking an operator-supplied mnemonic against the envelope."""

    model_config = _STRICT_FROZEN

    verified: bool
    recovery_fingerprint: str | None = None


class RecoveryRecoverOutcome(BaseModel):
    """Result of rewrapping the master key from the recovery envelope."""

    model_config = _STRICT_FROZEN

    recovery_fingerprint: str


def _require_file_custody(provider: MasterKeyProvider) -> FileFallbackMasterKeyProvider:
    """Return ``provider`` narrowed to the file backend, or refuse.

    Mnemonic recovery rewraps the master key under a new file passphrase, which
    only the encrypted-file backend supports. Keyring and unsecured custody are
    refused with typed, remediating :class:`SecretStoreError` refusals rather
    than silently succeeding or crashing later.
    """
    from ._master_key import (
        FileFallbackMasterKeyProvider,
        KeyringMasterKeyProvider,
        UnsecuredMasterKeyProvider,
    )

    if isinstance(provider, FileFallbackMasterKeyProvider):
        return provider
    if isinstance(provider, KeyringMasterKeyProvider):
        raise SecretStoreError(
            "recovery and passphrase custody operations require the file secret-store "
            "backend; the resolved backend is the OS keyring. Set "
            "CADRUMO_SECRET_STORE_BACKEND=file and retry.",
        )
    if isinstance(provider, UnsecuredMasterKeyProvider):
        raise SecretStoreError(
            "recovery and passphrase custody operations require the file secret-store "
            "backend; the resolved backend is unsecured, which holds no recoverable "
            "master key. Set CADRUMO_SECRET_STORE_BACKEND=file and retry.",
        )
    raise SecretStoreError(
        "recovery and passphrase custody operations require the file secret-store "
        f"backend; the resolved backend {type(provider).__name__} is unsupported.",
    )


def recovery_status(*, path: Path) -> RecoveryLifecycleStatus:
    """Report whether a recovery envelope is enrolled at ``path``.

    Read-only. When enrolled, the returned status carries the non-secret
    :attr:`RecoveryRecord.recovery_fingerprint` so the operator can correlate
    the enrollment across verify and recover without exposing any secret.
    """
    if not path.is_file():
        return RecoveryLifecycleStatus(enrolled=False, recovery_fingerprint=None)
    envelope = load_recovery_envelope(path)
    return RecoveryLifecycleStatus(enrolled=True, recovery_fingerprint=envelope.recovery_fingerprint)


def _enroll_recovery(
    *,
    provider: MasterKeyProvider,
    path: Path,
    mode: RecoveryEnrollmentMode,
    created_at: datetime,
    confirm: Callable[[str], str],
) -> RecoveryEnrollmentOutcome:
    """Stage a candidate envelope, verify the retype, then atomically install it."""
    file_provider = _require_file_custody(provider)
    already_enrolled = path.is_file()
    if mode is RecoveryEnrollmentMode.CREATE and already_enrolled:
        raise SecretStoreError(
            "recovery is already enrolled for this secret store; use recovery rotate "
            "to replace the existing recovery envelope.",
        )
    if mode is RecoveryEnrollmentMode.ROTATE and not already_enrolled:
        raise SecretStoreError(
            "no recovery envelope is enrolled for this secret store; use recovery create "
            "to enroll one before rotating.",
        )

    # The provider hands back immutable bytes (its own steady-state contract);
    # copy into a wipeable buffer immediately, because this value is then held
    # live across `confirm`, an interactive prompt that lasts as long as it
    # takes the operator to copy down 24 words.
    master_key = bytearray(file_provider.get_master_key())
    candidate: MintedRecovery | None = None
    try:
        candidate = mint_recovery_envelope(dek=master_key, created_at=created_at)
        _zeroise(master_key)
        retyped = confirm(candidate.mnemonic)
        payload = candidate.envelope.model_dump_json().encode(_UTF_8_ENCODING)
        staged_envelope = candidate.envelope

        def _verify_candidate() -> None:
            if not verify_recovery_mnemonic(envelope=staged_envelope, mnemonic=retyped):
                raise RecoveryVerificationError(
                    "recovery confirmation did not match the staged recovery code; "
                    "the previous recovery envelope is unchanged.",
                )

        atomically_install_verified_recovery(path=path, payload=payload, verify=_verify_candidate)
        return RecoveryEnrollmentOutcome(
            recovery_fingerprint=staged_envelope.recovery_fingerprint,
            rotated=mode is RecoveryEnrollmentMode.ROTATE,
        )
    finally:
        # Runs on the cancelled and mistyped paths too, where the operator has
        # already seen a mnemonic that will never be installed.
        _zeroise(master_key)
        if candidate is not None:
            candidate.wipe()


def recovery_create(
    *,
    provider: MasterKeyProvider,
    path: Path,
    created_at: datetime,
    confirm: Callable[[str], str],
) -> RecoveryEnrollmentOutcome:
    """Enroll a first recovery envelope; refuse if one already exists.

    ``provider`` is the resolved :class:`MasterKeyProvider`; only the file
    backend is accepted. ``confirm`` receives the staged 24-word mnemonic (the
    caller writes it to the controlling terminal), returns the operator's
    no-echo retype, and may raise to cancel. The candidate is fully verified
    before any file is written, so a cancelled or mistyped confirmation leaves
    the store with no envelope.
    """
    return _enroll_recovery(
        provider=provider,
        path=path,
        mode=RecoveryEnrollmentMode.CREATE,
        created_at=created_at,
        confirm=confirm,
    )


def recovery_rotate(
    *,
    provider: MasterKeyProvider,
    path: Path,
    created_at: datetime,
    confirm: Callable[[str], str],
) -> RecoveryEnrollmentOutcome:
    """Replace an existing recovery envelope; require an existing enrollment.

    Two-phase like :func:`recovery_create`, against the file-backed
    :class:`MasterKeyProvider`. The prior envelope survives a cancelled,
    mistyped, or otherwise unverified candidate untouched, and is atomically
    replaced only after the retype is fully verified.
    """
    return _enroll_recovery(
        provider=provider,
        path=path,
        mode=RecoveryEnrollmentMode.ROTATE,
        created_at=created_at,
        confirm=confirm,
    )


def recovery_verify(
    *,
    provider: MasterKeyProvider,
    path: Path,
    mnemonic: str,
) -> RecoveryVerifyOutcome:
    """Verify ``mnemonic`` against the enrolled envelope without changing custody.

    File custody only: ``provider`` must be a file-backed
    :class:`MasterKeyProvider`. The envelope file is read, never written, so the
    :attr:`RecoveryRecord.recovery_fingerprint` reported here is identical
    before and after the call.
    """
    _require_file_custody(provider)
    if not path.is_file():
        return RecoveryVerifyOutcome(verified=False, recovery_fingerprint=None)
    envelope = load_recovery_envelope(path)
    verified = verify_recovery_mnemonic(envelope=envelope, mnemonic=mnemonic)
    return RecoveryVerifyOutcome(verified=verified, recovery_fingerprint=envelope.recovery_fingerprint)


def recovery_recover(
    *,
    provider: MasterKeyProvider,
    path: Path,
    mnemonic: str,
) -> RecoveryRecoverOutcome:
    """Rewrap the master key from ``mnemonic`` under the file provider's passphrase.

    File custody only: ``provider`` must be a file-backed
    :class:`MasterKeyProvider`. Unwraps the master key from the recovery
    envelope and calls the file provider's ``complete_recovery`` to re-mint
    ``master.key`` / ``master.kdf`` under its (new) passphrase. The recovery
    envelope itself is never rewritten, so its fingerprint is preserved across
    the operation.
    """
    file_provider = _require_file_custody(provider)
    envelope = load_recovery_envelope(path)
    established_fingerprint = envelope.recovery_fingerprint
    master_key = unwrap_recovery_envelope(envelope=envelope, mnemonic=mnemonic)
    try:
        file_provider.complete_recovery(bytes(master_key))
    finally:
        _zeroise(master_key)
    return RecoveryRecoverOutcome(recovery_fingerprint=established_fingerprint)


__all__ = [
    "MintedRecovery",
    "RecoveryEnrollmentMode",
    "RecoveryEnrollmentOutcome",
    "RecoveryLifecycleStatus",
    "RecoveryRecoverOutcome",
    "RecoveryVerifyOutcome",
    "load_recovery_envelope",
    "mint_recovery_envelope",
    "open_session_from_recovery",
    "recovery_create",
    "recovery_recover",
    "recovery_rotate",
    "recovery_status",
    "recovery_verify",
    "save_recovery_envelope",
    "unwrap_recovery_envelope",
    "verify_recovery_mnemonic",
]
