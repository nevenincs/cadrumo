"""Recipient feedback-package round trip: reviewer notes back to the originator.

The recipient (accountant/gestor) who received a review package via
:func:`~application.modelo.encrypt_review_package_for_recipient` /
:func:`~application.modelo.decrypt_review_package_for_recipient` now has a
SYMMETRIC path back to the originator (the taxpayer) -- a small structured
``FeedbackPackage`` (a verdict note plus an optional
:class:`~application.modelo.CounterSignedReceipt`) sealed with the EXACT
SAME X25519 ECIES construction, re-encrypted FOR THE ORIGINATOR rather than for
the accountant.

This module invents no new cryptography
(``aeat-architecture-boundaries`` /
``sensitive-financial-data-secure-storage-only``): both
:func:`encrypt_feedback_package_for_originator` and
:func:`decrypt_feedback_package_from_originator_envelope` are thin
serialise-then-delegate / delegate-then-parse wrappers around
:func:`~application.modelo.encrypt_review_package_for_recipient` and
:func:`~application.modelo.decrypt_review_package_for_recipient` -- the
"recipient" of a feedback package is simply the ORIGINATOR's own encryption
keypair (the same :func:`~application.modelo.ensure_recipient_encryption_keypair`
primitive the accountant used for the forward direction, minted for the
taxpayer instead), and the "package bytes" being sealed are a small JSON
document rather than a review-package ZIP. Every expiry, replay-nonce, and
review-only mechanic the forward direction already proves therefore composes
for free on the return trip.

Import composition (:func:`import_feedback_package`) ties the whole round trip
together for the originator: decrypt the envelope, parse the
:class:`FeedbackPackage`, and -- when the feedback carries a
:class:`~application.modelo.CounterSignedReceipt` -- verify BOTH signature
layers against the local review-package archive bytes the originator already
holds (via :func:`~application.modelo.verify_counter_signed_receipt`)
before accepting it. A tampered feedback package, a wrong originator key, or an
invalid/forged countersignature refuse loudly rather than silently importing
unverified feedback (``no-silent-under-declaration``'s spirit applied to
collaboration integrity: an unverifiable countersignature is not evidence of
review).

See Also:
    :mod:`~application.modelo._review_package_recipient_encryption`
        Owns the X25519 ECIES primitive this module reuses verbatim, in both
        directions.
    :mod:`~application.modelo._review_package_counter_sign`
        Owns the counter-signed receipt this module's feedback optionally
        carries and verifies on import.
    :mod:`~application.modelo._review_package_collab_audit`
        Owns the bucket-event audit-tag emission this module's import
        composition appends to the originator's journal.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.errors.hierarchy import CadrumoError
from ...core.external_constants import UTF_8_ENCODING as _UTF_8_ENCODING
from ...core.identity import BucketId, CalculationRevisionId, WorkUnitId
from ...core.time import UtcInstant
from ...core.time import now as _utc_now
from ._review_package_counter_sign import CounterSignedReceipt, verify_counter_signed_receipt
from ._review_package_recipient_encryption import (
    RecipientDecryptedPackage,
    RecipientEncryptedPackage,
    decrypt_review_package_for_recipient,
    encrypt_review_package_for_recipient,
)

if TYPE_CHECKING:
    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

#: Wire-format version of the feedback-package document. Bumped when the
#: document schema changes shape.
_FEEDBACK_PACKAGE_VERSION = 1


class ReviewPackageFeedbackError(CadrumoError):
    """Base error for review-package feedback round-trip failures."""


class FeedbackCounterSignatureInvalidError(ReviewPackageFeedbackError):
    """Raised when an imported feedback package's counter-signed receipt fails verification.

    Covers a tampered original signature, a tampered or forged
    counter-signature, an edited note, or an archive that no longer matches
    the receipt's original signature -- never distinguished further, mirroring
    the undifferentiated-failure posture of
    :class:`~application.modelo.RecipientDecryptionError`.
    """


class FeedbackPackage(BaseModel):
    """A recipient's structured feedback, sealed and returned to the originator.

    Wraps a free-text verdict/note plus an OPTIONAL
    :class:`~application.modelo.CounterSignedReceipt` -- a recipient may
    return unstructured feedback alone (``counter_signed_receipt=None``, e.g.
    "see attached corrections, no formal sign-off yet") or a fully
    counter-signed approval. The identifiers (``bucket_id``,
    ``work_unit_id``, ``calculation_revision_id``) are carried verbatim from
    the :class:`~application.modelo.ReviewPackageManifest` the recipient
    reviewed, so the originator can address the feedback to the correct
    work unit / revision without re-parsing the original archive.

    This model is the PLAINTEXT document sealed by
    :func:`encrypt_feedback_package_for_originator` -- it is never persisted
    directly; only the resulting
    :class:`~application.modelo.RecipientEncryptedPackage` envelope is
    written to disk by the caller.
    """

    model_config = _STRICT_FROZEN

    feedback_version: int = Field(default=_FEEDBACK_PACKAGE_VERSION, ge=1)
    bucket_id: BucketId
    work_unit_id: WorkUnitId
    calculation_revision_id: CalculationRevisionId
    note: str = Field(default="", max_length=4000)
    counter_signed_receipt: CounterSignedReceipt | None = Field(default=None)
    submitted_at: UtcInstant
    submitted_by: str = Field(min_length=1, max_length=128)


def build_feedback_package(
    *,
    bucket_id: BucketId,
    work_unit_id: WorkUnitId,
    calculation_revision_id: CalculationRevisionId,
    note: str = "",
    counter_signed_receipt: CounterSignedReceipt | None = None,
    submitted_by: str,
    submitted_at: datetime | None = None,
) -> FeedbackPackage:
    """Build a :class:`FeedbackPackage` document, no I/O.

    Args:
        bucket_id: The originator's bucket the reviewed package was built
            from (from :class:`~application.modelo.ReviewPackageManifest`).
        work_unit_id: The reviewed work unit's id.
        calculation_revision_id: The reviewed calculation revision's id.
        note: Free-text verdict or note (e.g. ``"reviewed, no changes"`` or
            ``"see attached corrections"``).
        counter_signed_receipt: Optional
            :class:`~application.modelo.CounterSignedReceipt` produced by
            :func:`~application.modelo.counter_sign_review_package`, when
            the recipient formally counter-signed the operator's original
            signature. ``None`` for unstructured feedback with no formal
            sign-off.
        submitted_by: The recipient's actor label (e.g. an accountant's
            display name).
        submitted_at: Optional override for the document's ``submitted_at``
            timestamp (tests only); defaults to the current UTC time.
    """
    return FeedbackPackage(
        bucket_id=bucket_id,
        work_unit_id=work_unit_id,
        calculation_revision_id=calculation_revision_id,
        note=note,
        counter_signed_receipt=counter_signed_receipt,
        submitted_at=submitted_at or _utc_now(),
        submitted_by=submitted_by,
    )


def encrypt_feedback_package_for_originator(
    feedback: FeedbackPackage,
    *,
    originator_public_key_hex: str,
    review_only: bool = False,
    valid_for: timedelta | None = None,
    issued_at: datetime | None = None,
) -> RecipientEncryptedPackage:
    """Seal ``feedback`` so only the originator's private key can open it.

    A thin serialise-then-delegate wrapper: the recipient's feedback document
    is dumped to canonical JSON bytes and sealed via the EXACT SAME
    :func:`~application.modelo.encrypt_review_package_for_recipient`
    ECIES construction used for the forward (originator-to-recipient)
    direction -- no new cryptographic primitive is introduced for this
    reverse direction. The "recipient" of this call is the originator's own
    encryption public key (see
    :func:`~application.modelo.recipient_encryption_public_key`, minted
    for the originator via
    :func:`~application.modelo.ensure_recipient_encryption_keypair`,
    exactly as it is minted for an accountant in the forward direction).

    Args:
        feedback: The :class:`FeedbackPackage` document to seal.
        originator_public_key_hex: The originator's raw 32-byte X25519
            public key, hex-encoded.
        review_only: Passed straight through to
            :func:`~application.modelo.encrypt_review_package_for_recipient`;
            a review-only feedback envelope carries no filing authority
            (almost always ``False`` for feedback, but exposed for parity
            with the forward direction).
        valid_for: Optional validity window; see
            :func:`~application.modelo.encrypt_review_package_for_recipient`.
        issued_at: Optional override for the envelope's ``issued_at``
            timestamp (tests only); defaults to the current UTC time.
    """
    feedback_bytes = feedback.model_dump_json().encode(_UTF_8_ENCODING)
    return encrypt_review_package_for_recipient(
        feedback_bytes,
        recipient_public_key_hex=originator_public_key_hex,
        review_only=review_only,
        valid_for=valid_for,
        issued_at=issued_at,
    )


def decrypt_feedback_package_from_originator_envelope(
    envelope: RecipientEncryptedPackage,
    *,
    originator_private_key: X25519PrivateKey,
    now: datetime | None = None,
) -> FeedbackPackage:
    """Reverse :func:`encrypt_feedback_package_for_originator` and parse the document.

    Delegates decryption entirely to
    :func:`~application.modelo.decrypt_review_package_for_recipient`
    (same AEAD authentication, same expiry check, same undifferentiated
    failure posture) and then parses the recovered bytes as a
    :class:`FeedbackPackage`. A tampered envelope, wrong private key, or
    expired envelope raises exactly as the forward direction does; a
    recovered payload that is not valid ``FeedbackPackage`` JSON raises
    :class:`ReviewPackageFeedbackError`.

    Args:
        envelope: The :class:`~application.modelo.RecipientEncryptedPackage`
            produced by :func:`encrypt_feedback_package_for_originator`.
        originator_private_key: The originator's own X25519 private key (see
            :func:`~application.modelo.load_recipient_encryption_keypair`).
        now: The instant to evaluate the envelope's expiry against; defaults
            to the current UTC time (tests inject an explicit value).

    Raises:
        RecipientPackageExpiredError: If the envelope has expired.
        RecipientDecryptionError: If decryption fails for any other reason
            (wrong key, tampered ciphertext).
        ReviewPackageFeedbackError: If the recovered plaintext is not valid
            :class:`FeedbackPackage` JSON.
    """
    decrypted: RecipientDecryptedPackage = decrypt_review_package_for_recipient(
        envelope,
        recipient_private_key=originator_private_key,
        now=now,
    )
    try:
        return FeedbackPackage.model_validate_json(decrypted.package_bytes)
    except ValueError as exc:
        raise ReviewPackageFeedbackError(
            "recovered feedback envelope did not contain a well-formed feedback package",
            translated_message="application.modelo.errors.review_package_generic",
        ) from exc


class ImportedFeedback(BaseModel):
    """Result of :func:`import_feedback_package`: the parsed feedback plus its verification outcome.

    ``counter_signature_verified`` is ``None`` when the feedback carried no
    :class:`~application.modelo.CounterSignedReceipt` (unstructured
    feedback), and a real ``bool`` -- never silently omitted -- when one was
    present, so a caller can distinguish "no formal sign-off was offered"
    from "a sign-off was offered and it verified/failed".
    """

    model_config = _STRICT_FROZEN

    feedback: FeedbackPackage
    counter_signature_verified: bool | None


def import_feedback_package(
    envelope: RecipientEncryptedPackage,
    *,
    originator_private_key: X25519PrivateKey,
    reviewed_package_path: Path,
    operator_public_key_hex: str,
    counter_signer_public_key_hex: str | None = None,
    now: datetime | None = None,
) -> ImportedFeedback:
    """Decrypt, parse, and (when present) verify a recipient's feedback package.

    This is the originator-side composition that ties the whole feedback
    round trip together: decrypt the envelope
    (:func:`decrypt_feedback_package_from_originator_envelope`), and when the
    recovered :class:`FeedbackPackage` carries a
    :class:`~application.modelo.CounterSignedReceipt`, re-verify BOTH
    signature layers against ``reviewed_package_path`` -- the ORIGINAL
    review-package archive the originator built and signed, still held
    locally -- via
    :func:`~application.modelo.verify_counter_signed_receipt`. A feedback
    package with no counter-signed receipt is accepted as unstructured
    feedback with ``counter_signature_verified=None``; one that carries an
    invalid or forged receipt raises rather than silently importing
    unverified sign-off.

    Args:
        envelope: The sealed feedback envelope received from the recipient.
        originator_private_key: The originator's own X25519 private key.
        reviewed_package_path: Path to the ORIGINAL review-package ZIP the
            originator built and (optionally) signed -- required only when
            the feedback carries a counter-signed receipt; unused for
            unstructured feedback.
        operator_public_key_hex: The originator's own Ed25519 signing public
            key (the key the ORIGINAL signature in the receipt must verify
            against).
        counter_signer_public_key_hex: The recipient's Ed25519 signing public
            key the counter-signature must verify against. Required when the
            feedback carries a counter-signed receipt; a receipt present
            without this argument raises.
        now: The instant to evaluate the envelope's expiry against; defaults
            to the current UTC time (tests inject an explicit value).

    Returns:
        An :class:`ImportedFeedback` carrying the parsed feedback and the
        countersignature verification outcome.

    Raises:
        RecipientPackageExpiredError: If the envelope has expired.
        RecipientDecryptionError: If decryption fails for any other reason.
        ReviewPackageFeedbackError: If the recovered plaintext is malformed,
            or if the feedback carries a counter-signed receipt but no
            ``counter_signer_public_key_hex`` was supplied to verify it
            against.
        FeedbackCounterSignatureInvalidError: If the feedback carries a
            counter-signed receipt and it fails verification (tampered
            archive, tampered note, forged/wrong signature on either layer).
    """
    feedback = decrypt_feedback_package_from_originator_envelope(
        envelope,
        originator_private_key=originator_private_key,
        now=now,
    )

    if feedback.counter_signed_receipt is None:
        return ImportedFeedback(feedback=feedback, counter_signature_verified=None)

    if counter_signer_public_key_hex is None:
        raise ReviewPackageFeedbackError(
            "feedback carries a counter-signed receipt but no counter_signer_public_key_hex "
            "was supplied to verify it against",
            translated_message="application.modelo.errors.review_package_generic",
        )

    verified = verify_counter_signed_receipt(
        reviewed_package_path,
        feedback.counter_signed_receipt,
        operator_public_key_hex=operator_public_key_hex,
        counter_signer_public_key_hex=counter_signer_public_key_hex,
    )
    if not verified:
        raise FeedbackCounterSignatureInvalidError(
            "imported feedback's counter-signed receipt failed verification; "
            "the archive, the original signature, the note, or the counter-signature "
            "no longer match",
            translated_message="application.modelo.errors.review_package_generic",
            context={
                "calculation_revision_id": feedback.calculation_revision_id,
                "work_unit_id": feedback.work_unit_id,
            },
        )
    return ImportedFeedback(feedback=feedback, counter_signature_verified=True)


__all__ = [
    "FeedbackCounterSignatureInvalidError",
    "FeedbackPackage",
    "ImportedFeedback",
    "ReviewPackageFeedbackError",
    "build_feedback_package",
    "decrypt_feedback_package_from_originator_envelope",
    "encrypt_feedback_package_for_originator",
    "import_feedback_package",
]
