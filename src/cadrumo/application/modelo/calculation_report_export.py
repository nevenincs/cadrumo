"""Publish one sealed revision's calculation report to an operator-chosen file.

The service every surface reaches for a calculation report: resolve the revision
through the same lookup and state rule the fichero-BOE export applies, assemble
the typed report, serialise it into the requested document format, and publish
the bytes through the one local-file export sink. No second file writer, no
second admission rule, and no content decision of its own.

A calculation report is not a filing artefact. It is refused for the same
revisions the fichero-BOE refuses -- a draft revision, a revision whose registry
coordinates no longer resolve, a work unit in another bucket -- because all of
those make the report a statement about something that is not settled. It does
not apply the fichero-BOE's layout, profile-readiness, cross-period or wallet
gates: those decide whether a file can be *presented at AEAT*, and a local
review record makes no such claim.

Two profile-scoped facts are resolved here rather than by a surface, so the CLI
and the terminal interface cannot disagree about them: the filer's own identity,
which the report shows in full, and the derived key every source reference is
digested with.

The calculation summary PDF is the one format that needs more than the report: an
outbound writer to draw it, supplied by the calling surface, and the profile's
signing keypair to certify it, resolved here through the same capability the
provenance key comes from. It is refused before any profile state is read when
the optional ``pdf`` extra is absent, or when the surface supplies no writer.

See Also:
    :func:`~cadrumo.application.modelo.export.load_exportable_revision_target`:
        The shared revision lookup.
    :func:`~cadrumo.application.modelo.export.require_exportable_revision_state`:
        The shared sealed-revision rule.
    :class:`~cadrumo.application.modelo.export_sink.LocalFileExportSink`:
        The one place export bytes land on a local path.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, NonNegativeInt

from ...core.calculation_report_format import CalculationReportDocumentFormat
from ...core.external_constants import OutputLanguage
from ...core.filing_year import FilingYear
from ...core.identity.digest import ContentDigest
from ...core.identity.hex_ids import CalculationRevisionId, FilingRecordId, VerificationReportId, WorkUnitId
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.period import Period
from ...core.time.clock import now as _utc_now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.filing.software_identity import AeatSoftwareIdentityGrade
from ...domain.modelos.calculation_revision import CalculationRevision
from ...domain.modelos.codes import ModeloCode
from ...domain.modelos.errors import ModeloExportError
from ...domain.modelos.filing_record import ModeloRecord, ModeloRecordStatus
from ...domain.modelos.verification_report import VerificationCompletenessStatus
from ...domain.modelos.work_unit import WorkUnit
from ..calculations.verification_report_gate import require_verification_report_coordinates_current
from ..export.errors import ExportFormatError
from ..filing.runtime import build_runtime_schema_provider
from .calculation_report import ModeloCalculationReport, build_modelo_calculation_report
from .calculation_report_document import (
    CalculationReportDocument,
    CalculationSummaryPdfRendering,
    require_calculation_summary_pdf_available,
    serialize_calculation_report,
)
from .calculation_report_provenance_key import derive_calculation_report_provenance_key
from .export import (
    ModeloExportNoActiveBucketError,
    envelope_stamped_software_identity,
    load_exportable_revision_target,
    require_exportable_revision_state,
)
from .export_ports import ModeloExportPorts
from .export_sink import LocalFileExportReceipt, LocalFileExportSink
from .profile_export_binding import resolve_export_identity
from .review_package_signing import ensure_review_package_signing_keypair
from .work_review import build_modelo_work_review_casillas

if TYPE_CHECKING:
    from .calculation_summary_pdf_ports import CalculationSummaryPdfWriter
    from .review_package_signing_ports import ReviewPackageSigningKeypairCapability


class ModeloCalculationReportTaxpayerUnknownError(ModeloExportError):
    """The active profile declares no usable taxpayer identity.

    A calculation report names the filer in full, so a report built without that
    identity would be a record of somebody's declaration without saying whose.
    Refused rather than filled with a placeholder: the profile's synthetic
    stand-in NIF is checksum-valid and would read downstream as a declared one.
    """


class ModeloCalculationReportCommand(BaseModel):
    """Strict input contract for :func:`export_modelo_calculation_report`.

    Attributes:
        calculation_revision_id: Revision to report. Must be sealed --
            verificado-completo, presentado, or a superseded presentado.
        document_format: Serialisation the operator asked for.
        report_language: Language the report's chrome is rendered in. Carried
            explicitly rather than read from the ambient render language so the
            report is a pure function of its inputs and its bytes reproduce.
        output_path: Path the document is published to. Its parent directory must
            already exist; an existing file is refused unless
            ``replace_existing`` is set.
        replace_existing: The operator's explicit choice to replace a file
            already at ``output_path``.
    """

    model_config = STRICT_FROZEN_CONFIG

    calculation_revision_id: CalculationRevisionId
    document_format: CalculationReportDocumentFormat
    report_language: OutputLanguage
    output_path: Path
    replace_existing: bool = False


class ModeloCalculationReportResult(BaseModel):
    """Receipt of one published calculation report.

    Names the file and fingerprints its bytes, and carries the report's own
    canonical digest beside them: the file digest proves which bytes landed, and
    ``report_sha256`` proves which report content they render, so the same
    content published twice in two formats is provably the same report.

    Carries no taxpayer identity. The identity belongs in the artefact the
    operator asked for, not in a machine-readable receipt that reaches a terminal
    and a journal.
    """

    model_config = STRICT_FROZEN_CONFIG

    calculation_revision_id: CalculationRevisionId
    work_unit_id: WorkUnitId
    verification_report_id: VerificationReportId | None
    filing_record_id: FilingRecordId | None
    modelo: ModeloCode
    filing_year: FilingYear
    period: Period
    document_format: CalculationReportDocumentFormat
    report_language: OutputLanguage
    output_path: Path
    byte_size: NonNegativeInt
    file_sha256: ContentDigest
    report_sha256: ContentDigest
    row_count: NonNegativeInt
    software_identity_grade: AeatSoftwareIdentityGrade | None
    local_calculation_notice: str = Field(min_length=1)
    #: Fingerprint of the profile key the document is certified with -- the value
    #: a recipient compares out of band before trusting its signature. ``None``
    #: for a format that carries no signature.
    signing_key_fingerprint: ContentDigest | None = None


def _latest_verification_facts(
    revision: CalculationRevision,
    *,
    export_ports: ModeloExportPorts,
    operation: PinnedAuthorityOperation,
) -> tuple[VerificationReportId | None, VerificationCompletenessStatus | None]:
    """Return the id and verdict of the last verification run for the revision."""
    reports = require_verification_report_coordinates_current(
        export_ports.verification.load(),
        operation=operation,
    ).for_calculation_revision(revision.calculation_revision_id)
    if not reports:
        return None, None
    latest = reports[-1]
    return latest.verification_report_id, latest.completeness_status


def _filing_record_id_for_revision(
    revision: CalculationRevision,
    *,
    export_ports: ModeloExportPorts,
) -> FilingRecordId | None:
    """Return the filing record this revision was filed under, when it was.

    A revision can carry a current record and superseded predecessors of it, so
    the current one wins and the remainder are ordered by id to keep the answer
    stable rather than dependent on catalogue iteration order.
    """
    matching: list[ModeloRecord] = [
        record
        for record in export_ports.filing.load().records.values()
        if record.calculation_revision_id == revision.calculation_revision_id
    ]
    if not matching:
        return None
    current = [record for record in matching if record.status is ModeloRecordStatus.VIGENTE]
    selected = min(current or matching, key=lambda record: record.filing_record_id)
    return selected.filing_record_id


def _software_identity_grade(
    work_unit: WorkUnit,
    *,
    export_ports: ModeloExportPorts,
    operation: PinnedAuthorityOperation,
) -> AeatSoftwareIdentityGrade | None:
    """Return the grade the filing file for this modelo would stamp, if any."""
    schema_provider = build_runtime_schema_provider(
        filing_year=work_unit.period.filing_year,
        period=work_unit.period,
        modelos=(str(work_unit.modelo),),
        operation=operation,
    )
    layouts = schema_provider.get_subview(str(work_unit.modelo)).export_layouts
    identity = envelope_stamped_software_identity(
        layouts[0] if layouts else None,
        product_software_identity=export_ports.product_software_identity,
    )
    return None if identity is None else identity.grade


def _taxpayer_identity(*, active_bucket_id: str, operation: PinnedAuthorityOperation) -> tuple[str, str]:
    """Return the filer's own tax identifier and name, or refuse.

    Read through the one export identity resolver, which already decides that the
    profile preparing a filing IS its taxpayer and presenter -- the product
    exposes no representative or gestor identity -- so the report names the same
    person the fichero-BOE would.

    Raises:
        ModeloCalculationReportTaxpayerUnknownError: The profile is absent or
            declares no usable identity.
    """
    identity = resolve_export_identity(bucket_id=active_bucket_id, operation=operation)
    if identity is None:
        raise ModeloCalculationReportTaxpayerUnknownError(
            translated_message="application.modelo.errors.calculation_report_taxpayer_unknown",
            context={"bucket_id": active_bucket_id},
        )
    presenter, taxpayer = identity
    if taxpayer.full_name is None:
        raise ModeloCalculationReportTaxpayerUnknownError(
            translated_message="application.modelo.errors.calculation_report_taxpayer_unknown",
            context={"bucket_id": active_bucket_id},
        )
    return presenter.tax_id, taxpayer.full_name


def build_modelo_calculation_report_for_revision(
    calculation_revision_id: CalculationRevisionId,
    *,
    active_bucket_id: str,
    export_ports: ModeloExportPorts,
    signing_keypair: ReviewPackageSigningKeypairCapability,
    operation: PinnedAuthorityOperation,
    report_language: OutputLanguage,
    exported_at: datetime,
) -> ModeloCalculationReport:
    """Resolve one sealed revision and assemble its calculation report.

    Separated from publication so a caller that wants the report itself -- a
    preview, a second document format of the same content, a rebuild that proves
    a published document still matches the store -- reaches the same assembly the
    published document is rendered from.

    Raises:
        CalculationRevisionStateError: The revision is not sealed.
        ModeloCalculationReportTaxpayerUnknownError: The profile declares no
            usable taxpayer identity.
    """
    revision, work_unit = load_exportable_revision_target(
        calculation_revision_id,
        active_bucket_id=active_bucket_id,
        export_ports=export_ports,
        operation=operation,
    )
    require_exportable_revision_state(revision)
    # The same two-step resolution the review assembly performs: select the
    # revision metadata first so the snapshot is built at the rung of authority
    # that revision declares, rather than at the strictest rung a modelo filed
    # on AEAT's own sede would refuse.
    selected = operation.revision_for_context(
        str(work_unit.modelo),
        filing_year=work_unit.period.filing_year,
        period=work_unit.period.registry_token,
    )
    snapshot = operation.snapshot(
        str(work_unit.modelo),
        filing_year=work_unit.period.filing_year,
        period=work_unit.period.registry_token,
        revision_id=selected.id,
        grade=selected.effective_authority_grade,
    )
    verification_report_id, verification_outcome = _latest_verification_facts(
        revision,
        export_ports=export_ports,
        operation=operation,
    )
    taxpayer_tax_id, taxpayer_name = _taxpayer_identity(active_bucket_id=active_bucket_id, operation=operation)
    return build_modelo_calculation_report(
        revision=revision,
        work_unit=work_unit,
        review_casillas=build_modelo_work_review_casillas(
            snapshot=snapshot,
            revision=revision,
            operation=operation,
        ),
        taxpayer_tax_id=taxpayer_tax_id,
        taxpayer_name=taxpayer_name,
        verification_report_id=verification_report_id,
        verification_outcome=verification_outcome,
        filing_record_id=_filing_record_id_for_revision(revision, export_ports=export_ports),
        authority_logical_generation=operation.generation.logical_generation,
        software_identity_grade=_software_identity_grade(
            work_unit,
            export_ports=export_ports,
            operation=operation,
        ),
        provenance_key=derive_calculation_report_provenance_key(
            bucket_id=active_bucket_id,
            signing_keypair=signing_keypair,
        ),
        report_language=report_language,
        exported_at=exported_at,
    )


def export_modelo_calculation_report(
    command: ModeloCalculationReportCommand,
    *,
    export_ports: ModeloExportPorts,
    signing_keypair: ReviewPackageSigningKeypairCapability,
    operation: PinnedAuthorityOperation,
    clock: datetime | None = None,
    pdf_writer: CalculationSummaryPdfWriter | None = None,
) -> ModeloCalculationReportResult:
    """Publish one sealed revision's calculation report to the operator's path.

    Local-only: the service never contacts AEAT. The destination is checked
    before the report is assembled, so an unusable path is a typed refusal rather
    than a late failure after taxpayer figures exist in memory, and the bytes are
    staged beside the path and discarded on every exit that does not publish.

    Args:
        command: The revision, document format, language, destination and replace
            choice.
        export_ports: The persisted authorities this invocation reads.
        signing_keypair: The profile's signing-keypair capability, from which the
            provenance digest key is derived in memory, and which certifies a
            summary PDF.
        operation: The caller's pinned authority operation.
        clock: UTC instant stamped as the export timestamp; the current instant
            when omitted.
        pdf_writer: The outbound writer that draws a summary PDF. Required for
            the PDF format and ignored by every other.

    Returns:
        :class:`ModeloCalculationReportResult`: The published file's identity and
        the report's own canonical digest.

    Raises:
        CalculationSummaryPdfUnavailableError: The PDF was asked for and the
            optional ``pdf`` extra is not installed.
        ExportFormatError: The PDF was asked for and the surface supplied no
            writer.
        ModeloExportNoActiveBucketError: No active profile bucket is configured.
        ModeloExportOutputPathError: The destination cannot receive the document.
    """
    from ...core.bucket_pointer import resolve_active_bucket_id

    if command.document_format is CalculationReportDocumentFormat.PDF:
        require_calculation_summary_pdf_available()
        if pdf_writer is None:
            raise ExportFormatError(
                translated_message="errors.refused.refused_export_format",
                context={"export_format": str(command.document_format)},
            )
    active_bucket_id = resolve_active_bucket_id()
    if active_bucket_id is None:
        raise ModeloExportNoActiveBucketError(
            translated_message="application.modelo.errors.export_no_active_bucket",
        )
    sink = LocalFileExportSink(path=command.output_path, replace_existing=command.replace_existing)
    sink.require_writable()
    report = build_modelo_calculation_report_for_revision(
        command.calculation_revision_id,
        active_bucket_id=active_bucket_id,
        export_ports=export_ports,
        signing_keypair=signing_keypair,
        operation=operation,
        report_language=command.report_language,
        exported_at=clock or _utc_now(),
    )
    document = serialize_calculation_report(
        report,
        document_format=command.document_format,
        pdf_rendering=(
            None
            if pdf_writer is None or command.document_format is not CalculationReportDocumentFormat.PDF
            else CalculationSummaryPdfRendering(
                writer=pdf_writer,
                keypair=ensure_review_package_signing_keypair(
                    bucket_id=active_bucket_id,
                    signing_keypair=signing_keypair,
                ),
            )
        ),
    )
    return _report_result(
        report=report,
        document=document,
        receipt=sink.write(document.payload),
    )


def _report_result(
    *,
    report: ModeloCalculationReport,
    document: CalculationReportDocument,
    receipt: LocalFileExportReceipt,
) -> ModeloCalculationReportResult:
    """Compose the receipt from the report, the document and the landed file.

    The byte size and digest come from the landed file rather than from the
    in-memory document, so the numbers the operator keeps are measured on what is
    actually on disk.
    """
    header = report.header
    return ModeloCalculationReportResult(
        calculation_revision_id=header.calculation_revision_id,
        work_unit_id=header.work_unit_id,
        verification_report_id=header.verification_report_id,
        filing_record_id=header.filing_record_id,
        modelo=header.modelo,
        filing_year=header.filing_year,
        period=header.period,
        document_format=document.document_format,
        report_language=header.report_language,
        output_path=receipt.path,
        byte_size=receipt.byte_size,
        file_sha256=receipt.sha256,
        report_sha256=report.report_sha256,
        row_count=header.row_count,
        software_identity_grade=header.software_identity_grade,
        local_calculation_notice=header.local_calculation_notice,
        signing_key_fingerprint=document.signing_key_fingerprint,
    )


__all__ = [
    "ModeloCalculationReportCommand",
    "ModeloCalculationReportResult",
    "ModeloCalculationReportTaxpayerUnknownError",
    "build_modelo_calculation_report_for_revision",
    "export_modelo_calculation_report",
]
