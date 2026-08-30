"""Encrypted persistence adapter for recipient-package replay-nonce ledgers.

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
the ``aeat-architecture-boundaries`` companion to that
registry -- the decrypt primitive itself performs no persistence; a caller
(the future CLI decrypt verb) composes this ledger's ``check_and_consume``
around the existing, unmodified
:func:`~application.modelo.decrypt_review_package_for_recipient` call.
The encrypted row's storage policy is governed by
:class:`~adapters.persistence.storage.SensitivityClass`.

``mark_consumed`` composes
:class:`~adapters.persistence.profile._secure_model_document.ProfileBareModelSecurePersistence`'s
``mutate`` for its read-mutate-write-with-retry mechanic, rather than
hand-rolling the loop: the ledger is stored bare (``ConsumedNonceLedger.model_dump_json()``
directly, no ``Envelope`` wrapper), matching that kernel's wire shape exactly,
and the "refuse a duplicate nonce unretried, else append and retry only on a
genuine revision conflict" logic is precisely the ``mutate`` contract. ``load``
stays hand-rolled because it translates a bare ``OSError`` into
``RecipientReplayGuardError``, a translation the kernel does not perform.

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

from ....core import HEX_PATTERN_64 as _HEX_PATTERN_64
from ....core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ....core.errors.hierarchy import CadrumoError
from ....core.time import UtcInstant
from ....core.time import now as _utc_now
from ..storage import (
    MODELO_REVIEW_PACKAGE_RECIPIENT_REPLAY_GUARD_NAMESPACE as _NAMESPACE,
)
from ._secure_model_document import ProfileBareModelSecurePersistence, resolve_profile_secure_object_repository

if TYPE_CHECKING:
    from ..storage import SecureObjectRepository


# A stale writer always fails closed at the secure-object CAS boundary. This
# generous bound lets a hot burst make progress without turning unbounded
# contention into an infinite loop.
#
# Deliberately higher than ProfileBareModelSecurePersistence.mutate()'s
# default of 4: nonce consumption is a burst-contention point in a way most
# singleton-document mutations are not -- a recipient re-running a decrypt
# CLI verb, or several concurrent decrypt attempts of the same captured
# package, all race to mutate this exact ledger at once. 4 attempts is tuned
# for occasional single-writer contention; this ledger's own concurrency
# test (test_concurrent_same_nonce_consumption_allows_exactly_one_success)
# exercises 8 simultaneous writers on one nonce, which the default budget
# is not sized for.
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
    consumed_at: UtcInstant


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
        self._storage = ProfileBareModelSecurePersistence(
            objects=resolve_profile_secure_object_repository(objects=objects, bucket_id=bucket_id),
            definition=_NAMESPACE,
            model_type=ConsumedNonceLedger,
            empty_document=ConsumedNonceLedger,
            write_provenance="adapters.persistence.profile.recipient_replay_guard",
        )

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
        try:
            ledger, _revision_id = self._storage.load_revisioned()
        except OSError as exc:
            raise RecipientReplayGuardError(
                "unable to load recipient replay-guard ledger",
                context={"namespace": self._storage.namespace, "object_key": self._storage.object_key},
                translated_message="application.modelo.errors.recipient_registry_load_failed",
            ) from exc
        return ledger

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

        def _append_if_new(current: ConsumedNonceLedger) -> ConsumedNonceLedger:
            if any(existing.nonce_hex == nonce_hex for existing in current.records):
                raise RecipientPackageReplayedError(
                    "recipient-encrypted package nonce has already been consumed; refusing replay",
                    context={"nonce_hex": nonce_hex},
                    translated_message="application.modelo.errors.recipient_decryption_failed",
                )
            return ConsumedNonceLedger(records=(*current.records, record))

        return self._storage.mutate(_append_if_new, attempts=_CONSUME_RETRY_LIMIT)


__all__ = [
    "ConsumedNonceLedger",
    "ConsumedNonceRecord",
    "RecipientPackageReplayedError",
    "RecipientReplayGuardError",
    "RecipientReplayGuardRepository",
]
