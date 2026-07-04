"""Review-package build/verify CLI payload schemas.

Strict :class:`OutputSchema` subclasses registered through
:func:`register_schema` for the ``aeat app modelo review-package build`` and
``aeat app modelo review-package verify`` verbs. Kept in its own module
(mirroring the ``_modelo_aux_payloads`` split for the evidence-bundle audit
payloads) so the review-package CLI surface has one dedicated payload home.
"""

from __future__ import annotations

from ...core import Period
from ._schemas import OutputSchema, register_schema


@register_schema("modelo.review_package.build")
class ModeloReviewPackageBuildResult(OutputSchema):
    """Review-package build result (path reference only — no raw bytes in envelope)."""

    operation: str = "modelo.review_package.build"
    bucket_id: str
    work_unit_id: str
    calculation_revision_id: str
    modelo: str
    filing_year: int
    period: Period
    revision_state: str
    has_ledger_evidence: bool
    output_path: str
    member_count: int
    built_by: str
    built_at: str


@register_schema("modelo.review_package.verify")
class ModeloReviewPackageVerifyResult(OutputSchema):
    """Review-package integrity-verification result.

    ``is_clean`` summarises ``missing`` / ``unexpected`` / ``mismatched``
    (empty across all three iff clean). This is an INTEGRITY check only —
    it does not assert who built the package; cryptographic signing and
    counter-sign verification are surfaced by the sibling ``sign`` /
    ``verify-signature`` / ``counter-sign`` / ``verify-receipt`` verbs.
    """

    operation: str = "modelo.review_package.verify"
    package_path: str
    is_clean: bool
    missing: list[str]
    unexpected: list[str]
    mismatched: list[str]
    bucket_id: str
    work_unit_id: str
    calculation_revision_id: str
    modelo: str
    filing_year: int
    period: Period
    revision_state: str
    has_ledger_evidence: bool
    built_by: str
    built_at: str


@register_schema("modelo.review_package.sign")
class ModeloReviewPackageSignResult(OutputSchema):
    """Review-package signing result.

    Carries only the exportable public half of the signer's keypair and the
    path to the written signature envelope — the private key never appears
    in this payload (it stays inside the encrypted per-bucket keystore; see
    :func:`~aeat.application.modelo.ensure_review_package_signing_keypair`).
    """

    operation: str = "modelo.review_package.sign"
    package_path: str
    signature_path: str
    bucket_id: str
    calculation_revision_id: str
    manifest_sha256: str
    signer_public_key_hex: str
    signed_at: str


@register_schema("modelo.review_package.verify_signature")
class ModeloReviewPackageVerifySignatureResult(OutputSchema):
    """Review-package Ed25519 signature-verification result (authenticity check)."""

    operation: str = "modelo.review_package.verify_signature"
    package_path: str
    signature_path: str
    signer_public_key_hex: str
    is_valid: bool


@register_schema("modelo.review_package.counter_sign")
class ModeloReviewPackageCounterSignResult(OutputSchema):
    """Review-package accountant counter-sign result.

    Carries only the exportable public half of the counter-signer's keypair
    and the path to the written receipt envelope — the private key never
    appears in this payload.
    """

    operation: str = "modelo.review_package.counter_sign"
    package_path: str
    signature_path: str
    receipt_path: str
    bucket_id: str
    note: str
    counter_signer_public_key_hex: str
    counter_signed_at: str


@register_schema("modelo.review_package.verify_receipt")
class ModeloReviewPackageVerifyReceiptResult(OutputSchema):
    """Review-package counter-signed receipt verification result (both layers)."""

    operation: str = "modelo.review_package.verify_receipt"
    package_path: str
    receipt_path: str
    operator_public_key_hex: str
    counter_signer_public_key_hex: str
    is_valid: bool


@register_schema("modelo.review_package.encrypt_for_recipient")
class ModeloReviewPackageEncryptForRecipientResult(OutputSchema):
    """Review-package encrypt-for-recipient result.

    The private ephemeral sender key never appears in this payload (it exists
    only transiently in process memory for the duration of the call, per
    :func:`~aeat.application.modelo.encrypt_review_package_for_recipient`).
    ``valid_until`` is ``None`` when the sealed package never expires.
    """

    operation: str = "modelo.review_package.encrypt_for_recipient"
    package_path: str
    output_path: str
    recipient_id: str
    recipient_public_key_hex: str
    review_only: bool
    issued_at: str
    valid_until: str | None = None


@register_schema("modelo.review_package.decrypt")
class ModeloReviewPackageDecryptResult(OutputSchema):
    """Review-package decrypt (recipient side) result.

    The recipient's own private key never appears in this payload (it is
    minted-or-loaded from encrypted secure storage and used only transiently
    to decrypt, per
    :func:`~aeat.application.modelo.ensure_recipient_encryption_keypair`).
    ``review_only`` asserts the recovered package carries no filing authority
    -- see :func:`~aeat.application.modelo.decrypt_review_package_for_recipient`.
    """

    operation: str = "modelo.review_package.decrypt"
    envelope_path: str
    output_path: str
    bucket_id: str
    review_only: bool


__all__ = [
    "ModeloReviewPackageBuildResult",
    "ModeloReviewPackageCounterSignResult",
    "ModeloReviewPackageDecryptResult",
    "ModeloReviewPackageEncryptForRecipientResult",
    "ModeloReviewPackageSignResult",
    "ModeloReviewPackageVerifyReceiptResult",
    "ModeloReviewPackageVerifyResult",
    "ModeloReviewPackageVerifySignatureResult",
]
