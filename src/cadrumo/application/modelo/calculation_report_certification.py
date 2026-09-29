"""The signed integrity statement a calculation summary carries.

A calculation summary is a PDF a taxpayer hands to an accountant, and the
accountant usually has no Cadrumo. What travels with it has to answer two
questions without the store: were the embedded report, CSV and pages changed
after export, and which installation's key attests to them. This module owns the
answer's shape and its cryptography, and nothing about PDFs.

The statement is one canonical JSON record binding the report's digest, the
CSV's digest, the digest of the visible page layer and every traceability
identifier the report header carries. It is signed with the profile's existing
Ed25519 review-package key through the product's one digest primitive
(:func:`~cadrumo.core.ed25519_signing.sign_digest_hex`). The primitive signs the
raw bytes of a SHA-256 digest; here that digest is taken over a fixed context
label, a NUL byte and the statement bytes, so a report signature can never be
presented as a review-package signature under the same key, nor the reverse.
The same construction is what a recipient reproduces with stock OpenSSL.

What a valid signature asserts is narrow and deliberate: that this profile's key
attests that, at the recorded export instant by this installation's clock, the
named revision in the named state, verification report, registry snapshot and
authority generation produced exactly this report, CSV and page layer. It does
not assert AEAT acceptance, legal correctness, the truth of the inputs, the
taxpayer's identity or consent, or a trusted time. ``aeat_official`` is part of
the signed record and can only ever be ``false``.

See Also:
    :mod:`cadrumo.application.modelo.calculation_report`:
        The report whose canonical bytes the statement binds.
    :mod:`cadrumo.application.modelo.calculation_report_verification`:
        Verifies a summary against this statement and, optionally, the store.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import TYPE_CHECKING, Final, Literal

from pydantic import BaseModel, Field, model_validator

from ...core.ed25519_signing import digest_signature_is_valid, sign_digest_hex
from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.filing_year import FilingYear
from ...core.hashing import canonical_json_bytes, reject_duplicate_json_members, reject_json_constant, sha256_hex
from ...core.hex import Hex64Str
from ...core.identity.digest import ContentDigest
from ...core.identity.hex_ids import (
    CalculationRevisionId,
    FilingRecordId,
    VerificationReportId,
    WorkUnitId,
)
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.period import Period
from ...core.time.utc import UtcInstant
from ...domain.calculations.registry.schema_references import RegistrySnapshotRef
from ...domain.filing.software_identity import AeatSoftwareIdentityGrade
from ...domain.modelos.calculation_revision import CalculationRevisionState
from ...domain.modelos.codes import ModeloCode
from ...domain.modelos.verification_report import VerificationCompletenessStatus
from .calculation_report import CALCULATION_REPORT_CONTENT_VERSION, ModeloCalculationReport

if TYPE_CHECKING:
    from .review_package_signing import ReviewPackageSigningKeypair

CALCULATION_REPORT_CERTIFICATION_SCHEMA: Final[str] = "cadrumo.calculation-report-certification/1"
"""Schema identifier of the certification statement.

A verifier refuses a statement naming any other schema rather than guessing
which fields a different version binds.
"""

CALCULATION_REPORT_SCHEMA: Final[str] = f"cadrumo.calculation-report/{CALCULATION_REPORT_CONTENT_VERSION}"
"""Schema identifier of the canonical report bytes the statement binds."""

CALCULATION_SUMMARY_PDF_RENDER_PROFILE: Final[str] = "cadrumo.calculation-summary-pdf/1"
"""Identifier of the page layout, tagging and embedding contract a summary follows.

Signed, so a verifier knows which visible-layer recipe produced the page digest
it is about to recompute.
"""

CALCULATION_REPORT_SIGNING_CONTEXT: Final[bytes] = b"cadrumo/calculation-report-certification/v1\x00"
"""Domain-separation prefix of the signed digest's preimage.

Versioned and NUL-terminated, so no statement byte sequence can extend the label
into another one. A review-package signature signs a bare manifest digest with no
prefix, which is exactly why the two can never verify as each other.
"""

_ED25519_SIGNATURE_BYTES: Final[int] = 64

CERTIFICATION_XMP_PROPERTIES: Final[tuple[tuple[str, str], ...]] = (
    ("StatementSchema", "Schema identifier of the embedded certification statement"),
    ("RenderProfile", "Page layout, tagging and embedding contract of the summary"),
    ("ReportSchema", "Schema identifier of the embedded calculation report"),
    ("ReportSha256", "SHA-256 of the embedded canonical calculation report"),
    ("CsvSha256", "SHA-256 of the embedded CSV table"),
    ("VisibleLayerSha256", "SHA-256 over the page boxes, decoded page content and font programs"),
    ("Modelo", "AEAT modelo code"),
    ("FilingYear", "Filing year the calculation addresses"),
    ("Period", "Period code the calculation addresses"),
    ("RegistryModelo", "Modelo of the registry snapshot the calculation used"),
    ("RegistryRevisionId", "Registry revision of the snapshot the calculation used"),
    ("RegistryYear", "Year of the registry snapshot the calculation used"),
    ("RegistryPeriod", "Period of the registry snapshot the calculation used"),
    ("CalculationRevisionId", "Content-addressed calculation revision identifier"),
    ("CalculationRevisionState", "State of the calculation revision at export"),
    ("WorkUnitId", "Content-addressed work unit identifier"),
    ("VerificationReportId", "Content-addressed verification report identifier"),
    ("VerificationOutcome", "Completeness verdict of the verification report"),
    ("FilingRecordId", "Content-addressed filing record identifier"),
    ("AuthorityLogicalGeneration", "Logical generation of the registry authority"),
    ("SoftwareIdentityGrade", "Grade of the software identity the filing file would carry"),
    ("ExportedAt", "Export instant, UTC, by the exporting installation's clock"),
    ("AeatOfficial", "Always false: a local calculation, not AEAT evidence"),
    ("SignatureAlgorithm", "Algorithm of the certification signature"),
    ("SigningPublicKey", "Raw Ed25519 public key of the signing profile, hex"),
    ("SigningKeyFingerprint", "SHA-256 of the raw signing public key, hex"),
    ("StatementSha256", "SHA-256 of the embedded certification statement"),
)
"""Every document-metadata property a summary may carry, with its declared meaning.

The writer declares each one in the document's metadata extension schema, which
archival conformance requires of any property outside the predefined schemas.
"""


_UTF_8: Final[str] = "utf-8"


class CalculationReportSigningKey(BaseModel):
    """The public half of the key a statement is signed with.

    ``fingerprint_sha256`` is the SHA-256 of the raw 32-byte public key. It is the
    value printed on the summary's page, and the one a recipient compares with a
    fingerprint received out of band before trusting any signature this key made.
    """

    model_config = STRICT_FROZEN_CONFIG

    algorithm: Literal["Ed25519"] = "Ed25519"
    public_key_hex: Hex64Str
    fingerprint_sha256: ContentDigest

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _fingerprint_names_the_key(self) -> CalculationReportSigningKey:
        if self.fingerprint_sha256 != signing_key_fingerprint(self.public_key_hex):
            raise ValueError("signing key fingerprint is not the SHA-256 of its public key")
        return self


class CalculationReportCertificationStatement(BaseModel):
    """The canonical record a calculation summary's signature covers.

    Every identifier is copied from the report header, so the statement adds no
    fact of its own beyond the three digests, the render profile and the key. A
    ``None`` identifier is carried as ``null`` in the statement, which is the
    canonical spelling of "the report states none".
    """

    model_config = STRICT_FROZEN_CONFIG

    statement_schema: Literal["cadrumo.calculation-report-certification/1"] = (
        "cadrumo.calculation-report-certification/1"
    )
    render_profile: str = Field(min_length=1, max_length=128)
    report_schema: str = Field(min_length=1, max_length=128)
    report_sha256: ContentDigest
    csv_sha256: ContentDigest
    visible_layer_sha256: ContentDigest
    modelo: ModeloCode
    filing_year: FilingYear
    period: Period
    registry_snapshot_ref: RegistrySnapshotRef
    calculation_revision_id: CalculationRevisionId
    calculation_revision_state: CalculationRevisionState
    work_unit_id: WorkUnitId
    verification_report_id: VerificationReportId | None
    verification_outcome: VerificationCompletenessStatus | None
    filing_record_id: FilingRecordId | None
    authority_logical_generation: ContentDigest
    software_identity_grade: AeatSoftwareIdentityGrade | None
    exported_at: UtcInstant
    aeat_official: Literal[False] = False
    signing_key: CalculationReportSigningKey

    def canonical_bytes(self) -> bytes:
        """Return the statement's canonical bytes: exactly what is signed and embedded."""
        return canonical_json_bytes(self.model_dump(mode="json"))

    @property
    def statement_sha256(self) -> ContentDigest:
        """SHA-256 over :meth:`canonical_bytes`."""
        return sha256_hex(self.canonical_bytes())


class CalculationReportCertification(BaseModel):
    """One signed statement, as the bytes a summary embeds.

    ``xmp_properties`` is the statement mirrored into the summary's document
    metadata, one text property per statement field, plus the statement's own
    digest. It is a convenience for indexers and is never authoritative: a
    verifier compares it with the statement and refuses any disagreement.
    """

    model_config = STRICT_FROZEN_CONFIG

    statement: CalculationReportCertificationStatement
    statement_bytes: bytes
    signature: bytes = Field(min_length=_ED25519_SIGNATURE_BYTES, max_length=_ED25519_SIGNATURE_BYTES)
    xmp_properties: Mapping[str, str]

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _bytes_are_the_statement(self) -> CalculationReportCertification:
        if self.statement_bytes != self.statement.canonical_bytes():
            raise ValueError("certification statement bytes are not the statement's canonical bytes")
        return self


def signing_key_fingerprint(public_key_hex: str) -> ContentDigest:
    """Return the SHA-256 of the raw public key named by ``public_key_hex``."""
    return sha256_hex(bytes.fromhex(public_key_hex))


def certification_signing_digest_hex(statement_bytes: bytes) -> str:
    """Return the digest the signature covers: SHA-256 of the context label and the statement."""
    return sha256_hex(CALCULATION_REPORT_SIGNING_CONTEXT + statement_bytes)


def calculation_report_signature_is_valid(
    statement_bytes: bytes,
    signature: bytes,
    *,
    public_key_hex: str,
) -> bool:
    """Return whether ``signature`` is this key's signature over ``statement_bytes``.

    Never raises for a verdict: a signature of the wrong length and a public key
    that is not a valid curve point are both "does not verify", exactly as a
    tampered statement is.
    """
    if len(signature) != _ED25519_SIGNATURE_BYTES:
        return False
    try:
        return digest_signature_is_valid(
            public_key_hex=public_key_hex,
            digest_hex=certification_signing_digest_hex(statement_bytes),
            signature_hex=signature.hex(),
        )
    except ValueError:
        return False


def build_certification_statement(
    report: ModeloCalculationReport,
    *,
    csv_sha256: str,
    visible_layer_sha256: str,
    public_key_hex: str,
) -> CalculationReportCertificationStatement:
    """Assemble the statement for ``report`` from its header and the three digests."""
    header = report.header
    return CalculationReportCertificationStatement(
        render_profile=CALCULATION_SUMMARY_PDF_RENDER_PROFILE,
        report_schema=CALCULATION_REPORT_SCHEMA,
        report_sha256=report.report_sha256,
        csv_sha256=csv_sha256,
        visible_layer_sha256=visible_layer_sha256,
        modelo=header.modelo,
        filing_year=header.filing_year,
        period=header.period,
        registry_snapshot_ref=header.registry_snapshot_ref,
        calculation_revision_id=header.calculation_revision_id,
        calculation_revision_state=header.calculation_revision_state,
        work_unit_id=header.work_unit_id,
        verification_report_id=header.verification_report_id,
        verification_outcome=header.verification_outcome,
        filing_record_id=header.filing_record_id,
        authority_logical_generation=header.authority_logical_generation,
        software_identity_grade=header.software_identity_grade,
        exported_at=header.exported_at,
        signing_key=CalculationReportSigningKey(
            public_key_hex=public_key_hex,
            fingerprint_sha256=signing_key_fingerprint(public_key_hex),
        ),
    )


def certification_xmp_properties(
    statement: CalculationReportCertificationStatement,
) -> dict[str, str]:
    """Mirror ``statement`` into text properties for the document metadata.

    Carries only content-addressed identifiers, digests, codes, the grade, the
    export instant and the public key -- the statement's own fields, which hold no
    taxpayer identity by construction. A ``None`` field is omitted rather than
    spelled, so absence in the metadata means exactly what it means in the
    statement.
    """
    snapshot = statement.registry_snapshot_ref
    mirrored: dict[str, str | None] = {
        "StatementSchema": statement.statement_schema,
        "RenderProfile": statement.render_profile,
        "ReportSchema": statement.report_schema,
        "ReportSha256": statement.report_sha256,
        "CsvSha256": statement.csv_sha256,
        "VisibleLayerSha256": statement.visible_layer_sha256,
        "Modelo": str(statement.modelo),
        "FilingYear": str(statement.filing_year),
        "Period": statement.period.registry_token,
        "RegistryModelo": str(snapshot.modelo),
        "RegistryRevisionId": str(snapshot.revision_id),
        "RegistryYear": str(snapshot.modelo_year),
        "RegistryPeriod": str(snapshot.period),
        "CalculationRevisionId": statement.calculation_revision_id,
        "CalculationRevisionState": statement.calculation_revision_state.value,
        "WorkUnitId": statement.work_unit_id,
        "VerificationReportId": statement.verification_report_id,
        "VerificationOutcome": None if statement.verification_outcome is None else statement.verification_outcome.value,
        "FilingRecordId": statement.filing_record_id,
        "AuthorityLogicalGeneration": statement.authority_logical_generation,
        "SoftwareIdentityGrade": (
            None if statement.software_identity_grade is None else statement.software_identity_grade.value
        ),
        "ExportedAt": statement.model_dump(mode="json")["exported_at"],
        "AeatOfficial": "false",
        "SignatureAlgorithm": statement.signing_key.algorithm,
        "SigningPublicKey": statement.signing_key.public_key_hex,
        "SigningKeyFingerprint": statement.signing_key.fingerprint_sha256,
        "StatementSha256": statement.statement_sha256,
    }
    declared = {name for name, _description in CERTIFICATION_XMP_PROPERTIES}
    undeclared = sorted(set(mirrored) - declared)
    if undeclared:
        raise ValueError(f"certification metadata properties are not declared: {undeclared!r}")
    return {name: value for name, value in mirrored.items() if value is not None}


def certify_calculation_report(
    report: ModeloCalculationReport,
    *,
    csv_sha256: str,
    visible_layer_sha256: str,
    keypair: ReviewPackageSigningKeypair,
) -> CalculationReportCertification:
    """Build, sign and mirror the statement for one rendered summary.

    The private key is read from the in-memory keypair only to sign; nothing here
    stores or returns it.
    """
    statement = build_certification_statement(
        report,
        csv_sha256=csv_sha256,
        visible_layer_sha256=visible_layer_sha256,
        public_key_hex=keypair.public_key_hex,
    )
    statement_bytes = statement.canonical_bytes()
    signature = bytes.fromhex(
        sign_digest_hex(
            private_key_hex=keypair.private_key_hex,
            digest_hex=certification_signing_digest_hex(statement_bytes),
        ),
    )
    return CalculationReportCertification(
        statement=statement,
        statement_bytes=statement_bytes,
        signature=signature,
        xmp_properties=certification_xmp_properties(statement),
    )


def parse_certification_statement(statement_bytes: bytes) -> CalculationReportCertificationStatement:
    """Decode embedded statement bytes into the typed statement.

    Strict in both directions: a repeated member or a non-finite constant is
    refused at decode, and the typed record is validated with the statement's own
    strict configuration. Whether the bytes are the statement's CANONICAL
    spelling is a separate question the caller asks by re-encoding.

    Raises:
        ValueError: The bytes are not UTF-8 JSON, or do not validate as a
            statement of this schema.
    """
    decoded = json.loads(
        statement_bytes.decode(_UTF_8),
        object_pairs_hook=reject_duplicate_json_members,
        parse_constant=reject_json_constant,
    )
    return CalculationReportCertificationStatement.model_validate_json(canonical_json_bytes(decoded))


__all__ = [
    "CALCULATION_REPORT_CERTIFICATION_SCHEMA",
    "CALCULATION_REPORT_SCHEMA",
    "CALCULATION_REPORT_SIGNING_CONTEXT",
    "CALCULATION_SUMMARY_PDF_RENDER_PROFILE",
    "CERTIFICATION_XMP_PROPERTIES",
    "CalculationReportCertification",
    "CalculationReportCertificationStatement",
    "CalculationReportSigningKey",
    "build_certification_statement",
    "calculation_report_signature_is_valid",
    "certification_signing_digest_hex",
    "certification_xmp_properties",
    "certify_calculation_report",
    "parse_certification_statement",
    "signing_key_fingerprint",
]
