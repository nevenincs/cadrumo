"""Installation acts that verify the files an operator holds: review packages and calculation reports.

Each handler calls the application function the matching command-line verb
calls, on the same bytes, and answers with a projection of the verdict. The
projections exist because the verification models load the tax registry, which
a process that only connects to the runtime must not import. Nothing here opens
a profile, and nothing here contacts the tax agency.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from ...application.modelo.calculation_report_verification import (
    CalculationSummaryVerification,
    verify_calculation_summary,
)
from ...application.modelo.calculation_summary_pdf_ports import CalculationSummaryPdfUnreadableError
from ...application.modelo.review_package import (
    ReviewPackageIntegrityError,
    ReviewPackageVerification,
    verify_review_package,
)
from ...application.modelo.review_package_counter_sign import ReviewPackageCounterSigningError
from ...application.modelo.review_package_signing import ReviewPackageSigningError
from ...application.modelo.review_package_verification_files import (
    verify_review_package_receipt_file,
    verify_review_package_signature_file,
)
from ...application.operations.public_period import PublicPeriod
from ...application.runtime.installation_requests import (
    RuntimeReportVerifyDocumentReply,
    RuntimeReportVerifyDocumentRequest,
    RuntimeReviewPackageVerifyReceiptReply,
    RuntimeReviewPackageVerifyReceiptRequest,
    RuntimeReviewPackageVerifyReply,
    RuntimeReviewPackageVerifyRequest,
    RuntimeReviewPackageVerifySignatureReply,
    RuntimeReviewPackageVerifySignatureRequest,
)
from ...core.hex import HEX_PATTERN_64
from ...domain.calculations.registry.authority import bundled_indexed_authority

if TYPE_CHECKING:
    from .installation_composition import InstallationActRegistry
    from .installation_door import InstallationActExchange

_PACKAGE_NOT_FOUND = "review package file not found"
_SIGNATURE_NOT_READABLE = "signature envelope could not be read"
_RECEIPT_NOT_READABLE = "counter-signed receipt could not be read"
_TRUSTED_KEY_INVALID = "a trusted signing key is 64 hexadecimal characters"


def _package_verification_document(package: str, verification: ReviewPackageVerification) -> dict[str, object]:
    manifest = verification.manifest
    return {
        "operation": "modelo.review_package.verify",
        "package_path": package,
        "is_clean": verification.is_clean,
        "missing": list(verification.missing),
        "unexpected": list(verification.unexpected),
        "mismatched": list(verification.mismatched),
        "bucket_id": manifest.bucket_id,
        "work_unit_id": manifest.work_unit_id,
        "calculation_revision_id": manifest.calculation_revision_id,
        "modelo": manifest.modelo,
        "filing_year": manifest.filing_year,
        "period": PublicPeriod.from_period(manifest.period),
        "revision_state": manifest.revision_state,
        "has_ledger_evidence": manifest.has_ledger_evidence,
        "built_by": manifest.built_by,
        "built_at": manifest.built_at,
    }


def _report_verification_document(path: str, verification: CalculationSummaryVerification) -> dict[str, object]:
    return {
        "operation": "modelo.work.report_verify",
        "path": path,
        "outcome": verification.outcome.value,
        "store_checked": verification.store_checked,
        "reasons": [reason.value for reason in verification.reasons],
        "checks": [
            {
                "check": row.check.value,
                "layer": row.layer.value,
                "reason": None if row.reason is None else row.reason.value,
                "detail": row.detail,
                "refuses": row.refuses,
            }
            for row in verification.checks
        ],
        "calculation_revision_id": verification.calculation_revision_id,
        "report_sha256": verification.report_sha256,
        "statement_sha256": verification.statement_sha256,
        "signing_key_fingerprint": verification.signing_key_fingerprint,
    }


def serve_review_package_verify(
    request: RuntimeReviewPackageVerifyRequest, exchange: InstallationActExchange
) -> RuntimeReviewPackageVerifyReply:
    """Check a package's checksum manifest and read its descriptor."""
    package = Path(request.package)
    try:
        with bundled_indexed_authority().operation() as operation:
            verification = verify_review_package(package, operation=operation)
    except FileNotFoundError as error:
        raise ReviewPackageIntegrityError(
            translated_message="application.modelo.errors.review_package_integrity",
            context={"package_path": request.package, "detail": _PACKAGE_NOT_FOUND},
        ) from error
    return exchange.reply(
        RuntimeReviewPackageVerifyReply, **_package_verification_document(request.package, verification)
    )


def serve_review_package_verify_signature(
    request: RuntimeReviewPackageVerifySignatureRequest, exchange: InstallationActExchange
) -> RuntimeReviewPackageVerifySignatureReply:
    """Check a package's signature envelope against the key the caller trusts."""
    try:
        verdict = verify_review_package_signature_file(
            Path(request.package), Path(request.signature), public_key=request.public_key
        )
    except OSError as error:
        raise ReviewPackageSigningError(_SIGNATURE_NOT_READABLE, context={"detail": _SIGNATURE_NOT_READABLE}) from error
    return exchange.reply(
        RuntimeReviewPackageVerifySignatureReply,
        operation="modelo.review_package.verify_signature",
        package_path=request.package,
        signature_path=request.signature,
        signer_public_key_hex=verdict.signer_public_key_hex,
        is_valid=verdict.is_valid,
    )


def serve_review_package_verify_receipt(
    request: RuntimeReviewPackageVerifyReceiptRequest, exchange: InstallationActExchange
) -> RuntimeReviewPackageVerifyReceiptReply:
    """Check both signature layers of a counter-signed receipt."""
    try:
        verdict = verify_review_package_receipt_file(
            Path(request.package),
            Path(request.receipt),
            operator_public_key=request.operator_public_key,
            counter_signer_public_key=request.counter_signer_public_key,
        )
    except OSError as error:
        raise ReviewPackageCounterSigningError(
            _RECEIPT_NOT_READABLE, context={"detail": _RECEIPT_NOT_READABLE}
        ) from error
    return exchange.reply(
        RuntimeReviewPackageVerifyReceiptReply,
        operation="modelo.review_package.verify_receipt",
        package_path=request.package,
        receipt_path=request.receipt,
        operator_public_key_hex=verdict.operator_public_key_hex,
        counter_signer_public_key_hex=verdict.counter_signer_public_key_hex,
        is_valid=verdict.is_valid,
    )


def serve_report_verify_document(
    request: RuntimeReportVerifyDocumentRequest, exchange: InstallationActExchange
) -> RuntimeReportVerifyDocumentReply:
    """Check a calculation summary by its own bytes, tracing it to no profile."""
    from ...adapters.outbound.calculation_summary_pdf.summary_reading import read_calculation_summary_pdf

    trusted_public_key_hex = None if request.trusted_key is None else request.trusted_key.strip().lower()
    if trusted_public_key_hex is not None and not re.fullmatch(HEX_PATTERN_64, trusted_public_key_hex):
        raise ReviewPackageSigningError(_TRUSTED_KEY_INVALID, context={"detail": _TRUSTED_KEY_INVALID})
    try:
        payload = Path(request.path).read_bytes()
    except OSError as error:
        raise CalculationSummaryPdfUnreadableError(
            translated_message="application.modelo.errors.calculation_summary_pdf_unreadable",
            context={"error_type": type(error).__name__},
        ) from error
    verification = verify_calculation_summary(
        payload, reader=read_calculation_summary_pdf, trusted_public_key_hex=trusted_public_key_hex
    )
    return exchange.reply(RuntimeReportVerifyDocumentReply, **_report_verification_document(request.path, verification))


def register_artefact_acts(registry: InstallationActRegistry) -> None:
    """Serve the four file-verification acts on ``registry``."""
    registry.register(RuntimeReviewPackageVerifyRequest, serve_review_package_verify)
    registry.register(RuntimeReviewPackageVerifySignatureRequest, serve_review_package_verify_signature)
    registry.register(RuntimeReviewPackageVerifyReceiptRequest, serve_review_package_verify_receipt)
    registry.register(RuntimeReportVerifyDocumentRequest, serve_report_verify_document)
