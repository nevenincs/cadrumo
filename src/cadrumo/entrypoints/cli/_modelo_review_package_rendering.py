"""Output projection helpers for Modelo review-package CLI commands.

See Also:
    :mod:`~entrypoints.cli._modelo_review_package_cli`
        Typer verb registrar that calls these projection helpers before emitting
        CLI envelopes.
    :mod:`~entrypoints.cli._modelo_review_package_payloads`
        Strict result schemas populated by this module for build, verify,
        signing, recipient encryption, and feedback flows.
    :func:`~application.modelo.review_package.build_review_package`
        Application build primitive whose manifest is projected into build
        result payloads and text lines.
    :func:`~application.modelo.review_package_signing.sign_review_package`
        Ed25519 authenticity primitive represented by the signing projections.
    :func:`~application.modelo.review_package_recipient_encryption.encrypt_review_package_for_recipient`
        X25519 recipient-sealing primitive represented by encrypt/decrypt
        projections.
    :func:`~application.modelo.review_package_feedback.import_feedback_package`
        Originator-side feedback import primitive represented by the feedback
        projection.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ...domain.modelos.codes import ModeloCode
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
    from ...application.modelo.review_package import ReviewPackageBuildResult, ReviewPackageVerification
    from ...application.modelo.review_package_exchange_operation import (
        ModeloReviewPackageCounterSignProjection,
        ModeloReviewPackageDecryptProjection,
        ModeloReviewPackageEncryptFeedbackProjection,
        ModeloReviewPackageEncryptForRecipientProjection,
        ModeloReviewPackageImportFeedbackProjection,
        ModeloReviewPackageSignProjection,
    )


def review_package_build_result_payload(build_result: ReviewPackageBuildResult) -> ModeloReviewPackageBuildResult:
    """Project a review-package build result into the JSON envelope payload."""
    manifest = build_result.manifest
    return ModeloReviewPackageBuildResult(
        bucket_id=manifest.bucket_id,
        work_unit_id=manifest.work_unit_id,
        calculation_revision_id=manifest.calculation_revision_id,
        modelo=ModeloCode(manifest.modelo),
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
        modelo=ModeloCode(manifest.modelo),
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
    projection: ModeloReviewPackageSignProjection,
) -> tuple[ModeloReviewPackageSignResult, list[str]]:
    """Project a review-package signature write into envelope output."""
    result = ModeloReviewPackageSignResult(
        package_path=projection.package_path,
        signature_path=projection.signature_path,
        bucket_id=projection.bucket_id,
        calculation_revision_id=projection.calculation_revision_id,
        manifest_sha256=projection.manifest_sha256,
        signer_public_key_hex=projection.signer_public_key_hex,
        signed_at=projection.signed_at,
    )
    lines = [
        "operation\tmodelo.review_package.sign",
        f"package_path\t{projection.package_path}",
        f"signature_path\t{projection.signature_path}",
        f"bucket\t{projection.bucket_id}",
        f"calculation_revision_id\t{projection.calculation_revision_id}",
        f"signer_public_key_hex\t{projection.signer_public_key_hex}",
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
    projection: ModeloReviewPackageCounterSignProjection,
) -> tuple[ModeloReviewPackageCounterSignResult, list[str]]:
    """Project an accountant counter-signature receipt into envelope output."""
    result = ModeloReviewPackageCounterSignResult(
        package_path=projection.package_path,
        signature_path=projection.signature_path,
        receipt_path=projection.receipt_path,
        bucket_id=projection.bucket_id,
        note=projection.note,
        counter_signer_public_key_hex=projection.counter_signer_public_key_hex,
        counter_signed_at=projection.counter_signed_at,
    )
    lines = [
        "operation\tmodelo.review_package.counter_sign",
        f"package_path\t{projection.package_path}",
        f"receipt_path\t{projection.receipt_path}",
        f"bucket\t{projection.bucket_id}",
        f"counter_signer_public_key_hex\t{projection.counter_signer_public_key_hex}",
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
    projection: ModeloReviewPackageEncryptForRecipientProjection,
) -> tuple[ModeloReviewPackageEncryptForRecipientResult, list[str]]:
    """Project recipient-encryption output into the CLI envelope."""
    result = ModeloReviewPackageEncryptForRecipientResult(
        package_path=projection.package_path,
        output_path=projection.output_path,
        recipient_id=projection.recipient_id,
        recipient_public_key_hex=projection.recipient_public_key_hex,
        review_only=projection.review_only,
        issued_at=projection.issued_at,
        valid_until=projection.valid_until,
    )
    lines = [
        "operation\tmodelo.review_package.encrypt_for_recipient",
        f"package_path\t{projection.package_path}",
        f"output_path\t{projection.output_path}",
        f"recipient_id\t{projection.recipient_id}",
        f"recipient_public_key_hex\t{projection.recipient_public_key_hex}",
        f"review_only\t{projection.review_only}",
        f"valid_until\t{projection.valid_until.isoformat() if projection.valid_until is not None else 'never'}",
    ]
    return result, lines


def review_package_decrypt_result(
    projection: ModeloReviewPackageDecryptProjection,
) -> tuple[ModeloReviewPackageDecryptResult, list[str]]:
    """Project recipient-decryption output into the CLI envelope."""
    result = ModeloReviewPackageDecryptResult(
        envelope_path=projection.envelope_path,
        output_path=projection.output_path,
        bucket_id=projection.bucket_id,
        review_only=projection.review_only,
    )
    lines = [
        "operation\tmodelo.review_package.decrypt",
        f"envelope_path\t{projection.envelope_path}",
        f"output_path\t{projection.output_path}",
        f"bucket\t{projection.bucket_id}",
        f"review_only\t{projection.review_only}",
    ]
    return result, lines


def review_package_encrypt_feedback_result(
    projection: ModeloReviewPackageEncryptFeedbackProjection,
) -> tuple[ModeloReviewPackageEncryptFeedbackResult, list[str]]:
    """Project encrypted feedback output into the CLI envelope."""
    result = ModeloReviewPackageEncryptFeedbackResult(
        output_path=projection.output_path,
        originator_id=projection.originator_id,
        originator_public_key_hex=projection.originator_public_key_hex,
        work_unit_id=projection.work_unit_id,
        calculation_revision_id=projection.calculation_revision_id,
        has_counter_sign=projection.has_counter_sign,
        issued_at=projection.issued_at,
        valid_until=projection.valid_until,
    )
    lines = [
        "operation\tmodelo.review_package.encrypt_feedback",
        f"output_path\t{projection.output_path}",
        f"originator_id\t{projection.originator_id}",
        f"work_unit_id\t{projection.work_unit_id}",
        f"calculation_revision_id\t{projection.calculation_revision_id}",
        f"has_counter_sign\t{projection.has_counter_sign}",
    ]
    return result, lines


def review_package_import_feedback_result(
    projection: ModeloReviewPackageImportFeedbackProjection,
) -> tuple[ModeloReviewPackageImportFeedbackResult, list[str]]:
    """Project imported feedback output into the CLI envelope."""
    result = ModeloReviewPackageImportFeedbackResult(
        envelope_path=projection.envelope_path,
        bucket_id=projection.bucket_id,
        work_unit_id=projection.work_unit_id,
        calculation_revision_id=projection.calculation_revision_id,
        note=projection.note,
        submitted_by=projection.submitted_by,
        counter_signature_verified=projection.counter_signature_verified,
        attached_to_journal=projection.attached_to_journal,
    )
    lines = [
        "operation\tmodelo.review_package.import_feedback",
        f"envelope_path\t{projection.envelope_path}",
        f"bucket\t{projection.bucket_id}",
        f"work_unit_id\t{projection.work_unit_id}",
        f"calculation_revision_id\t{projection.calculation_revision_id}",
        f"submitted_by\t{projection.submitted_by}",
        f"counter_signature_verified\t{projection.counter_signature_verified}",
        f"attached_to_journal\t{projection.attached_to_journal}",
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
