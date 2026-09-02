"""Bucket-event audit-tag emission for the accountant/gestor collaboration surface.

Every trust-boundary crossing on the review-package recipient-encryption
surface -- registering or removing a trusted recipient, sealing a package for
a recipient, decrypting a sealed package, opening a review-only workspace,
and counter-signing a received package -- emits a typed
:class:`~domain.buckets.BucketEvent` so an operator can reconstruct the
collaboration timeline from the bucket-event-history catalogue, mirroring
every other material workflow transition in the codebase (the pattern
established by ``_iva_wallet_seed.py`` and ``_revision_persistence.py``).

Two distinct event-name prefixes are used, per the enum's own grouping
comment: ``collab_event.*`` marks a TRUST/TRANSPORT-boundary action (adding a
recipient, sealing a package for them) that does not itself expose decrypted
material to the caller emitting the event; ``privacy_event.*`` marks a
DISCLOSURE-relevant action where decrypted or otherwise sensitive material
was read (decrypting a package, opening a review-only workspace). This lets
a future audit query distinguish "who was trusted / what was sealed" from
"what was actually read".

Every function in this module is a thin, pure composition over
:func:`~application.modelo.revision_persistence.emit_modelo_bucket_event`
(``aeat-architecture-boundaries``): none of them open a
:class:`~adapters.persistence.storage.SecureObjectRepository` write path
of their own for the recipient registry, the encryption primitives, or the
review-package build/verify layer -- those already own their persistence.
This module's only write is the bucket-event-history append.

Payloads never carry secret key material or decrypted package bytes -- only
identifiers (recipient id, public-key fingerprint, revision id, bucket id)
and small disposition flags (``review_only``), matching the existing
bucket-event payload convention (short strings, no credentials).

:func:`emit_collab_feedback_countersign_attached_event` records,
on the ORIGINATOR's own bucket, that a recipient's counter-signed receipt
(recovered from an imported
:class:`~application.modelo.FeedbackPackage`, see
:mod:`~application.modelo.review_package_feedback`) was verified and
attached to the originator's approval journal -- the mirror image of
:func:`emit_collab_package_counter_signed_event`, which records the
counter-signer's OWN act of signing on their bucket. Reuses the same
``COLLAB_PACKAGE_COUNTER_SIGNED`` event type (no new
:class:`~domain.buckets.BucketEventType` member): the enum member names
the FACT that a counter-signature exists for a package, not which party's
bucket recorded it, exactly as ``COLLAB_PACKAGE_DECRYPTED`` already serves
both the forward (accountant decrypts the original package) and reverse (the
originator decrypts a feedback package) directions.

See Also:
    :mod:`~application.modelo._review_package_recipient_registry`
        Owns the recipient-fingerprint registry this module's
        register/remove events describe.
    :mod:`~application.modelo._review_package_recipient_encryption`
        Owns the encrypt/decrypt primitives this module's package events
        describe.
    :mod:`~application.modelo._review_package_review_only_workspace`
        Owns the review-only workspace this module's workspace-opened event
        describes.
    :mod:`~application.modelo._review_package_counter_sign`
        Owns the counter-sign primitive this module's counter-signed event
        describes.
    :mod:`~application.modelo.review_package_feedback`
        Owns the feedback-package round trip whose imported counter-signed
        receipt :func:`emit_collab_feedback_countersign_attached_event`
        attaches to the originator's journal.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from ...core.time.clock import now as _utc_now
from ...domain.buckets.event import BucketEventObjectType, BucketEventType
from ._review_package_review_only_workspace import ReviewOnlyWorkspace
from .review_package_recipient_registry import RecipientFingerprintRecord
from .revision_persistence import emit_modelo_bucket_event

if TYPE_CHECKING:
    from ...domain.buckets.event import BucketEvent
    from ...domain.buckets.protocols import BucketEventHistoryRepositoryProtocol
    from .review_package_counter_sign import CounterSignedReceipt
    from .review_package_feedback import ImportedFeedback
    from .review_package_recipient_encryption import RecipientEncryptedPackage


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
        record: The :class:`~application.modelo.RecipientFingerprintRecord`
            just added to the fingerprint registry.
        bucket_id: The bucket the registry entry was added to.
        repository: The bucket's
            :class:`~domain.buckets.BucketEventHistoryRepositoryProtocol`.
        actor: Actor label (see :class:`~domain.buckets.BucketEvent`).
        occurred_at: Optional override for the event's ``occurred_at``
            timestamp (tests only); defaults to the current UTC time.
    """
    return emit_modelo_bucket_event(
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
            :class:`~domain.buckets.BucketEventHistoryRepositoryProtocol`.
        actor: Actor label.
        occurred_at: Optional override for the event's ``occurred_at``
            timestamp (tests only); defaults to the current UTC time.
    """
    return emit_modelo_bucket_event(
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
        envelope: The :class:`~application.modelo.RecipientEncryptedPackage`
            just produced by
            :func:`~application.modelo.encrypt_review_package_for_recipient`.
        bucket_id: The sender's bucket.
        repository: The bucket's
            :class:`~domain.buckets.BucketEventHistoryRepositoryProtocol`.
        actor: Actor label.
        occurred_at: Optional override for the event's ``occurred_at``
            timestamp (tests only); defaults to the current UTC time.
    """
    return emit_modelo_bucket_event(
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
    :func:`~application.modelo.decrypt_review_package_for_recipient`
    call: decrypted package bytes were read, so this is a
    ``privacy_event.*``-prefixed disclosure event, not a bare
    ``collab_event.*`` transport event.

    Args:
        envelope: The :class:`~application.modelo.RecipientEncryptedPackage`
            that was just successfully decrypted.
        bucket_id: The recipient's own bucket.
        repository: The bucket's
            :class:`~domain.buckets.BucketEventHistoryRepositoryProtocol`.
        actor: Actor label.
        occurred_at: Optional override for the event's ``occurred_at``
            timestamp (tests only); defaults to the current UTC time.
    """
    return emit_modelo_bucket_event(
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
        workspace: The :class:`~application.modelo.ReviewOnlyWorkspace`
            just materialised by
            :func:`~application.modelo.open_review_only_workspace`.
        bucket_id: The bucket the workspace was opened in.
        repository: The bucket's
            :class:`~domain.buckets.BucketEventHistoryRepositoryProtocol`.
        actor: Actor label.
        occurred_at: Optional override for the event's ``occurred_at``
            timestamp (tests only); defaults to the current UTC time.
    """
    return emit_modelo_bucket_event(
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
    :func:`~application.modelo.counter_sign_review_package`: a
    trust/transport-boundary action (attesting to a signature already
    received), hence ``collab_event.*``.

    Args:
        receipt: The :class:`~application.modelo.CounterSignedReceipt`
            just produced.
        bucket_id: The counter-signer's own bucket.
        repository: The bucket's
            :class:`~domain.buckets.BucketEventHistoryRepositoryProtocol`.
        actor: Actor label.
        occurred_at: Optional override for the event's ``occurred_at``
            timestamp (tests only); defaults to the current UTC time.
    """
    return emit_modelo_bucket_event(
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


def emit_collab_feedback_countersign_attached_event(
    imported: ImportedFeedback,
    *,
    bucket_id: str,
    repository: BucketEventHistoryRepositoryProtocol,
    actor: str = "operator",
    occurred_at: datetime | None = None,
) -> BucketEvent:
    """Append a ``COLLAB_PACKAGE_COUNTER_SIGNED`` event to the ORIGINATOR's journal.

    Recorded on the originator's OWN bucket after
    :func:`~application.modelo.import_feedback_package` has already
    verified the imported feedback's
    :class:`~application.modelo.CounterSignedReceipt` (i.e.
    ``imported.counter_signature_verified`` is ``True``): the countersigned
    approval is now attached to the originator's approval journal, closing
    the collaboration round trip. Reuses ``COLLAB_PACKAGE_COUNTER_SIGNED``
    (see module docstring) rather than minting a new event type -- the same
    fact, recorded from the other party's bucket.

    Args:
        imported: The :class:`~application.modelo.ImportedFeedback`
            returned by
            :func:`~application.modelo.import_feedback_package`. Must
            carry a verified counter-signed receipt
            (``counter_signature_verified is True``); calling this with
            unverified or absent feedback is a caller error, not a runtime
            state this function silently tolerates.
        bucket_id: The originator's own bucket.
        repository: The bucket's
            :class:`~domain.buckets.BucketEventHistoryRepositoryProtocol`.
        actor: Actor label.
        occurred_at: Optional override for the event's ``occurred_at``
            timestamp (tests only); defaults to the current UTC time.

    Raises:
        ValueError: If ``imported.feedback.counter_signed_receipt`` is
            ``None`` or ``imported.counter_signature_verified`` is not
            ``True`` -- attaching an unverified or absent countersignature
            to the journal would misrepresent the collaboration record.
    """
    receipt = imported.feedback.counter_signed_receipt
    if receipt is None or imported.counter_signature_verified is not True:
        raise ValueError(
            "cannot attach an unverified or absent counter-signed receipt to the journal; "
            "import_feedback_package must report counter_signature_verified=True first",
        )
    return emit_modelo_bucket_event(
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
            "calculation_revision_id": imported.feedback.calculation_revision_id,
            "work_unit_id": imported.feedback.work_unit_id,
        },
    )


__all__ = [
    "emit_collab_feedback_countersign_attached_event",
    "emit_collab_package_counter_signed_event",
    "emit_collab_package_decrypted_event",
    "emit_collab_package_encrypted_event",
    "emit_collab_recipient_registered_event",
    "emit_collab_recipient_removed_event",
    "emit_collab_review_only_workspace_opened_event",
]
