"""Ed25519 review-package signing + signature-verify application proofs.

Exercises the application signing policy against a real built-and-checksummed
review package (:func:`~application.modelo.build_review_package`) while an
inward capability fake supplies the transient keypair. Secure-object
persistence and race behavior are covered by the outward adapter test cluster.

Mirrors the anti-tautology discipline already established in
``test_review_package.py``: every negative-path test names the exact way the
system deviates from "clean" before asserting the refusal.

See Also:
    :mod:`~application.modelo.review_package_signing`
        Ed25519 authenticity layer exercised by the roundtrip and tamper cases.
    :mod:`~application.modelo.review_package`
        Checksum-manifest package builder whose integrity guarantee is verified
        before signature validation.
    :mod:`~application.modelo.review_package_counter_sign`
        Accountant receipt layer that signs over this module's original
        signature bytes.
"""

from __future__ import annotations

import functools
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import ValidationError

from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ..review_package_signing import (
    ReviewPackageSigningKeypair,
    SignedReviewPackage,
    ensure_review_package_signing_keypair,
    sign_review_package,
    verify_review_package_signature,
)
from .review_package_bytes_support import build_package_path, review_package_revision, review_package_work_unit
from .review_package_signing_support import InMemoryReviewPackageSigningKeypairCapability

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# Canonical UUIDv4 profile identities. Test buckets publish through
# ``canonical_profile_bucket_id``, which accepts only a version-4 UUID, so
# a readable label cannot address a bucket. The foreign id is a VALID but
# different identity on purpose: the refusal under test is a bucket
# mismatch, and a malformed id would refuse for the wrong reason.
_OWNER_BUCKET_ID = "2e510000-0000-4000-8000-000000000001"
_YEAR = filing_year_envelope().horizon
_NOW = datetime(_YEAR, 7, 3, 12, 0, tzinfo=UTC)
_DRAFT_BYTES = b"FICHERO-BOE-BYTES-FOR-REVIEW-PACKAGE-SIGNING-TEST"
_SIGNING_CAPABILITY = InMemoryReviewPackageSigningKeypairCapability()


_build_package = functools.partial(
    build_package_path,
    work_unit_factory=review_package_work_unit,
    revision_factory=functools.partial(review_package_revision, source_ref="test-review-package-signing"),
    draft_bytes=_DRAFT_BYTES,
)


def test_sign_then_verify_with_correct_public_key_passes(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    bucket_id = _OWNER_BUCKET_ID
    package_path = _build_package(tmp_path, bucket_id=bucket_id, operation=operation)
    keypair = ensure_review_package_signing_keypair(
        bucket_id=bucket_id,
        signing_keypair=_SIGNING_CAPABILITY,
    )

    signed = sign_review_package(package_path, keypair=keypair, signed_at=_NOW)
    round_tripped = SignedReviewPackage.model_validate_json(signed.model_dump_json())

    assert round_tripped == signed
    assert round_tripped.signed_at == _NOW
    assert round_tripped.bucket_id == bucket_id
    assert round_tripped.public_key_hex == keypair.public_key_hex
    assert len(bytes.fromhex(round_tripped.signature_hex)) == 64

    assert verify_review_package_signature(package_path, round_tripped, public_key_hex=keypair.public_key_hex) is True


@pytest.mark.parametrize(
    "signed_at",
    (
        pytest.param(datetime(_YEAR, 7, 3, 12, 0), id="naive"),
        pytest.param(datetime(_YEAR, 7, 3, 14, 0, tzinfo=timezone(timedelta(hours=2))), id="non-utc"),
    ),
)
def test_sign_refuses_a_naive_or_non_utc_envelope_timestamp(
    tmp_path: Path, signed_at: datetime, *, operation: PinnedAuthorityOperation
) -> None:
    """A signature envelope must carry one explicit UTC instant."""
    bucket_id = _OWNER_BUCKET_ID
    package_path = _build_package(tmp_path, bucket_id=bucket_id, operation=operation)
    keypair = ensure_review_package_signing_keypair(
        bucket_id=bucket_id,
        signing_keypair=_SIGNING_CAPABILITY,
    )

    with pytest.raises(ValidationError, match="datetime must be"):
        sign_review_package(package_path, keypair=keypair, signed_at=signed_at)


def test_verify_fails_when_package_tampered_after_signing(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """Tampering the archive after signing must fail verification (integrity-then-signature)."""
    import zipfile

    bucket_id = _OWNER_BUCKET_ID
    package_path = _build_package(tmp_path, bucket_id=bucket_id, operation=operation)
    keypair = ensure_review_package_signing_keypair(
        bucket_id=bucket_id,
        signing_keypair=_SIGNING_CAPABILITY,
    )
    signed = sign_review_package(package_path, keypair=keypair)

    # Tamper one archived member's bytes after the signature was minted.
    rewritten = package_path.with_name(package_path.name + ".rewritten")
    with zipfile.ZipFile(package_path, "r") as src, zipfile.ZipFile(rewritten, "w") as dst:
        for item in src.infolist():
            data = b"TAMPERED FICHERO BYTES" if item.filename == "draft.fichero-boe" else src.read(item.filename)
            dst.writestr(item, data)
    rewritten.replace(package_path)

    assert verify_review_package_signature(package_path, signed, public_key_hex=keypair.public_key_hex) is False


def test_verify_fails_with_wrong_public_key(tmp_path: Path, *, operation: PinnedAuthorityOperation) -> None:
    bucket_id = _OWNER_BUCKET_ID
    package_path = _build_package(tmp_path, bucket_id=bucket_id, operation=operation)
    keypair = ensure_review_package_signing_keypair(
        bucket_id=bucket_id,
        signing_keypair=_SIGNING_CAPABILITY,
    )
    signed = sign_review_package(package_path, keypair=keypair)

    wrong_public_key = Ed25519PrivateKey.generate().public_key()
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

    wrong_public_key_hex = wrong_public_key.public_bytes(
        encoding=Encoding.Raw,
        format=PublicFormat.Raw,
    ).hex()

    assert verify_review_package_signature(package_path, signed, public_key_hex=wrong_public_key_hex) is False


def test_verify_fails_when_signature_bytes_are_corrupted(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """A structurally-valid but wrong signature (same length, different bytes) must fail."""
    bucket_id = _OWNER_BUCKET_ID
    package_path = _build_package(tmp_path, bucket_id=bucket_id, operation=operation)
    keypair = ensure_review_package_signing_keypair(
        bucket_id=bucket_id,
        signing_keypair=_SIGNING_CAPABILITY,
    )
    signed = sign_review_package(package_path, keypair=keypair)

    corrupted_signature_hex = ("0" if signed.signature_hex[0] != "0" else "1") + signed.signature_hex[1:]
    corrupted = signed.model_copy(update={"signature_hex": corrupted_signature_hex})

    assert verify_review_package_signature(package_path, corrupted, public_key_hex=keypair.public_key_hex) is False


__all__: list[str] = []


@pytest.mark.parametrize(
    "instant",
    [
        datetime(_YEAR, 5, 3, 12, 0),  # naive: the shape under test
        datetime(_YEAR, 5, 3, 12, 0, tzinfo=timezone(timedelta(hours=1))),
    ],
)
def test_signing_keypair_refuses_a_non_utc_created_at(instant: datetime) -> None:
    """A key's minting instant is held to the same UTC contract as its signatures.

    ``signed_at`` already refused a naive or offset instant while the key's own
    ``created_at`` accepted one, so "was this signature made after the key
    existed?" was unanswerable across the boundary the signature defends.
    """
    with pytest.raises(ValidationError):
        ReviewPackageSigningKeypair(
            bucket_id="bucket",
            private_key_hex="a" * 64,
            public_key_hex="b" * 64,
            created_at=instant,
        )


def test_signing_keypair_accepts_a_utc_created_at() -> None:
    """Positive control: the UTC shape the mint path produces is still accepted."""
    minted_at = datetime(_YEAR, 5, 3, 12, 0, tzinfo=UTC)

    keypair = ReviewPackageSigningKeypair(
        bucket_id="bucket",
        private_key_hex="a" * 64,
        public_key_hex="b" * 64,
        created_at=minted_at,
    )

    assert keypair.created_at == minted_at
