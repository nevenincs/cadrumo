"""The certification statement a calculation summary is signed through.

The signing digest is recomputed here from the literal context label and the
statement bytes with the standard library, independently of the module under
test, so a change to the construction a recipient reproduces with OpenSSL cannot
pass by agreeing with itself.
"""

from __future__ import annotations

import hashlib

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat

from ....core.ed25519_signing import digest_signature_is_valid, sign_digest_hex
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ..calculation_report import ModeloCalculationReport
from ..calculation_report_certification import (
    CERTIFICATION_XMP_PROPERTIES,
    CalculationReportCertification,
    CalculationReportSigningKey,
    calculation_report_signature_is_valid,
    certify_calculation_report,
    parse_certification_statement,
)
from ..review_package_signing import ReviewPackageSigningKeypair
from ._calculation_report_fixture import EXPORTED_AT, TAXPAYER_NAME, TAXPAYER_TAX_ID, build_fixture_report

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CONTEXT = b"cadrumo/calculation-report-certification/v1\x00"
_CSV_SHA256 = "a" * 64
_PAGES_SHA256 = "b" * 64


def _keypair(seed: str) -> ReviewPackageSigningKeypair:
    private = Ed25519PrivateKey.from_private_bytes(hashlib.sha256(seed.encode("utf-8")).digest())
    return ReviewPackageSigningKeypair(
        bucket_id="22222222-2222-4222-8222-222222222222",
        private_key_hex=private.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption()).hex(),
        public_key_hex=private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex(),
        created_at=EXPORTED_AT,
    )


_PROFILE = _keypair("certification-profile")


@pytest.fixture
def certified(operation: PinnedAuthorityOperation) -> tuple[ModeloCalculationReport, CalculationReportCertification]:
    report, _ = build_fixture_report(operation)
    return report, certify_calculation_report(
        report,
        csv_sha256=_CSV_SHA256,
        visible_layer_sha256=_PAGES_SHA256,
        keypair=_PROFILE,
    )


def test_the_statement_binds_the_report_and_round_trips_canonically(
    certified: tuple[ModeloCalculationReport, CalculationReportCertification],
) -> None:
    report, certification = certified
    statement = certification.statement

    assert statement.report_sha256 == report.report_sha256
    assert statement.csv_sha256 == _CSV_SHA256
    assert statement.visible_layer_sha256 == _PAGES_SHA256
    assert statement.calculation_revision_id == report.header.calculation_revision_id
    assert statement.authority_logical_generation == report.header.authority_logical_generation
    assert statement.aeat_official is False
    assert parse_certification_statement(certification.statement_bytes) == statement
    assert parse_certification_statement(certification.statement_bytes).canonical_bytes() == (
        certification.statement_bytes
    )
    assert statement.statement_sha256 == hashlib.sha256(certification.statement_bytes).hexdigest()


def test_the_signature_is_ed25519_over_the_prefixed_statement_digest(
    certified: tuple[ModeloCalculationReport, CalculationReportCertification],
) -> None:
    """The construction a recipient reproduces with stock tools, recomputed independently."""
    _, certification = certified
    digest = hashlib.sha256(_CONTEXT + certification.statement_bytes).hexdigest()

    assert digest_signature_is_valid(
        public_key_hex=_PROFILE.public_key_hex,
        digest_hex=digest,
        signature_hex=certification.signature.hex(),
    )
    assert calculation_report_signature_is_valid(
        certification.statement_bytes,
        certification.signature,
        public_key_hex=_PROFILE.public_key_hex,
    )


def test_a_single_tampered_byte_or_another_key_fails_verification(
    certified: tuple[ModeloCalculationReport, CalculationReportCertification],
) -> None:
    _, certification = certified
    tampered_statement = bytearray(certification.statement_bytes)
    tampered_statement[len(tampered_statement) // 2] ^= 0x01
    tampered_signature = bytearray(certification.signature)
    tampered_signature[0] ^= 0x01

    def valid(statement: bytes, signature: bytes, key: str) -> bool:
        return calculation_report_signature_is_valid(statement, signature, public_key_hex=key)

    assert not valid(bytes(tampered_statement), certification.signature, _PROFILE.public_key_hex)
    assert not valid(certification.statement_bytes, bytes(tampered_signature), _PROFILE.public_key_hex)
    assert not valid(certification.statement_bytes, certification.signature, _keypair("other").public_key_hex)
    assert not valid(certification.statement_bytes, certification.signature[:-1], _PROFILE.public_key_hex)


def test_a_report_signature_and_a_review_package_signature_never_verify_as_each_other(
    certified: tuple[ModeloCalculationReport, CalculationReportCertification],
) -> None:
    """One profile key signs both; the context label keeps the two purposes apart."""
    _, certification = certified
    bare_digest = hashlib.sha256(certification.statement_bytes).hexdigest()
    review_package_style = bytes.fromhex(
        sign_digest_hex(private_key_hex=_PROFILE.private_key_hex, digest_hex=bare_digest),
    )

    assert not digest_signature_is_valid(
        public_key_hex=_PROFILE.public_key_hex,
        digest_hex=bare_digest,
        signature_hex=certification.signature.hex(),
    )
    assert not calculation_report_signature_is_valid(
        certification.statement_bytes,
        review_package_style,
        public_key_hex=_PROFILE.public_key_hex,
    )


def test_the_metadata_mirror_is_declared_omits_absence_and_carries_no_identity(
    certified: tuple[ModeloCalculationReport, CalculationReportCertification],
) -> None:
    report, certification = certified
    properties = certification.xmp_properties

    assert set(properties) <= {name for name, _ in CERTIFICATION_XMP_PROPERTIES}
    assert properties["AeatOfficial"] == "false"
    assert properties["ReportSha256"] == report.report_sha256
    assert properties["StatementSha256"] == certification.statement.statement_sha256
    assert properties["SigningPublicKey"] == _PROFILE.public_key_hex
    for value in properties.values():
        assert TAXPAYER_TAX_ID not in value
        assert TAXPAYER_NAME not in value
    assert all(value not in {"None", "none", ""} for value in properties.values())


def test_an_absent_identifier_is_omitted_from_the_mirror_rather_than_spelled(
    certified: tuple[ModeloCalculationReport, CalculationReportCertification],
) -> None:
    report, _ = certified
    unfiled = report.model_copy(update={"header": report.header.model_copy(update={"filing_record_id": None})})

    certification = certify_calculation_report(
        unfiled,
        csv_sha256=_CSV_SHA256,
        visible_layer_sha256=_PAGES_SHA256,
        keypair=_PROFILE,
    )

    assert certification.statement.filing_record_id is None
    assert "FilingRecordId" not in certification.xmp_properties
    assert "FilingRecordId" in {name for name, _ in CERTIFICATION_XMP_PROPERTIES}


def test_a_signing_key_whose_fingerprint_names_another_key_is_refused() -> None:
    with pytest.raises(ValueError, match="fingerprint"):
        CalculationReportSigningKey(
            public_key_hex=_PROFILE.public_key_hex,
            fingerprint_sha256=hashlib.sha256(bytes.fromhex(_keypair("other").public_key_hex)).hexdigest(),
        )
