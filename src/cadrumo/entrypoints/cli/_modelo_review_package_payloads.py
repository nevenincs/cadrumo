"""Review-package build/verify CLI payload schemas.

Strict :class:`~core.json_contract.OutputSchema` subclasses referenced
as deferred public schema targets through production-authored CommandSpec for the ``aeat app
modelo review-package build`` and ``aeat app modelo review-package verify``
verbs. Kept in its own module (mirroring the ``_modelo_aux_payloads`` split
for the evidence-bundle audit payloads) so the review-package CLI surface has
one dedicated payload home.

See Also:
    :mod:`~entrypoints.cli._modelo_review_package_cli`
        CLI transport that populates these result payloads.
    :func:`~application.modelo.build_review_package`
        Application build primitive represented by
        :class:`ModeloReviewPackageBuildResult`.
    :func:`~application.modelo.sign_review_package`
        Application signing primitive represented by
        :class:`ModeloReviewPackageSignResult`.
    :func:`~application.modelo.encrypt_review_package_for_recipient`
        Recipient-sealing primitive represented by
        :class:`ModeloReviewPackageEncryptForRecipientResult`.
    :func:`~application.modelo.import_feedback_package`
        Feedback-import primitive represented by
        :class:`ModeloReviewPackageImportFeedbackResult`.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from ...core import Hex64Str, Period
from ...core.filing_year import FilingYear
from ...core.identity import BucketId, CalculationRevisionId, WorkUnitId
from ...core.json_contract import OutputSchema
from ...core.text_bounds import NonEmptyStr, PositiveCount


class ModeloReviewPackageBuildResult(OutputSchema):
    """Review-package build result (path reference only — no raw bytes in envelope).

    Identity, count, and timestamp fields mirror
    :class:`~cadrumo.application.modelo.ReviewPackageManifest` /
    :class:`~cadrumo.application.modelo.ReviewPackageBuildResult` so a
    malformed manifest field is refused at the CLI boundary too.
    """

    operation: str = "modelo.review_package.build"
    bucket_id: BucketId
    work_unit_id: WorkUnitId
    calculation_revision_id: CalculationRevisionId
    modelo: str = Field(min_length=1, max_length=8)
    filing_year: FilingYear
    period: Period
    revision_state: NonEmptyStr
    has_ledger_evidence: bool
    output_path: str
    member_count: PositiveCount
    built_by: str = Field(min_length=1, max_length=128)
    built_at: datetime


class ModeloReviewPackageVerifyResult(OutputSchema):
    """Review-package integrity-verification result.

    ``is_clean`` summarises ``missing`` / ``unexpected`` / ``mismatched``
    (empty across all three iff clean). This is an INTEGRITY check only —
    it does not assert who built the package; cryptographic signing and
    counter-sign verification are surfaced by the sibling ``sign`` /
    ``verify-signature`` / ``counter-sign`` / ``verify-receipt`` verbs.
    Identity and timestamp fields mirror
    :class:`~cadrumo.application.modelo.ReviewPackageManifest`.
    """

    operation: str = "modelo.review_package.verify"
    package_path: str
    is_clean: bool
    missing: list[str]
    unexpected: list[str]
    mismatched: list[str]
    bucket_id: BucketId
    work_unit_id: WorkUnitId
    calculation_revision_id: CalculationRevisionId
    modelo: str = Field(min_length=1, max_length=8)
    filing_year: FilingYear
    period: Period
    revision_state: NonEmptyStr
    has_ledger_evidence: bool
    built_by: str = Field(min_length=1, max_length=128)
    built_at: datetime


class ModeloReviewPackageSignResult(OutputSchema):
    """Review-package signing result.

    Carries only the exportable public half of the signer's keypair and the
    path to the written signature envelope — the private key never appears
    in this payload (it stays inside the encrypted per-bucket keystore; see
    :func:`~application.modelo.ensure_review_package_signing_keypair`).
    Identity, digest, and timestamp fields mirror
    :class:`~cadrumo.application.modelo.SignedReviewPackage`.
    """

    operation: str = "modelo.review_package.sign"
    package_path: str
    signature_path: str
    bucket_id: BucketId
    calculation_revision_id: CalculationRevisionId
    manifest_sha256: Hex64Str
    signer_public_key_hex: Hex64Str
    signed_at: datetime


class ModeloReviewPackageVerifySignatureResult(OutputSchema):
    """Review-package Ed25519 signature-verification result (authenticity check)."""

    operation: str = "modelo.review_package.verify_signature"
    package_path: str
    signature_path: str
    signer_public_key_hex: Hex64Str
    is_valid: bool


class ModeloReviewPackageCounterSignResult(OutputSchema):
    """Review-package accountant counter-sign result.

    Carries only the exportable public half of the counter-signer's keypair
    and the path to the written receipt envelope — the private key never
    appears in this payload. Digest and timestamp fields mirror
    :class:`~cadrumo.application.modelo.CounterSignedReceipt`.
    """

    operation: str = "modelo.review_package.counter_sign"
    package_path: str
    signature_path: str
    receipt_path: str
    bucket_id: BucketId
    note: str = Field(default="", max_length=2000)
    counter_signer_public_key_hex: Hex64Str
    counter_signed_at: datetime


class ModeloReviewPackageVerifyReceiptResult(OutputSchema):
    """Review-package counter-signed receipt verification result (both layers)."""

    operation: str = "modelo.review_package.verify_receipt"
    package_path: str
    receipt_path: str
    operator_public_key_hex: Hex64Str
    counter_signer_public_key_hex: Hex64Str
    is_valid: bool


class ModeloReviewPackageEncryptForRecipientResult(OutputSchema):
    """Review-package encrypt-for-recipient result.

    The private ephemeral sender key never appears in this payload (it exists
    only transiently in process memory for the duration of the call, per
    :func:`~application.modelo.encrypt_review_package_for_recipient`).
    ``valid_until`` is ``None`` when the sealed package never expires.
    Timestamp fields mirror
    :class:`~cadrumo.application.modelo.RecipientEncryptedPackage`.
    """

    operation: str = "modelo.review_package.encrypt_for_recipient"
    package_path: str
    output_path: str
    recipient_id: NonEmptyStr
    recipient_public_key_hex: Hex64Str
    review_only: bool
    issued_at: datetime
    valid_until: datetime | None = None


class ModeloReviewPackageDecryptResult(OutputSchema):
    """Review-package decrypt (recipient side) result.

    The recipient's own private key never appears in this payload (it is
    minted-or-loaded from encrypted secure storage and used only transiently
    to decrypt, per
    :func:`~application.modelo.ensure_recipient_encryption_keypair`).
    ``review_only`` asserts the recovered package carries no filing authority
    -- see :func:`~application.modelo.decrypt_review_package_for_recipient`.
    """

    operation: str = "modelo.review_package.decrypt"
    envelope_path: str
    output_path: str
    bucket_id: BucketId
    review_only: bool


class ModeloReviewPackageEncryptFeedbackResult(OutputSchema):
    """Feedback-package encrypt (recipient side) result.

    The recipient (accountant/gestor) seals structured feedback back to the
    originator (taxpayer) so only the originator's private key can open it,
    reusing the same X25519 ECIES construction as the forward direction (see
    :func:`~application.modelo.encrypt_feedback_package_for_originator`).
    Only the exportable originator public key appears here; no private key of
    either party is ever surfaced. ``has_counter_sign`` reports whether a
    counter-signed receipt was bundled with the note. Identity and timestamp
    fields mirror :class:`~cadrumo.application.modelo.RecipientEncryptedPackage`.
    """

    operation: str = "modelo.review_package.encrypt_feedback"
    output_path: str
    originator_id: NonEmptyStr
    originator_public_key_hex: Hex64Str
    work_unit_id: WorkUnitId
    calculation_revision_id: CalculationRevisionId
    has_counter_sign: bool
    issued_at: datetime
    valid_until: datetime | None = None


class ModeloReviewPackageImportFeedbackResult(OutputSchema):
    """Feedback-package import (originator side) result.

    The originator mints-or-loads their own X25519 keypair to decrypt the
    feedback envelope, and -- when the feedback carries a counter-signed
    receipt -- re-verifies BOTH signature layers against their locally-held
    review-package archive before accepting it and attaching the verified
    countersignature to their own approval journal
    (:func:`~application.modelo.import_feedback_package`,
    :func:`~application.modelo.emit_collab_feedback_countersign_attached_event`).
    No private key of either party appears in this payload.
    ``counter_signature_verified`` is ``None`` when the feedback carried no
    formal sign-off, ``True`` when a bundled receipt verified clean. Identity
    fields mirror :class:`~cadrumo.application.modelo.FeedbackPackage`.
    """

    operation: str = "modelo.review_package.import_feedback"
    envelope_path: str
    bucket_id: BucketId
    work_unit_id: WorkUnitId
    calculation_revision_id: CalculationRevisionId
    note: str = Field(default="", max_length=4000)
    submitted_by: str = Field(min_length=1, max_length=128)
    counter_signature_verified: bool | None = None
    attached_to_journal: bool = False


__all__ = [
    "ModeloReviewPackageBuildResult",
    "ModeloReviewPackageCounterSignResult",
    "ModeloReviewPackageDecryptResult",
    "ModeloReviewPackageEncryptFeedbackResult",
    "ModeloReviewPackageEncryptForRecipientResult",
    "ModeloReviewPackageImportFeedbackResult",
    "ModeloReviewPackageSignResult",
    "ModeloReviewPackageVerifyReceiptResult",
    "ModeloReviewPackageVerifyResult",
    "ModeloReviewPackageVerifySignatureResult",
]
