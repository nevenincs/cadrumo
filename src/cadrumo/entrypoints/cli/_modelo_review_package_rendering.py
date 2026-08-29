"""Output projection helpers for Modelo review-package CLI commands.

See Also:
    :mod:`~entrypoints.cli._modelo_review_package_cli`
        Typer verb registrar that calls these projection helpers before emitting
        CLI envelopes.
    :mod:`~entrypoints.cli._modelo_review_package_payloads`
        Strict result schemas populated by this module for build, verify,
        signing, recipient encryption, and feedback flows.
    :func:`~application.modelo.build_review_package`
        Application build primitive whose manifest is projected into build
        result payloads and text lines.
    :func:`~application.modelo.sign_review_package`
        Ed25519 authenticity primitive represented by the signing projections.
    :func:`~application.modelo.encrypt_review_package_for_recipient`
        X25519 recipient-sealing primitive represented by encrypt/decrypt
        projections.
    :func:`~application.modelo.import_feedback_package`
        Originator-side feedback import primitive represented by the feedback
        projection.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ...core.identity import CalculationRevisionId
from ._modelo_review_package_payloads import (
    ModeloReviewPackageBuildResult,
    ModeloReviewPackageCounterSignResult,
    ModeloReviewPackageDecryptResult,
    ModeloReviewPackageEncryptFeedbackResult,
    ModeloReviewPackageEncryptForRecipientResult,
    ModeloReviewPackageImportFeedbackResult,
    ModeloReviewPackageSignResult,
    ModeloReviewPackageVerifyReceiptResult,
    ModeloReviewPackageVerifyResult,
    ModeloReviewPackageVerifySignatureResult,
)

if TYPE_CHECKING:
    from ...application.modelo.review_package import (
        ReviewPackageBuildResult,
        ReviewPackageVerification,
    )
    from ...application.modelo._review_package_counter_sign import CounterSignedReceipt
    from ...application.modelo._review_package_feedback import ImportedFeedback
    from ...application.modelo._review_package_recipient_encryption import (
        RecipientDecryptedPackage,
        RecipientEncryptedPackage,
    )
    from ...application.modelo._review_package_signing import SignedReviewPackage


def review_package_build_result_payload(build_result: ReviewPackageBuildResult) -> ModeloReviewPackageBuildResult:
    """Project a review-package build result into the JSON envelope payload."""
    manifest = build_result.manifest
    return ModeloReviewPackageBuildResult(
        bucket_id=manifest.bucket_id,
        work_unit_id=manifest.work_unit_id,
        calculation_revision_id=manifest.calculation_revision_id,
        modelo=manifest.modelo,
        filing_year=manifest.filing_year,
        period=manifest.period,
        revision_state=manifest.revision_state,
        has_ledger_evidence=manifest.has_ledger_evidence,
        output_path=str(build_result.output_path),
        member_count=build_result.member_count,
        built_by=manifest.built_by,
        built_at=manifest.built_at,
    )


def review_package_build_result_lines(
    build_result: ReviewPackageBuildResult,
    *,
    export_bucket_event_id: str,
) -> list[str]:
    """Project a review-package build result into text output lines."""
    manifest = build_result.manifest
    return [
        "operation\tmodelo.review_package.build",
        f"work_unit_id\t{manifest.work_unit_id}",
        f"calculation_revision_id\t{manifest.calculation_revision_id}",
        f"bucket\t{manifest.bucket_id}",
        f"modelo\t{manifest.modelo}",
        f"filing_year\t{manifest.filing_year}",
        f"period\t{manifest.period}",
        f"output_path\t{build_result.output_path}",
        f"member_count\t{build_result.member_count}",
        f"has_ledger_evidence\t{manifest.has_ledger_evidence}",
        f"export_bucket_event_id\t{export_bucket_event_id}",
    ]


def review_package_verify_result(
    package: Path,
    verification: ReviewPackageVerification,
) -> tuple[ModeloReviewPackageVerifyResult, list[str]]:
    """Project a review-package integrity verification into envelope output."""
    manifest = verification.manifest
    result = ModeloReviewPackageVerifyResult(
        package_path=str(package),
        is_clean=verification.is_clean,
        missing=list(verification.missing),
        unexpected=list(verification.unexpected),
        mismatched=list(verification.mismatched),
        bucket_id=manifest.bucket_id,
        work_unit_id=manifest.work_unit_id,
        calculation_revision_id=manifest.calculation_revision_id,
        modelo=manifest.modelo,
        filing_year=manifest.filing_year,
        period=manifest.period,
        revision_state=manifest.revision_state,
        has_ledger_evidence=manifest.has_ledger_evidence,
        built_by=manifest.built_by,
        built_at=manifest.built_at,
    )
    lines = [
        "operation\tmodelo.review_package.verify",
        f"package_path\t{package}",
        f"is_clean\t{verification.is_clean}",
        f"missing\t{', '.join(verification.missing)}",
        f"unexpected\t{', '.join(verification.unexpected)}",
        f"mismatched\t{', '.join(verification.mismatched)}",
        f"calculation_revision_id\t{manifest.calculation_revision_id}",
        f"modelo\t{manifest.modelo}",
        f"built_by\t{manifest.built_by}",
    ]
    return result, lines


def review_package_sign_result(
    package: Path,
    output: Path,
    *,
    bucket_id: str,
    signed: SignedReviewPackage,
    signer_public_key_hex: str,
) -> tuple[ModeloReviewPackageSignResult, list[str]]:
    """Project a review-package signature write into envelope output."""
    result = ModeloReviewPackageSignResult(
        package_path=str(package),
        signature_path=str(output),
        bucket_id=bucket_id,
        calculation_revision_id=signed.calculation_revision_id,
        manifest_sha256=signed.manifest_sha256,
        signer_public_key_hex=signer_public_key_hex,
        signed_at=signed.signed_at,
    )
    lines = [
        "operation\tmodelo.review_package.sign",
        f"package_path\t{package}",
        f"signature_path\t{output}",
        f"bucket\t{bucket_id}",
        f"calculation_revision_id\t{signed.calculation_revision_id}",
        f"signer_public_key_hex\t{signer_public_key_hex}",
    ]
    return result, lines


def review_package_verify_signature_result(
    package: Path,
    signature: Path,
    *,
    signer_public_key_hex: str,
    is_valid: bool,
) -> tuple[ModeloReviewPackageVerifySignatureResult, list[str]]:
    """Project an Ed25519 signature verification into envelope output."""
    result = ModeloReviewPackageVerifySignatureResult(
        package_path=str(package),
        signature_path=str(signature),
        signer_public_key_hex=signer_public_key_hex,
        is_valid=is_valid,
    )
    lines = [
        "operation\tmodelo.review_package.verify_signature",
        f"package_path\t{package}",
        f"signature_path\t{signature}",
        f"is_valid\t{is_valid}",
    ]
    return result, lines


def review_package_counter_sign_result(
    package: Path,
    signature: Path,
    output: Path,
    *,
    bucket_id: str,
    receipt: CounterSignedReceipt,
    counter_signer_public_key_hex: str,
) -> tuple[ModeloReviewPackageCounterSignResult, list[str]]:
    """Project an accountant counter-signature receipt into envelope output."""
    result = ModeloReviewPackageCounterSignResult(
        package_path=str(package),
        signature_path=str(signature),
        receipt_path=str(output),
        bucket_id=bucket_id,
        note=receipt.note,
        counter_signer_public_key_hex=counter_signer_public_key_hex,
        counter_signed_at=receipt.counter_signed_at,
    )
    lines = [
        "operation\tmodelo.review_package.counter_sign",
        f"package_path\t{package}",
        f"receipt_path\t{output}",
        f"bucket\t{bucket_id}",
        f"counter_signer_public_key_hex\t{counter_signer_public_key_hex}",
    ]
    return result, lines


def review_package_verify_receipt_result(
    package: Path,
    receipt_path: Path,
    *,
    operator_public_key_hex: str,
    counter_signer_public_key_hex: str,
    is_valid: bool,
) -> tuple[ModeloReviewPackageVerifyReceiptResult, list[str]]:
    """Project counter-signed receipt verification into envelope output."""
    result = ModeloReviewPackageVerifyReceiptResult(
        package_path=str(package),
        receipt_path=str(receipt_path),
        operator_public_key_hex=operator_public_key_hex,
        counter_signer_public_key_hex=counter_signer_public_key_hex,
        is_valid=is_valid,
    )
    lines = [
        "operation\tmodelo.review_package.verify_receipt",
        f"package_path\t{package}",
        f"receipt_path\t{receipt_path}",
        f"is_valid\t{is_valid}",
    ]
    return result, lines


def review_package_encrypt_for_recipient_result(
    package: Path,
    output: Path,
    *,
    recipient_id: str,
    recipient_public_key_hex: str,
    envelope: RecipientEncryptedPackage,
) -> tuple[ModeloReviewPackageEncryptForRecipientResult, list[str]]:
    """Project recipient-encryption output into the CLI envelope."""
    result = ModeloReviewPackageEncryptForRecipientResult(
        package_path=str(package),
        output_path=str(output),
        recipient_id=recipient_id,
        recipient_public_key_hex=recipient_public_key_hex,
        review_only=envelope.review_only,
        issued_at=envelope.issued_at,
        valid_until=envelope.valid_until,
    )
    lines = [
        "operation\tmodelo.review_package.encrypt_for_recipient",
        f"package_path\t{package}",
        f"output_path\t{output}",
        f"recipient_id\t{recipient_id}",
        f"recipient_public_key_hex\t{recipient_public_key_hex}",
        f"review_only\t{envelope.review_only}",
        f"valid_until\t{envelope.valid_until.isoformat() if envelope.valid_until is not None else 'never'}",
    ]
    return result, lines


def review_package_decrypt_result(
    envelope_path: Path,
    output: Path,
    *,
    bucket_id: str,
    decrypted: RecipientDecryptedPackage,
) -> tuple[ModeloReviewPackageDecryptResult, list[str]]:
    """Project recipient-decryption output into the CLI envelope."""
    result = ModeloReviewPackageDecryptResult(
        envelope_path=str(envelope_path),
        output_path=str(output),
        bucket_id=bucket_id,
        review_only=decrypted.review_only,
    )
    lines = [
        "operation\tmodelo.review_package.decrypt",
        f"envelope_path\t{envelope_path}",
        f"output_path\t{output}",
        f"bucket\t{bucket_id}",
        f"review_only\t{decrypted.review_only}",
    ]
    return result, lines


def review_package_encrypt_feedback_result(
    output: Path,
    *,
    originator_id: str,
    originator_public_key_hex: str,
    work_unit_id: str,
    calculation_revision_id: CalculationRevisionId,
    has_counter_sign: bool,
    envelope: RecipientEncryptedPackage,
) -> tuple[ModeloReviewPackageEncryptFeedbackResult, list[str]]:
    """Project encrypted feedback output into the CLI envelope."""
    result = ModeloReviewPackageEncryptFeedbackResult(
        output_path=str(output),
        originator_id=originator_id,
        originator_public_key_hex=originator_public_key_hex,
        work_unit_id=work_unit_id,
        calculation_revision_id=calculation_revision_id,
        has_counter_sign=has_counter_sign,
        issued_at=envelope.issued_at,
        valid_until=envelope.valid_until,
    )
    lines = [
        "operation\tmodelo.review_package.encrypt_feedback",
        f"output_path\t{output}",
        f"originator_id\t{originator_id}",
        f"work_unit_id\t{work_unit_id}",
        f"calculation_revision_id\t{calculation_revision_id}",
        f"has_counter_sign\t{has_counter_sign}",
    ]
    return result, lines


def review_package_import_feedback_result(
    envelope_path: Path,
    *,
    bucket_id: str,
    imported: ImportedFeedback,
    attached: bool,
) -> tuple[ModeloReviewPackageImportFeedbackResult, list[str]]:
    """Project imported feedback output into the CLI envelope."""
    result = ModeloReviewPackageImportFeedbackResult(
        envelope_path=str(envelope_path),
        bucket_id=bucket_id,
        work_unit_id=imported.feedback.work_unit_id,
        calculation_revision_id=imported.feedback.calculation_revision_id,
        note=imported.feedback.note,
        submitted_by=imported.feedback.submitted_by,
        counter_signature_verified=imported.counter_signature_verified,
        attached_to_journal=attached,
    )
    lines = [
        "operation\tmodelo.review_package.import_feedback",
        f"envelope_path\t{envelope_path}",
        f"bucket\t{bucket_id}",
        f"work_unit_id\t{imported.feedback.work_unit_id}",
        f"calculation_revision_id\t{imported.feedback.calculation_revision_id}",
        f"submitted_by\t{imported.feedback.submitted_by}",
        f"counter_signature_verified\t{imported.counter_signature_verified}",
        f"attached_to_journal\t{attached}",
    ]
    return result, lines


__all__ = [
    "review_package_build_result_lines",
    "review_package_build_result_payload",
    "review_package_counter_sign_result",
    "review_package_decrypt_result",
    "review_package_encrypt_feedback_result",
    "review_package_encrypt_for_recipient_result",
    "review_package_import_feedback_result",
    "review_package_sign_result",
    "review_package_verify_receipt_result",
    "review_package_verify_result",
    "review_package_verify_signature_result",
]
