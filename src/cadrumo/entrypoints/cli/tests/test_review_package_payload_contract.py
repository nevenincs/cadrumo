"""Contract parity between review-package application results and their CLI shells.

The registered ``modelo.review_package.*`` result schemas must refuse the
malformed identity, count, digest, and timestamp shapes the canonical
``ReviewPackageManifest`` / ``ReviewPackageBuildResult`` /
``SignedReviewPackage`` / ``CounterSignedReceipt`` /
``RecipientEncryptedPackage`` / ``FeedbackPackage`` models already refuse.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ....core import Period
from .._modelo_review_package_payloads import (
    ModeloReviewPackageBuildResult,
    ModeloReviewPackageCounterSignResult,
    ModeloReviewPackageEncryptForRecipientResult,
    ModeloReviewPackageImportFeedbackResult,
    ModeloReviewPackageSignResult,
    ModeloReviewPackageVerifyResult,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_BUILT_AT = datetime(2026, 6, 1, 8, 0, tzinfo=UTC)


def _build_kwargs(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "bucket_id": "a" * 64,
        "work_unit_id": "b" * 64,
        "calculation_revision_id": "c" * 64,
        "modelo": "130",
        "filing_year": 2026,
        "period": Period.model_validate({"filing_year": 2026, "code": "1T"}),
        "revision_state": "VERIFICADO_COMPLETO",
        "has_ledger_evidence": True,
        "output_path": "/tmp/review.zip",
        "member_count": 3,
        "built_by": "operator",
        "built_at": _BUILT_AT,
    }
    base.update(overrides)
    return base


def test_build_result_accepts_a_real_projection() -> None:
    """A genuine build result projects and validates cleanly."""
    result = ModeloReviewPackageBuildResult(**_build_kwargs())

    assert result.modelo == "130"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("modelo", ""),
        ("filing_year", 0),
        ("revision_state", ""),
        ("member_count", -1),
        ("built_by", ""),
        ("built_at", "not-a-date"),
        ("bucket_id", ""),
        ("work_unit_id", "bad"),
        ("calculation_revision_id", "bad"),
    ],
)
def test_build_result_rejects_malformed_manifest_fields(field: str, value: object) -> None:
    """Every malformed manifest field the finding's probe named is refused."""
    with pytest.raises(ValidationError):
        ModeloReviewPackageBuildResult.model_validate(_build_kwargs(**{field: value}))


def test_verify_result_rejects_malformed_manifest_fields() -> None:
    """The verify envelope carries the same manifest fields and the same refusal."""
    kwargs = {
        "package_path": "/tmp/review.zip",
        "is_clean": True,
        "missing": [],
        "unexpected": [],
        "mismatched": [],
        **_build_kwargs(),
    }
    del kwargs["output_path"]
    del kwargs["member_count"]
    ModeloReviewPackageVerifyResult.model_validate(kwargs)

    with pytest.raises(ValidationError):
        ModeloReviewPackageVerifyResult.model_validate({**kwargs, "modelo": ""})


def test_sign_result_rejects_a_malformed_manifest_digest() -> None:
    """A non hex-64 manifest digest is refused, matching ``SignedReviewPackage``."""
    with pytest.raises(ValidationError):
        ModeloReviewPackageSignResult.model_validate(
            {
                "package_path": "/tmp/review.zip",
                "signature_path": "/tmp/review.sig",
                "bucket_id": "bucket-1",
                "calculation_revision_id": "c" * 64,
                "manifest_sha256": "not-a-digest",
                "signer_public_key_hex": "d" * 64,
                "signed_at": _BUILT_AT,
            },
        )


def test_sign_result_accepts_a_real_projection() -> None:
    """A genuine signing result round-trips cleanly."""
    result = ModeloReviewPackageSignResult.model_validate(
        {
            "package_path": "/tmp/review.zip",
            "signature_path": "/tmp/review.sig",
            "bucket_id": "bucket-1",
            "calculation_revision_id": "c" * 64,
            "manifest_sha256": "e" * 64,
            "signer_public_key_hex": "d" * 64,
            "signed_at": _BUILT_AT,
        },
    )

    assert result.manifest_sha256 == "e" * 64


def test_counter_sign_result_rejects_a_malformed_public_key() -> None:
    """A non hex-64 counter-signer public key is refused."""
    with pytest.raises(ValidationError):
        ModeloReviewPackageCounterSignResult.model_validate(
            {
                "package_path": "/tmp/review.zip",
                "signature_path": "/tmp/review.sig",
                "receipt_path": "/tmp/review.receipt",
                "bucket_id": "bucket-1",
                "note": "looks fine",
                "counter_signer_public_key_hex": "not-a-key",
                "counter_signed_at": _BUILT_AT,
            },
        )


def test_encrypt_for_recipient_result_rejects_a_malformed_recipient_key() -> None:
    """A non hex-64 recipient public key is refused, matching ``RecipientEncryptedPackage``."""
    with pytest.raises(ValidationError):
        ModeloReviewPackageEncryptForRecipientResult.model_validate(
            {
                "package_path": "/tmp/review.zip",
                "output_path": "/tmp/review.sealed",
                "recipient_id": "accountant-1",
                "recipient_public_key_hex": "not-a-key",
                "review_only": True,
                "issued_at": _BUILT_AT,
                "valid_until": None,
            },
        )


def test_import_feedback_result_rejects_a_malformed_work_unit_id() -> None:
    """A malformed work-unit id is refused, matching ``FeedbackPackage``."""
    with pytest.raises(ValidationError):
        ModeloReviewPackageImportFeedbackResult.model_validate(
            {
                "envelope_path": "/tmp/feedback.sealed",
                "bucket_id": "bucket-1",
                "work_unit_id": "bad",
                "calculation_revision_id": "c" * 64,
                "note": "looks fine",
                "submitted_by": "accountant",
                "counter_signature_verified": None,
                "attached_to_journal": False,
            },
        )
