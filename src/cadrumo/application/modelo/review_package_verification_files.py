"""Verification of the files a reviewer holds: a signature envelope and a counter-signed receipt.

The envelope and the receipt are read from disk, decoded, and checked against
public keys the verifier supplies. No profile and no store is consulted, so the
command line and the runtime's installation door give the same verdict from the
same call.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ...core.external_constants import UTF_8_ENCODING
from .review_package_counter_sign import (
    CounterSignedReceipt,
    ReviewPackageCounterSigningError,
    verify_counter_signed_receipt,
)
from .review_package_signing import (
    ReviewPackageSigningError,
    SignedReviewPackage,
    verify_review_package_signature,
)


@dataclass(frozen=True, slots=True)
class ReviewPackageSignatureVerdict:
    """Whether a package's signature holds for the key the verifier named."""

    signer_public_key_hex: str
    is_valid: bool


@dataclass(frozen=True, slots=True)
class ReviewPackageReceiptVerdict:
    """Whether both layers of a receipt hold for the keys the verifier named."""

    operator_public_key_hex: str
    counter_signer_public_key_hex: str
    is_valid: bool


def _normalise_public_key_hex(value: str) -> str:
    """Return the form in which a verifier's public key is compared and reported."""
    return value.strip().lower()


def verify_review_package_signature_file(
    package: Path, signature: Path, *, public_key: str
) -> ReviewPackageSignatureVerdict:
    """Verify ``package`` against the envelope stored at ``signature``.

    Raises:
        OSError: ``signature`` cannot be read.
        ReviewPackageSigningError: ``signature`` does not hold a signature envelope.
    """
    try:
        signed = SignedReviewPackage.model_validate_json(signature.read_text(encoding=UTF_8_ENCODING))
    except ValueError as exc:
        raise ReviewPackageSigningError(str(exc), context={"detail": str(exc)}) from exc
    signer_public_key_hex = _normalise_public_key_hex(public_key)
    return ReviewPackageSignatureVerdict(
        signer_public_key_hex=signer_public_key_hex,
        is_valid=verify_review_package_signature(package, signed, public_key_hex=signer_public_key_hex),
    )


def verify_review_package_receipt_file(
    package: Path, receipt: Path, *, operator_public_key: str, counter_signer_public_key: str
) -> ReviewPackageReceiptVerdict:
    """Verify both signature layers of the receipt stored at ``receipt`` against ``package``.

    Raises:
        OSError: ``receipt`` cannot be read.
        ReviewPackageCounterSigningError: ``receipt`` does not hold a counter-signed receipt.
    """
    try:
        decoded = CounterSignedReceipt.model_validate_json(receipt.read_text(encoding=UTF_8_ENCODING))
    except ValueError as exc:
        raise ReviewPackageCounterSigningError(str(exc), context={"detail": str(exc)}) from exc
    operator_key = _normalise_public_key_hex(operator_public_key)
    counter_key = _normalise_public_key_hex(counter_signer_public_key)
    return ReviewPackageReceiptVerdict(
        operator_public_key_hex=operator_key,
        counter_signer_public_key_hex=counter_key,
        is_valid=verify_counter_signed_receipt(
            package, decoded, operator_public_key_hex=operator_key, counter_signer_public_key_hex=counter_key
        ),
    )


__all__ = [
    "ReviewPackageReceiptVerdict",
    "ReviewPackageSignatureVerdict",
    "verify_review_package_receipt_file",
    "verify_review_package_signature_file",
]
