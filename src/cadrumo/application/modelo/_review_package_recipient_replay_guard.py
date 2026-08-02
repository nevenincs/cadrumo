"""Replay-nonce ledger for recipient-encrypted review packages.

Every :class:`~application.modelo.RecipientEncryptedPackage` carries a
fresh, unique ``envelope_nonce_hex`` minted at encryption time (see
:mod:`~application.modelo._review_package_recipient_encryption`). This
module lets the recipient side of :func:`~application.modelo.decrypt_review_package_for_recipient`
record which nonces have already been successfully decrypted, so a captured
ciphertext replayed a second time against the same recipient bucket is
refused rather than silently re-accepted.

The nonce ledger is a bucket-scoped append-only consumption record, following
the exact governed-repository shape of
:class:`~application.modelo.RecipientFingerprintRegistryRepository`: one
``FINANCIAL``-sensitivity secure-object singleton per bucket, an empty ledger
when absent, and ``mark_consumed`` refuses a nonce already on file. This is
the ``composition-service-no-parallel-write-path`` companion to that
registry -- the decrypt primitive itself performs no persistence; a caller
(the future CLI decrypt verb) composes this ledger's ``check_and_consume``
around the existing, unmodified
:func:`~application.modelo.decrypt_review_package_for_recipient` call.
The encrypted row's storage policy is governed by
:class:`~adapters.persistence.storage.SensitivityClass`.

Nonce identity is clock-free (the nonce is a random 32-byte value minted once
per encryption, never derived from a timestamp), so replay defence does not
depend on wall-clock ordering the way the paired expiry check does -- see
:mod:`~application.modelo._review_package_recipient_encryption` for the
``issued_at`` / ``valid_until`` expiry fields, which are a distinct concern
(a package can be replayed within its validity window, and expiry alone does
not detect a same-nonce replay before the deadline).

See Also:
    :mod:`~application.modelo._review_package_recipient_encryption`
        Mints the ``envelope_nonce_hex`` this ledger consumes and defines the
        paired expiry fields.
    :mod:`~application.modelo._review_package_recipient_registry`
        The structural template this repository mirrors.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from ...adapters.persistence.storage import (
    MODELO_REVIEW_PACKAGE_RECIPIENT_REPLAY_GUARD_NAMESPACE as _NAMESPACE,
)
from ...adapters.persistence.storage import (
    SecureObjectRevisionConflictError,
    secure_object_repository_for_active_bucket,
    secure_object_repository_for_bucket,
)
from ...core import ABSENT_SECURE_OBJECT_REVISION_ID
from ...core import HEX_PATTERN_64 as _HEX_PATTERN_64
from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.errors import CadrumoError
from ...core.external_constants import UTF_8_ENCODING as _UTF_8_ENCODING
from ...core.time import now as _utc_now

if TYPE_CHECKING:
    from ...adapters.persistence.storage import SecureObjectRepository


# A stale writer always fails closed at the secure-object CAS boundary. This
# generous bound lets a hot burst make progress without turning unbounded
# contention into an infinite loop.
_CONSUME_RETRY_LIMIT = 64


class RecipientReplayGuardError(CadrumoError):
    """Base error for recipient-package replay-guard failures."""


class RecipientPackageReplayedError(RecipientReplayGuardError):
    """Raised when a nonce already recorded as consumed is presented again.

    A captured recipient-encrypted package replayed against the same bucket
    (whether by an adversary or by an operator's own accidental re-run) is
    refused -- the nonce is single-use once consumed.
    """


class ConsumedNonceRecord(BaseModel):
    """One consumed ``envelope_nonce_hex`` on file, with its consumption time."""

    model_config = _STRICT_FROZEN

    nonce_hex: str = Field(pattern=_HEX_PATTERN_64)
    consumed_at: datetime


class ConsumedNonceLedger(BaseModel):
    """A bucket's full set of consumed recipient-package replay nonces."""

    model_config = _STRICT_FROZEN

    records: tuple[ConsumedNonceRecord, ...] = Field(default_factory=tuple)


class RecipientReplayGuardRepository:
    """Governed repository for the encrypted consumed-nonce ledger.

    The singleton row is owned by
    :data:`~adapters.persistence.storage.MODELO_REVIEW_PACKAGE_RECIPIENT_REPLAY_GUARD_NAMESPACE`
    and persisted through
    :class:`~adapters.persistence.storage.SecureObjectRepository`, mirroring
    :class:`~application.modelo.RecipientFingerprintRegistryRepository`.
    """

    def __init__(
        self,
        *,
        bucket_id: str | None = None,
        objects: SecureObjectRepository | None = None,
    ) -> None:
        """Initialise the repository.

        Args:
            bucket_id: Explicit bucket to bind to, resolved through
                :func:`~adapters.persistence.storage.secure_object_repository_for_bucket`.
                Ignored when ``objects`` is supplied.
            objects: Explicit
                :class:`~adapters.persistence.storage.SecureObjectRepository`
                override
                (tests). When neither ``objects`` nor ``bucket_id`` is
                supplied, defaults to the active-bucket secure object store.
        """
        if objects is not None:
            self._objects = objects
        elif bucket_id is not None:
            self._objects = secure_object_repository_for_bucket(bucket_id)
        else:
            self._objects = secure_object_repository_for_active_bucket()

    def load(self) -> ConsumedNonceLedger:
        """Load the ledger, returning an empty ledger when absent.

        Raises:
            RecipientReplayGuardError: When the envelope exists but the
                filesystem I/O itself fails.
            DecryptionError: When the envelope exists but its ciphertext
                fails AEAD authentication (tampered or corrupted at rest) --
                propagated verbatim rather than re-wrapped, so a caller can
                distinguish "this ledger was tampered with" from a generic
                I/O failure. This is the anti-tautology proof this
                repository's roundtrip tests require: a corrupted on-disk
                payload must be refused loudly, not silently coerced into a
                plausible-looking empty ledger (which would re-open every
                previously-consumed nonce to replay).
        """
        ledger, _revision_id = self._load_revisioned()
        return ledger

    def _load_revisioned(self) -> tuple[ConsumedNonceLedger, str]:
        """Load the ledger with the secure-object revision backing that snapshot."""
        try:
            record = self._objects.load(
                _NAMESPACE.namespace,
                self._object_key,
                expected_class=_NAMESPACE.sensitivity,
                max_supported_version=_NAMESPACE.schema_version,
            )
            if record is None:
                return ConsumedNonceLedger(), ABSENT_SECURE_OBJECT_REVISION_ID
            ledger = ConsumedNonceLedger.model_validate_json(record.payload.decode(_UTF_8_ENCODING))
            return ledger, record.revision_id
        except OSError as exc:
            raise RecipientReplayGuardError(
                f"unable to load recipient replay-guard ledger: {self._object_key}",
                context={"namespace": _NAMESPACE.namespace, "object_key": self._object_key},
                translated_message="application.modelo.errors.recipient_registry_load_failed",
            ) from exc

    def is_consumed(self, nonce_hex: str) -> bool:
        """Return whether ``nonce_hex`` has already been recorded as consumed."""
        return any(existing.nonce_hex == nonce_hex for existing in self.load().records)

    def mark_consumed(
        self,
        nonce_hex: str,
        *,
        consumed_at: datetime | None = None,
    ) -> ConsumedNonceLedger:
        """Atomically record ``nonce_hex`` as consumed.

        Args:
            nonce_hex: The envelope's ``envelope_nonce_hex`` (see
                :class:`~application.modelo.RecipientEncryptedPackage`).
            consumed_at: Optional override for the record's ``consumed_at``
                timestamp (tests only); defaults to the current UTC time.

        Raises:
            RecipientPackageReplayedError: When ``nonce_hex`` is already on
                file -- the package has been presented for decryption before.
        """
        record = ConsumedNonceRecord(nonce_hex=nonce_hex, consumed_at=consumed_at or _utc_now())
        for attempt in range(_CONSUME_RETRY_LIMIT):
            current, revision_id = self._load_revisioned()
            if any(existing.nonce_hex == nonce_hex for existing in current.records):
                raise RecipientPackageReplayedError(
                    "recipient-encrypted package nonce has already been consumed; refusing replay",
                    context={"nonce_hex": nonce_hex},
                    translated_message="application.modelo.errors.recipient_decryption_failed",
                )
            updated = ConsumedNonceLedger(records=(*current.records, record))
            try:
                self._save_revisioned(updated, expected_revision_id=revision_id)
            except SecureObjectRevisionConflictError:
                if attempt + 1 == _CONSUME_RETRY_LIMIT:
                    raise
                continue
            return updated
        raise AssertionError("bounded recipient replay consumption retry loop exhausted")

    def _save_revisioned(self, ledger: ConsumedNonceLedger, *, expected_revision_id: str) -> None:
        self._objects.save(
            namespace=_NAMESPACE.namespace,
            object_key=self._object_key,
            classification=_NAMESPACE.sensitivity,
            schema_version=_NAMESPACE.schema_version,
            written_at=_utc_now(),
            payload=ledger.model_dump_json().encode(_UTF_8_ENCODING),
            write_provenance="application.modelo.review_package_recipient_replay_guard",
            expected_revision_id=expected_revision_id,
        )

    @property
    def _object_key(self) -> str:
        return _NAMESPACE.require_default_object_key()


__all__ = [
    "ConsumedNonceLedger",
    "ConsumedNonceRecord",
    "RecipientPackageReplayedError",
    "RecipientReplayGuardError",
    "RecipientReplayGuardRepository",
]
