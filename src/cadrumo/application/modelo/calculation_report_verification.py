"""Verify a calculation summary PDF, alone or against the encrypted store.

A summary travels to people who usually have no Cadrumo, and returns to the
operator who wants to know whether it still says what the store says. This is
the one service both questions go through, in two layers, each producing check
rows with reasons from one closed set.

The DOCUMENT layer needs nothing but the file. It recovers the embedded report,
CSV, statement and signature; proves the signature over the statement; proves the
statement binds the report and CSV actually embedded, the page layer actually
shown and the identifiers the report header carries; proves the CSV is exactly
the one the report derives and the metadata mirrors the statement; and checks
that every figure and the taxpayer's identity can be read off the page. A file
that passes is internally consistent -- which a forger holding their own key can
also achieve. So without a trusted key or the store the verdict is
``valid_unpinned``, never ``verified``: only a key pinned from an out-of-band
fingerprint, or this profile's own key, turns consistency into provenance.

The STORE layer runs when the active profile is available. It pins the key to
this profile's own, finds the :class:`CalculationRevision` the statement names, compares
the identifiers the store can re-derive, and rebuilds the report from the store
with the recorded language and export instant under the same authority
generation, comparing digests. A later lifecycle step the export could not have
known about -- the revision was filed, or superseded -- is reported but does not
refuse the file; any disagreement about what the calculation WAS refuses it. A
rebuild under a different authority generation cannot prove anything and is
refused as unprovable rather than passed.

See Also:
    :mod:`cadrumo.application.modelo.calculation_report_certification`:
        The statement and signature construction checked here.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, ValidationError

from ...core.hashing import canonical_json_bytes, reject_duplicate_json_members, reject_json_constant, sha256_hex
from ...core.identity.bucket import canonical_bucket_id
from ...core.identity.digest import ContentDigest
from ...core.identity.hex_ids import CalculationRevisionId
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.product_identity import PRODUCT_IDENTITY
from ...core.type_guards import is_str_keyed_dict
from ...domain.modelos.calculation_revision import CalculationRevision
from .action_errors import CalculationRevisionNotFoundError, CalculationRevisionStateError
from .calculation_report import CALCULATION_REPORT_CONTENT_VERSION, ModeloCalculationReport
from .calculation_report_certification import (
    CALCULATION_REPORT_CERTIFICATION_SCHEMA,
    CalculationReportCertificationStatement,
    calculation_report_signature_is_valid,
    certification_xmp_properties,
    parse_certification_statement,
)
from .calculation_report_document import serialize_calculation_report_csv
from .calculation_summary_pdf_ports import (
    CSV_ATTACHMENT_NAME,
    REPORT_ATTACHMENT_NAME,
    SIGNATURE_ATTACHMENT_NAME,
    STATEMENT_ATTACHMENT_NAME,
    CalculationSummaryPdfContents,
    CalculationSummaryPdfReader,
    CalculationSummaryPdfUnreadableError,
)
from .calculation_summary_presentation import (
    CalculationSummaryChromeUnavailableError,
    build_calculation_summary_presentation,
)
from .review_package_signing import ReviewPackageSigningError, ReviewPackageSigningKeypair

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from .export_ports import ModeloExportPorts
    from .review_package_signing_ports import ReviewPackageSigningKeypairReader

_UTF_8: Final[str] = "utf-8"
_REPORT_PAYLOAD_KEYS: Final[frozenset[str]] = frozenset({"content_version", "header", "rows"})


class CalculationSummaryVerificationOutcome(StrEnum):
    """The verdict on one summary.

    Attributes:
        VERIFIED: Every check passed and the signing key is pinned -- to an
            explicitly trusted key, or to this profile's key by the store layer.
        VERIFIED_WITH_LATER_CHANGES: Verified against the store, which records a
            later lifecycle step the export predates.
        VALID_UNPINNED: Every document check passed but no key was trusted and the
            store was not consulted, so a consistent forgery is not excluded.
        REFUSED: At least one check failed, or the store layer cannot prove the
            file.
    """

    VERIFIED = "verified"
    VERIFIED_WITH_LATER_CHANGES = "verified_with_later_changes"
    VALID_UNPINNED = "valid_unpinned"
    REFUSED = "refused"


class CalculationSummaryVerificationLayer(StrEnum):
    """Which layer a check belongs to."""

    DOCUMENT = "document"
    STORE = "store"


class CalculationSummaryCheckName(StrEnum):
    """The closed set of checks, each reported as one or more rows."""

    PDF = "pdf"
    CADRUMO_REPORT = "cadrumo_report"
    ATTACHMENTS = "attachments"
    STATEMENT = "statement"
    STATEMENT_CANONICAL = "statement_canonical"
    SIGNATURE = "signature"
    SIGNING_KEY_TRUSTED = "signing_key_trusted"
    REPORT_DIGEST = "report_digest"
    CSV_DIGEST = "csv_digest"
    METADATA = "metadata"
    VISIBLE_LAYER = "visible_layer"
    VISIBLE_LAYER_OVERLAY = "visible_layer_overlay"
    REPORT_CANONICAL = "report_canonical"
    REPORT_STATEMENT = "report_statement"
    CSV_DERIVATION = "csv_derivation"
    TEXT_LAYER = "text_layer"
    SIGNING_KEY_PROFILE = "signing_key_profile"
    CALCULATION_REVISION = "calculation_revision"
    WORK_UNIT = "work_unit"
    REGISTRY_SNAPSHOT = "registry_snapshot"
    VERIFICATION_REPORT = "verification_report"
    FILING_RECORD = "filing_record"
    REVISION_STATE = "revision_state"
    AUTHORITY_GENERATION = "authority_generation"
    SOURCE_PROVENANCE = "source_provenance"
    REPORT_REBUILD = "report_rebuild"


class CalculationSummaryVerificationReason(StrEnum):
    """The closed set of reasons a check can report.

    Every reason refuses the file except :attr:`REVISION_STATE_CHANGED` and
    :attr:`FILED_SINCE_EXPORT`, which record a later lifecycle step.
    """

    PDF_UNREADABLE = "pdf_unreadable"
    NOT_A_CADRUMO_REPORT = "not_a_cadrumo_report"
    ATTACHMENT_MISSING = "attachment_missing"
    STATEMENT_UNREADABLE = "statement_unreadable"
    STATEMENT_NOT_CANONICAL = "statement_not_canonical"
    UNSUPPORTED_STATEMENT_SCHEMA = "unsupported_statement_schema"
    SIGNATURE_INVALID = "signature_invalid"
    SIGNING_KEY_UNTRUSTED = "signing_key_untrusted"
    REPORT_DIGEST_MISMATCH = "report_digest_mismatch"
    CSV_DIGEST_MISMATCH = "csv_digest_mismatch"
    REPORT_NOT_CANONICAL = "report_not_canonical"
    REPORT_STATEMENT_MISMATCH = "report_statement_mismatch"
    CSV_NOT_DERIVED_FROM_REPORT = "csv_not_derived_from_report"
    METADATA_MISMATCH = "metadata_mismatch"
    VISIBLE_LAYER_MISMATCH = "visible_layer_mismatch"
    VISIBLE_LAYER_OVERLAY = "visible_layer_overlay"
    TEXT_LAYER_MISMATCH = "text_layer_mismatch"
    SIGNING_KEY_NOT_THIS_PROFILE = "signing_key_not_this_profile"
    CALCULATION_REVISION_NOT_FOUND = "calculation_revision_not_found"
    WORK_UNIT_MISMATCH = "work_unit_mismatch"
    REGISTRY_SNAPSHOT_MISMATCH = "registry_snapshot_mismatch"
    VERIFICATION_REPORT_MISMATCH = "verification_report_mismatch"
    FILING_RECORD_MISMATCH = "filing_record_mismatch"
    AUTHORITY_GENERATION_UNAVAILABLE = "authority_generation_unavailable"
    REPORT_REBUILD_MISMATCH = "report_rebuild_mismatch"
    SOURCE_PROVENANCE_MISMATCH = "source_provenance_mismatch"
    REVISION_STATE_CHANGED = "revision_state_changed"
    FILED_SINCE_EXPORT = "filed_since_export"


INFORMATIONAL_VERIFICATION_REASONS: Final[frozenset[CalculationSummaryVerificationReason]] = frozenset(
    {
        CalculationSummaryVerificationReason.REVISION_STATE_CHANGED,
        CalculationSummaryVerificationReason.FILED_SINCE_EXPORT,
    },
)
"""Reasons that record a later lifecycle step rather than refuse the file."""


class CalculationSummaryVerificationCheck(BaseModel):
    """One check that ran, and what it found.

    ``reason`` is ``None`` when the check passed. ``detail`` names what the
    check compared -- an attachment name, a metadata property, a page -- and never
    carries a taxpayer figure or identity.
    """

    model_config = STRICT_FROZEN_CONFIG

    check: CalculationSummaryCheckName
    layer: CalculationSummaryVerificationLayer
    reason: CalculationSummaryVerificationReason | None = None
    detail: str | None = None

    @property
    def refuses(self) -> bool:
        """Whether this check refuses the file."""
        return self.reason is not None and self.reason not in INFORMATIONAL_VERIFICATION_REASONS


class CalculationSummaryVerification(BaseModel):
    """The verdict on one summary and every check behind it.

    The identifiers are the ones the statement names, when a statement could be
    read; they let a caller say which calculation a verdict is about without
    reading the page.
    """

    model_config = STRICT_FROZEN_CONFIG

    outcome: CalculationSummaryVerificationOutcome
    checks: tuple[CalculationSummaryVerificationCheck, ...]
    store_checked: bool
    signing_key_fingerprint: ContentDigest | None = None
    calculation_revision_id: CalculationRevisionId | None = None
    report_sha256: ContentDigest | None = None
    statement_sha256: ContentDigest | None = None

    @property
    def reasons(self) -> tuple[CalculationSummaryVerificationReason, ...]:
        """Every reason any check reported, in check order."""
        return tuple(check.reason for check in self.checks if check.reason is not None)


class _DocumentReading(BaseModel):
    """What the document layer established, for the store layer to continue from."""

    model_config = STRICT_FROZEN_CONFIG

    checks: tuple[CalculationSummaryVerificationCheck, ...]
    statement: CalculationReportCertificationStatement | None = None
    report: ModeloCalculationReport | None = None

    @property
    def refused(self) -> bool:
        return any(check.refuses for check in self.checks)


class _Checks:
    """Accumulate check rows for one layer."""

    def __init__(self, layer: CalculationSummaryVerificationLayer) -> None:
        self._layer = layer
        self.rows: list[CalculationSummaryVerificationCheck] = []

    def passed(self, check: CalculationSummaryCheckName, *, detail: str | None = None) -> None:
        self.rows.append(CalculationSummaryVerificationCheck(check=check, layer=self._layer, detail=detail))

    def failed(
        self,
        check: CalculationSummaryCheckName,
        reason: CalculationSummaryVerificationReason,
        *,
        detail: str | None = None,
    ) -> None:
        self.rows.append(
            CalculationSummaryVerificationCheck(check=check, layer=self._layer, reason=reason, detail=detail),
        )

    def failed_any(self, check: CalculationSummaryCheckName) -> bool:
        return any(row.check is check and row.reason is not None for row in self.rows)

    def expect(
        self,
        check: CalculationSummaryCheckName,
        holds: bool,
        reason: CalculationSummaryVerificationReason,
        *,
        detail: str | None = None,
    ) -> bool:
        if holds:
            self.passed(check, detail=detail)
        else:
            self.failed(check, reason, detail=detail)
        return holds


def _strict_json(payload: bytes) -> object:
    return json.loads(
        payload.decode(_UTF_8),
        object_pairs_hook=reject_duplicate_json_members,
        parse_constant=reject_json_constant,
    )


def _parse_report(report_bytes: bytes) -> ModeloCalculationReport | None:
    """Rebuild the typed report from its embedded bytes, or ``None`` if they are not one."""
    try:
        decoded = _strict_json(report_bytes)
    except (UnicodeDecodeError, ValueError):
        return None
    if not is_str_keyed_dict(decoded) or frozenset(decoded) != _REPORT_PAYLOAD_KEYS:
        return None
    if decoded["content_version"] != CALCULATION_REPORT_CONTENT_VERSION:
        return None
    try:
        return ModeloCalculationReport.model_validate_json(
            canonical_json_bytes({"header": decoded["header"], "rows": decoded["rows"]}),
        )
    except (ValidationError, ValueError):
        return None


def _statement_identifiers_match(
    statement: CalculationReportCertificationStatement,
    report: ModeloCalculationReport,
) -> tuple[str, ...]:
    """Return the statement fields that disagree with the report they claim to describe."""
    header = report.header
    expected: dict[str, object] = {
        "report_sha256": report.report_sha256,
        "modelo": header.modelo,
        "filing_year": header.filing_year,
        "period": header.period,
        "registry_snapshot_ref": header.registry_snapshot_ref,
        "calculation_revision_id": header.calculation_revision_id,
        "calculation_revision_state": header.calculation_revision_state,
        "work_unit_id": header.work_unit_id,
        "verification_report_id": header.verification_report_id,
        "verification_outcome": header.verification_outcome,
        "filing_record_id": header.filing_record_id,
        "authority_logical_generation": header.authority_logical_generation,
        "software_identity_grade": header.software_identity_grade,
        "exported_at": header.exported_at,
    }
    return tuple(name for name, value in expected.items() if getattr(statement, name) != value)


def _compact(text: str) -> str:
    """Drop every whitespace character, as a line or column break may add or remove one."""
    return "".join(text.split())


def _text_layer_gaps(
    contents: CalculationSummaryPdfContents,
    *,
    report: ModeloCalculationReport,
    statement: CalculationReportCertificationStatement,
) -> tuple[str, ...]:
    """Return what the page text fails to show, in reading order.

    Rebuilds the strings a genuine summary shows from the embedded report and
    walks the extracted page text in order: from the first section heading on,
    each casilla's number must be followed by its value before the next casilla
    starts, and the taxpayer's identity and the report, CSV and key digests must
    be present. Whitespace is ignored on both sides, because wrapping a line and
    extracting a no-break space both change it. Returns the casilla numbers and
    fact names the page does not show.
    """
    try:
        presentation = build_calculation_summary_presentation(
            report,
            csv_sha256=statement.csv_sha256,
            signing_key_fingerprint=statement.signing_key.fingerprint_sha256,
            brand=PRODUCT_IDENTITY.display_name,
        )
    except CalculationSummaryChromeUnavailableError:
        return ("chrome",)
    page = _compact(contents.page_text)
    gaps = [
        label
        for label, value in (
            ("taxpayer_tax_id", report.header.taxpayer_tax_id),
            ("taxpayer_name", report.header.taxpayer_name),
            ("report_sha256", report.report_sha256),
            ("csv_sha256", statement.csv_sha256),
            ("signing_key_fingerprint", statement.signing_key.fingerprint_sha256),
        )
        if _compact(value) not in page
    ]
    cursor = page.find(_compact(presentation.sections[0].heading)) if presentation.sections else 0
    if cursor < 0:
        return (*gaps, "sections")
    for section in presentation.sections:
        for row in section.rows:
            number = _compact(row.casilla_number)
            value = _compact(row.value_text)
            number_at = page.find(number, cursor)
            value_at = -1 if number_at < 0 else page.find(value, number_at + len(number))
            if value_at < 0:
                gaps.append(f"casilla {row.casilla_number}")
                continue
            cursor = value_at + len(value)
    return tuple(gaps)


def _check_statement(
    checks: _Checks,
    statement_bytes: bytes,
) -> CalculationReportCertificationStatement | None:
    try:
        decoded = _strict_json(statement_bytes)
    except (UnicodeDecodeError, ValueError):
        checks.failed(CalculationSummaryCheckName.STATEMENT, CalculationSummaryVerificationReason.STATEMENT_UNREADABLE)
        return None
    if not is_str_keyed_dict(decoded):
        checks.failed(CalculationSummaryCheckName.STATEMENT, CalculationSummaryVerificationReason.STATEMENT_UNREADABLE)
        return None
    if decoded.get("statement_schema") != CALCULATION_REPORT_CERTIFICATION_SCHEMA:
        checks.failed(
            CalculationSummaryCheckName.STATEMENT, CalculationSummaryVerificationReason.UNSUPPORTED_STATEMENT_SCHEMA
        )
        return None
    try:
        statement = parse_certification_statement(statement_bytes)
    except (ValidationError, ValueError):
        checks.failed(CalculationSummaryCheckName.STATEMENT, CalculationSummaryVerificationReason.STATEMENT_UNREADABLE)
        return None
    checks.expect(
        CalculationSummaryCheckName.STATEMENT_CANONICAL,
        statement.canonical_bytes() == statement_bytes,
        CalculationSummaryVerificationReason.STATEMENT_NOT_CANONICAL,
    )
    return statement


def _read_document(
    payload: bytes,
    *,
    reader: CalculationSummaryPdfReader,
    trusted_public_key_hex: str | None,
) -> _DocumentReading:
    checks = _Checks(CalculationSummaryVerificationLayer.DOCUMENT)
    try:
        contents = reader(payload)
    except CalculationSummaryPdfUnreadableError:
        checks.failed(CalculationSummaryCheckName.PDF, CalculationSummaryVerificationReason.PDF_UNREADABLE)
        return _DocumentReading(checks=tuple(checks.rows))
    checks.passed(CalculationSummaryCheckName.PDF)
    if not checks.expect(
        CalculationSummaryCheckName.CADRUMO_REPORT,
        contents.product_metadata is not None,
        CalculationSummaryVerificationReason.NOT_A_CADRUMO_REPORT,
    ):
        return _DocumentReading(checks=tuple(checks.rows))
    names = (REPORT_ATTACHMENT_NAME, CSV_ATTACHMENT_NAME, STATEMENT_ATTACHMENT_NAME, SIGNATURE_ATTACHMENT_NAME)
    missing = [name for name in names if name not in contents.attachments]
    for name in missing:
        checks.failed(
            CalculationSummaryCheckName.ATTACHMENTS,
            CalculationSummaryVerificationReason.ATTACHMENT_MISSING,
            detail=name,
        )
    if missing:
        return _DocumentReading(checks=tuple(checks.rows))
    checks.passed(CalculationSummaryCheckName.ATTACHMENTS)
    report_bytes = contents.attachments[REPORT_ATTACHMENT_NAME]
    csv_bytes = contents.attachments[CSV_ATTACHMENT_NAME]
    statement_bytes = contents.attachments[STATEMENT_ATTACHMENT_NAME]
    signature = contents.attachments[SIGNATURE_ATTACHMENT_NAME]
    statement = _check_statement(checks, statement_bytes)
    if statement is None:
        return _DocumentReading(checks=tuple(checks.rows))
    public_key_hex = statement.signing_key.public_key_hex
    checks.expect(
        CalculationSummaryCheckName.SIGNATURE,
        calculation_report_signature_is_valid(statement_bytes, signature, public_key_hex=public_key_hex),
        CalculationSummaryVerificationReason.SIGNATURE_INVALID,
    )
    if trusted_public_key_hex is not None:
        checks.expect(
            CalculationSummaryCheckName.SIGNING_KEY_TRUSTED,
            public_key_hex == trusted_public_key_hex.strip().lower(),
            CalculationSummaryVerificationReason.SIGNING_KEY_UNTRUSTED,
        )
    checks.expect(
        CalculationSummaryCheckName.REPORT_DIGEST,
        sha256_hex(report_bytes) == statement.report_sha256,
        CalculationSummaryVerificationReason.REPORT_DIGEST_MISMATCH,
    )
    checks.expect(
        CalculationSummaryCheckName.CSV_DIGEST,
        sha256_hex(csv_bytes) == statement.csv_sha256,
        CalculationSummaryVerificationReason.CSV_DIGEST_MISMATCH,
    )
    expected_metadata = certification_xmp_properties(statement)
    metadata = contents.product_metadata or {}
    for name in sorted(set(expected_metadata) | set(metadata)):
        if expected_metadata.get(name) != metadata.get(name):
            checks.failed(
                CalculationSummaryCheckName.METADATA,
                CalculationSummaryVerificationReason.METADATA_MISMATCH,
                detail=name,
            )
    if not checks.failed_any(CalculationSummaryCheckName.METADATA):
        checks.passed(CalculationSummaryCheckName.METADATA)
    checks.expect(
        CalculationSummaryCheckName.VISIBLE_LAYER,
        contents.visible_layer_sha256 == statement.visible_layer_sha256,
        CalculationSummaryVerificationReason.VISIBLE_LAYER_MISMATCH,
    )
    for overlay in contents.visible_layer_overlays:
        checks.failed(
            CalculationSummaryCheckName.VISIBLE_LAYER_OVERLAY,
            CalculationSummaryVerificationReason.VISIBLE_LAYER_OVERLAY,
            detail=overlay,
        )
    report = _parse_report(report_bytes)
    if report is None or report.canonical_bytes() != report_bytes:
        checks.failed(
            CalculationSummaryCheckName.REPORT_CANONICAL, CalculationSummaryVerificationReason.REPORT_NOT_CANONICAL
        )
        return _DocumentReading(checks=tuple(checks.rows), statement=statement)
    checks.passed(CalculationSummaryCheckName.REPORT_CANONICAL)
    for field in _statement_identifiers_match(statement, report):
        checks.failed(
            CalculationSummaryCheckName.REPORT_STATEMENT,
            CalculationSummaryVerificationReason.REPORT_STATEMENT_MISMATCH,
            detail=field,
        )
    if not checks.failed_any(CalculationSummaryCheckName.REPORT_STATEMENT):
        checks.passed(CalculationSummaryCheckName.REPORT_STATEMENT)
    checks.expect(
        CalculationSummaryCheckName.CSV_DERIVATION,
        serialize_calculation_report_csv(report) == csv_bytes,
        CalculationSummaryVerificationReason.CSV_NOT_DERIVED_FROM_REPORT,
    )
    gaps = _text_layer_gaps(contents, report=report, statement=statement)
    for gap in gaps:
        checks.failed(
            CalculationSummaryCheckName.TEXT_LAYER, CalculationSummaryVerificationReason.TEXT_LAYER_MISMATCH, detail=gap
        )
    if not gaps:
        checks.passed(CalculationSummaryCheckName.TEXT_LAYER)
    return _DocumentReading(checks=tuple(checks.rows), statement=statement, report=report)


def _filing_record_ids(revision: CalculationRevision, *, export_ports: ModeloExportPorts) -> frozenset[str]:
    """Return the ids of every filing record the store holds for the revision."""
    return frozenset(
        str(record.filing_record_id)
        for record in export_ports.filing.load().records.values()
        if record.calculation_revision_id == revision.calculation_revision_id
    )


@dataclass(frozen=True, slots=True)
class _ExistingSigningKeypairCapability:
    """Keep report reconstruction bound to the keypair already read."""

    keypair: ReviewPackageSigningKeypair

    def ensure_keypair(
        self,
        *,
        bucket_id: str,
        generated_at: datetime | None = None,
    ) -> ReviewPackageSigningKeypair:
        """Return the retained keypair only for its original bucket."""
        if canonical_bucket_id(bucket_id) != self.keypair.bucket_id:
            raise ReviewPackageSigningError(
                "review-package signing capability is bound to a different bucket",
            )
        return self.keypair


def _trace_against_store(
    reading: _DocumentReading,
    *,
    active_bucket_id: str,
    export_ports: ModeloExportPorts,
    signing_keypair: ReviewPackageSigningKeypairReader,
    operation: PinnedAuthorityOperation,
) -> tuple[CalculationSummaryVerificationCheck, ...]:
    """Run the store layer for a document whose statement and report were read."""
    from .calculation_report_export import build_modelo_calculation_report_for_revision

    statement = reading.statement
    report = reading.report
    checks = _Checks(CalculationSummaryVerificationLayer.STORE)
    if statement is None or report is None:
        return ()
    keypair = signing_keypair.load_keypair(bucket_id=active_bucket_id)
    if keypair is None:
        checks.failed(
            CalculationSummaryCheckName.SIGNING_KEY_PROFILE,
            CalculationSummaryVerificationReason.SIGNING_KEY_NOT_THIS_PROFILE,
        )
        return tuple(checks.rows)
    checks.expect(
        CalculationSummaryCheckName.SIGNING_KEY_PROFILE,
        statement.signing_key.public_key_hex == keypair.public_key_hex,
        CalculationSummaryVerificationReason.SIGNING_KEY_NOT_THIS_PROFILE,
    )
    revision = export_ports.calculation.load(operation=operation).revisions.get(statement.calculation_revision_id)
    if revision is None:
        checks.failed(
            CalculationSummaryCheckName.CALCULATION_REVISION,
            CalculationSummaryVerificationReason.CALCULATION_REVISION_NOT_FOUND,
        )
        return tuple(checks.rows)
    checks.passed(CalculationSummaryCheckName.CALCULATION_REVISION)
    checks.expect(
        CalculationSummaryCheckName.WORK_UNIT,
        revision.work_unit_id == statement.work_unit_id,
        CalculationSummaryVerificationReason.WORK_UNIT_MISMATCH,
    )
    checks.expect(
        CalculationSummaryCheckName.REGISTRY_SNAPSHOT,
        revision.registry_snapshot_ref == statement.registry_snapshot_ref,
        CalculationSummaryVerificationReason.REGISTRY_SNAPSHOT_MISMATCH,
    )
    verification_reports = export_ports.verification.load(operation=operation).for_calculation_revision(
        revision.calculation_revision_id
    )
    recorded_verification = next(
        (item for item in verification_reports if item.verification_report_id == statement.verification_report_id),
        None,
    )
    checks.expect(
        CalculationSummaryCheckName.VERIFICATION_REPORT,
        (statement.verification_report_id is None and not verification_reports)
        or (
            recorded_verification is not None
            and recorded_verification.completeness_status == statement.verification_outcome
        ),
        CalculationSummaryVerificationReason.VERIFICATION_REPORT_MISMATCH,
    )
    filing_record_ids = _filing_record_ids(revision, export_ports=export_ports)
    if statement.filing_record_id is None:
        if filing_record_ids:
            checks.failed(
                CalculationSummaryCheckName.FILING_RECORD, CalculationSummaryVerificationReason.FILED_SINCE_EXPORT
            )
        else:
            checks.passed(CalculationSummaryCheckName.FILING_RECORD)
    else:
        checks.expect(
            CalculationSummaryCheckName.FILING_RECORD,
            str(statement.filing_record_id) in filing_record_ids,
            CalculationSummaryVerificationReason.FILING_RECORD_MISMATCH,
        )
    if revision.state is statement.calculation_revision_state:
        checks.passed(CalculationSummaryCheckName.REVISION_STATE)
    else:
        checks.failed(
            CalculationSummaryCheckName.REVISION_STATE,
            CalculationSummaryVerificationReason.REVISION_STATE_CHANGED,
            detail=revision.state.value,
        )
    if not checks.expect(
        CalculationSummaryCheckName.AUTHORITY_GENERATION,
        operation.generation.logical_generation == statement.authority_logical_generation,
        CalculationSummaryVerificationReason.AUTHORITY_GENERATION_UNAVAILABLE,
    ):
        return tuple(checks.rows)
    try:
        rebuilt = build_modelo_calculation_report_for_revision(
            revision.calculation_revision_id,
            active_bucket_id=active_bucket_id,
            export_ports=export_ports,
            signing_keypair=_ExistingSigningKeypairCapability(keypair),
            operation=operation,
            report_language=report.header.report_language,
            exported_at=statement.exported_at,
        )
    except (CalculationRevisionNotFoundError, CalculationRevisionStateError):
        checks.failed(
            CalculationSummaryCheckName.REPORT_REBUILD, CalculationSummaryVerificationReason.REPORT_REBUILD_MISMATCH
        )
        return tuple(checks.rows)
    # The facts a later lifecycle step legitimately changes are compared by the
    # checks above, so the rebuild is judged as of the export: the recorded
    # state, verification and filing facts stand in for the current ones.
    as_exported = rebuilt.model_copy(
        update={
            "header": rebuilt.header.model_copy(
                update={
                    "calculation_revision_state": statement.calculation_revision_state,
                    "verification_report_id": statement.verification_report_id,
                    "verification_outcome": statement.verification_outcome,
                    "filing_record_id": statement.filing_record_id,
                },
            ),
        },
    )
    checks.expect(
        CalculationSummaryCheckName.SOURCE_PROVENANCE,
        tuple(row.source_provenance for row in as_exported.rows) == tuple(row.source_provenance for row in report.rows),
        CalculationSummaryVerificationReason.SOURCE_PROVENANCE_MISMATCH,
    )
    checks.expect(
        CalculationSummaryCheckName.REPORT_REBUILD,
        as_exported.report_sha256 == statement.report_sha256,
        CalculationSummaryVerificationReason.REPORT_REBUILD_MISMATCH,
    )
    return tuple(checks.rows)


def _outcome(
    checks: tuple[CalculationSummaryVerificationCheck, ...],
    *,
    store_checked: bool,
    key_pinned: bool,
) -> CalculationSummaryVerificationOutcome:
    if any(check.refuses for check in checks):
        return CalculationSummaryVerificationOutcome.REFUSED
    if store_checked:
        if any(check.reason is not None for check in checks):
            return CalculationSummaryVerificationOutcome.VERIFIED_WITH_LATER_CHANGES
        return CalculationSummaryVerificationOutcome.VERIFIED
    if key_pinned:
        return CalculationSummaryVerificationOutcome.VERIFIED
    return CalculationSummaryVerificationOutcome.VALID_UNPINNED


@dataclass(frozen=True, slots=True)
class CalculationSummaryStoreContext:
    """The unlocked profile a summary is traced against."""

    active_bucket_id: str
    export_ports: ModeloExportPorts
    signing_keypair: ReviewPackageSigningKeypairReader
    operation: PinnedAuthorityOperation


def verify_calculation_summary(
    payload: bytes,
    *,
    reader: CalculationSummaryPdfReader,
    trusted_public_key_hex: str | None = None,
    store: CalculationSummaryStoreContext | None = None,
) -> CalculationSummaryVerification:
    """Verify one summary's bytes, and trace it to the store when one is given.

    Args:
        payload: The summary file's bytes.
        reader: The PDF reader that recovers what the file carries.
        trusted_public_key_hex: A signing key the caller trusts, compared with the
            key the statement names. Given as 64 hex characters.
        store: The unlocked profile to trace the summary against; ``None`` runs
            the document layer only.

    Returns:
        :class:`CalculationSummaryVerification`: The verdict and every check.
    """
    reading = _read_document(payload, reader=reader, trusted_public_key_hex=trusted_public_key_hex)
    store_rows: tuple[CalculationSummaryVerificationCheck, ...] = ()
    store_checked = False
    if store is not None and reading.statement is not None and reading.report is not None:
        store_rows = _trace_against_store(
            reading,
            active_bucket_id=store.active_bucket_id,
            export_ports=store.export_ports,
            signing_keypair=store.signing_keypair,
            operation=store.operation,
        )
        store_checked = True
    checks = (*reading.checks, *store_rows)
    statement = reading.statement
    return CalculationSummaryVerification(
        outcome=_outcome(checks, store_checked=store_checked, key_pinned=trusted_public_key_hex is not None),
        checks=checks,
        store_checked=store_checked,
        signing_key_fingerprint=None if statement is None else statement.signing_key.fingerprint_sha256,
        calculation_revision_id=None if statement is None else statement.calculation_revision_id,
        report_sha256=None if statement is None else statement.report_sha256,
        statement_sha256=None if statement is None else statement.statement_sha256,
    )


__all__ = [
    "INFORMATIONAL_VERIFICATION_REASONS",
    "CalculationSummaryCheckName",
    "CalculationSummaryStoreContext",
    "CalculationSummaryVerification",
    "CalculationSummaryVerificationCheck",
    "CalculationSummaryVerificationLayer",
    "CalculationSummaryVerificationOutcome",
    "CalculationSummaryVerificationReason",
    "verify_calculation_summary",
]
