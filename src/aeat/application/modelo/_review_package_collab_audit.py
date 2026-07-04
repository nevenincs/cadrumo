"""Bucket-event audit-tag emission for the accountant/gestor collaboration surface.

This module closes the "``collab_event`` / ``privacy_event`` audit-tag
enrolment" item left open on issue #421
(`2026-07-04-recipient-encryption-adr` and its follow-up slices): every
trust-boundary crossing on the review-package recipient-encryption surface
-- registering or removing a trusted recipient, sealing a package for a
recipient, decrypting a sealed package, opening a review-only workspace, and
counter-signing a received package -- now emits a typed
:class:`~aeat.domain.buckets.BucketEvent` so an operator can reconstruct the
collaboration timeline from the bucket-event-history catalogue, mirroring
every other material workflow transition in the codebase
(``aeat-swarm-audit-cadence``'s persistence-identity axis; the pattern
established by ``_iva_wallet_seed.py`` and ``_revision_persistence.py``).

Two distinct event-name prefixes are used, per the enum's own grouping
comment: ``collab_event.*`` marks a TRUST/TRANSPORT-boundary action (adding a
recipient, sealing a package for them) that does not itself expose decrypted
material to the caller emitting the event; ``privacy_event.*`` marks a
DISCLOSURE-relevant action where decrypted or otherwise sensitive material
was read (decrypting a package, opening a review-only workspace). This
mirrors the ADR's own vocabulary and lets a future audit query distinguish
"who was trusted / what was sealed" from "what was actually read".

Every function in this module is a thin, pure composition over
:func:`aeat.application.modelo._revision_persistence.emit_bucket_event`
(``composition-service-no-parallel-write-path``): none of them open a
:class:`~aeat.adapters.persistence.storage.SecureObjectRepository` write path
of their own for the recipient registry, the encryption primitives, or the
review-package build/verify layer -- those already own their persistence.
This module's only write is the bucket-event-history append.

Payloads never carry secret key material or decrypted package bytes -- only
identifiers (recipient id, public-key fingerprint, revision id, bucket id)
and small disposition flags (``review_only``), matching the existing
bucket-event payload convention (short strings, no credentials).

See Also:
    :mod:`aeat.application.modelo._review_package_recipient_registry`
        Owns the recipient-fingerprint registry this module's
        register/remove events describe.
    :mod:`aeat.application.modelo._review_package_recipient_encryption`
        Owns the encrypt/decrypt primitives this module's package events
        describe.
    :mod:`aeat.application.modelo._review_package_review_only_workspace`
        Owns the review-only workspace this module's workspace-opened event
        describes.
    :mod:`aeat.application.modelo._review_package_counter_sign`
        Owns the counter-sign primitive this module's counter-signed event
        describes.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from ...core.time import now as _utc_now
from ...domain.buckets import BucketEventObjectType, BucketEventType
from ._review_package_recipient_registry import RecipientFingerprintRecord
from ._review_package_review_only_workspace import ReviewOnlyWorkspace
from ._revision_persistence import emit_bucket_event

if TYPE_CHECKING:
    from ...domain.buckets import BucketEvent, BucketEventHistoryRepositoryProtocol
    from ._review_package_counter_sign import CounterSignedReceipt
    from ._review_package_recipient_encryption import RecipientEncryptedPackage


def emit_collab_recipient_registered_event(
    record: RecipientFingerprintRecord,
    *,
    bucket_id: str,
    repository: BucketEventHistoryRepositoryProtocol,
    actor: str = "operator",
    occurred_at: datetime | None = None,
) -> BucketEvent:
    """Append a ``COLLAB_RECIPIENT_REGISTERED`` event for a newly-trusted recipient.

    Args:
        record: The :class:`~aeat.application.modelo.RecipientFingerprintRecord`
            just added to the fingerprint registry.
        bucket_id: The bucket the registry entry was added to.
        repository: The bucket's
            :class:`~aeat.domain.buckets.BucketEventHistoryRepositoryProtocol`.
        actor: Actor label (see :func:`~aeat.domain.buckets.BucketEvent`).
        occurred_at: Optional override for the event's ``occurred_at``
            timestamp (tests only); defaults to the current UTC time.
    """
    return emit_bucket_event(
        repository=repository,
        bucket_id=bucket_id,
        event_type=BucketEventType.COLLAB_RECIPIENT_REGISTERED,
        occurred_at=occurred_at or _utc_now(),
        actor=actor,
        object_type=BucketEventObjectType.RECIPIENT,
        object_id=record.recipient_id,
        payload={
            "recipient_id": record.recipient_id,
            "label": record.label,
            "fingerprint_sha256": record.fingerprint_sha256,
        },
    )


def emit_collab_recipient_removed_event(
    *,
    recipient_id: str,
    bucket_id: str,
    repository: BucketEventHistoryRepositoryProtocol,
    actor: str = "operator",
    occurred_at: datetime | None = None,
) -> BucketEvent:
    """Append a ``COLLAB_RECIPIENT_REMOVED`` event for a revoked recipient.

    Args:
        recipient_id: The removed record's ``recipient_id``.
        bucket_id: The bucket the registry entry was removed from.
        repository: The bucket's
            :class:`~aeat.domain.buckets.BucketEventHistoryRepositoryProtocol`.
        actor: Actor label.
        occurred_at: Optional override for the event's ``occurred_at``
            timestamp (tests only); defaults to the current UTC time.
    """
    return emit_bucket_event(
        repository=repository,
        bucket_id=bucket_id,
        event_type=BucketEventType.COLLAB_RECIPIENT_REMOVED,
        occurred_at=occurred_at or _utc_now(),
        actor=actor,
        object_type=BucketEventObjectType.RECIPIENT,
        object_id=recipient_id,
        payload={"recipient_id": recipient_id},
    )


def emit_collab_package_encrypted_event(
    envelope: RecipientEncryptedPackage,
    *,
    bucket_id: str,
    repository: BucketEventHistoryRepositoryProtocol,
    actor: str = "operator",
    occurred_at: datetime | None = None,
) -> BucketEvent:
    """Append a ``COLLAB_PACKAGE_ENCRYPTED_FOR_RECIPIENT`` event.

    Recorded on the SENDER's bucket (the taxpayer sealing the package): a
    trust/transport-boundary action, not a disclosure of decrypted material,
    hence ``collab_event.*`` rather than ``privacy_event.*``.

    Args:
        envelope: The :class:`~aeat.application.modelo.RecipientEncryptedPackage`
            just produced by
            :func:`~aeat.application.modelo.encrypt_review_package_for_recipient`.
        bucket_id: The sender's bucket.
        repository: The bucket's
            :class:`~aeat.domain.buckets.BucketEventHistoryRepositoryProtocol`.
        actor: Actor label.
        occurred_at: Optional override for the event's ``occurred_at``
            timestamp (tests only); defaults to the current UTC time.
    """
    return emit_bucket_event(
        repository=repository,
        bucket_id=bucket_id,
        event_type=BucketEventType.COLLAB_PACKAGE_ENCRYPTED_FOR_RECIPIENT,
        occurred_at=occurred_at or _utc_now(),
        actor=actor,
        object_type=BucketEventObjectType.RECIPIENT,
        object_id=envelope.recipient_public_key_hex,
        payload={
            "recipient_public_key_hex": envelope.recipient_public_key_hex,
            "envelope_nonce_hex": envelope.envelope_nonce_hex,
            "review_only": "true" if envelope.review_only else "false",
            "expires": "true" if envelope.valid_until is not None else "false",
        },
    )


def emit_collab_package_decrypted_event(
    envelope: RecipientEncryptedPackage,
    *,
    bucket_id: str,
    repository: BucketEventHistoryRepositoryProtocol,
    actor: str = "operator",
    occurred_at: datetime | None = None,
) -> BucketEvent:
    """Append a ``COLLAB_PACKAGE_DECRYPTED`` event.

    Recorded on the RECIPIENT's bucket after a successful
    :func:`~aeat.application.modelo.decrypt_review_package_for_recipient`
    call: decrypted package bytes were read, so this is a
    ``privacy_event.*``-prefixed disclosure event, not a bare
    ``collab_event.*`` transport event.

    Args:
        envelope: The :class:`~aeat.application.modelo.RecipientEncryptedPackage`
            that was just successfully decrypted.
        bucket_id: The recipient's own bucket.
        repository: The bucket's
            :class:`~aeat.domain.buckets.BucketEventHistoryRepositoryProtocol`.
        actor: Actor label.
        occurred_at: Optional override for the event's ``occurred_at``
            timestamp (tests only); defaults to the current UTC time.
    """
    return emit_bucket_event(
        repository=repository,
        bucket_id=bucket_id,
        event_type=BucketEventType.COLLAB_PACKAGE_DECRYPTED,
        occurred_at=occurred_at or _utc_now(),
        actor=actor,
        object_type=BucketEventObjectType.RECIPIENT,
        object_id=envelope.recipient_public_key_hex,
        payload={
            "recipient_public_key_hex": envelope.recipient_public_key_hex,
            "envelope_nonce_hex": envelope.envelope_nonce_hex,
            "review_only": "true" if envelope.review_only else "false",
        },
    )


def emit_collab_review_only_workspace_opened_event(
    workspace: ReviewOnlyWorkspace,
    *,
    bucket_id: str,
    repository: BucketEventHistoryRepositoryProtocol,
    actor: str = "operator",
    occurred_at: datetime | None = None,
) -> BucketEvent:
    """Append a ``COLLAB_REVIEW_ONLY_WORKSPACE_OPENED`` event.

    A ``privacy_event.*``-prefixed disclosure event: opening the workspace
    makes the decrypted review-package contents readable to the caller.

    Args:
        workspace: The :class:`~aeat.application.modelo.ReviewOnlyWorkspace`
            just materialised by
            :func:`~aeat.application.modelo.open_review_only_workspace`.
        bucket_id: The bucket the workspace was opened in.
        repository: The bucket's
            :class:`~aeat.domain.buckets.BucketEventHistoryRepositoryProtocol`.
        actor: Actor label.
        occurred_at: Optional override for the event's ``occurred_at``
            timestamp (tests only); defaults to the current UTC time.
    """
    return emit_bucket_event(
        repository=repository,
        bucket_id=bucket_id,
        event_type=BucketEventType.COLLAB_REVIEW_ONLY_WORKSPACE_OPENED,
        occurred_at=occurred_at or _utc_now(),
        actor=actor,
        object_type=BucketEventObjectType.CALCULATION_REVISION,
        object_id=workspace.manifest.calculation_revision_id,
        payload={
            "calculation_revision_id": workspace.manifest.calculation_revision_id,
            "work_unit_id": workspace.manifest.work_unit_id,
            "modelo": workspace.manifest.modelo,
            "review_only": "true" if workspace.review_only else "false",
        },
    )


def emit_collab_package_counter_signed_event(
    receipt: CounterSignedReceipt,
    *,
    bucket_id: str,
    repository: BucketEventHistoryRepositoryProtocol,
    actor: str = "operator",
    occurred_at: datetime | None = None,
) -> BucketEvent:
    """Append a ``COLLAB_PACKAGE_COUNTER_SIGNED`` event.

    Recorded on the counter-signer's (accountant's) bucket after
    :func:`~aeat.application.modelo.counter_sign_review_package`: a
    trust/transport-boundary action (attesting to a signature already
    received), hence ``collab_event.*``.

    Args:
        receipt: The :class:`~aeat.application.modelo.CounterSignedReceipt`
            just produced.
        bucket_id: The counter-signer's own bucket.
        repository: The bucket's
            :class:`~aeat.domain.buckets.BucketEventHistoryRepositoryProtocol`.
        actor: Actor label.
        occurred_at: Optional override for the event's ``occurred_at``
            timestamp (tests only); defaults to the current UTC time.
    """
    return emit_bucket_event(
        repository=repository,
        bucket_id=bucket_id,
        event_type=BucketEventType.COLLAB_PACKAGE_COUNTER_SIGNED,
        occurred_at=occurred_at or _utc_now(),
        actor=actor,
        object_type=BucketEventObjectType.RECIPIENT,
        object_id=receipt.counter_public_key_hex,
        payload={
            "counter_public_key_hex": receipt.counter_public_key_hex,
            "operator_signature_hex": receipt.original_signature.signature_hex,
            "has_note": "true" if receipt.note else "false",
        },
    )


__all__ = [
    "emit_collab_package_counter_signed_event",
    "emit_collab_package_decrypted_event",
    "emit_collab_package_encrypted_event",
    "emit_collab_recipient_registered_event",
    "emit_collab_recipient_removed_event",
    "emit_collab_review_only_workspace_opened_event",
]
