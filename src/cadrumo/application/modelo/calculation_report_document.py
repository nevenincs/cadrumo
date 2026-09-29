"""Serialise one modelo calculation report into an operator-chosen document.

The report decides what a document says; this module decides only how those
facts are laid out. Nothing here reads the registry, the ledger or a repository,
and nothing here derives a value: a serialiser that computed anything would be a
second place where a report's content is decided, and two formats of one revision
could then disagree.

The CSV document is a commented preamble carrying the report's header facts and
its content digest, followed by the fixed-column table of its rows. The table is
produced by the product's one tabular serialiser rather than a second CSV writer,
so quoting, line terminator and encoding match every other delimited export the
product emits. The preamble lines lead with ``#`` and carry no delimiter, so the
product's own tabular reader resolves them as metadata above the header rather
than as table rows.

The PDF document is the calculation summary. It embeds the report's canonical
bytes and exactly the CSV document above, presents the strings
:mod:`~cadrumo.application.modelo.calculation_summary_presentation` decides, and
is signed through the profile key the caller supplies. Its pages are drawn by an
outbound adapter the caller supplies too, because writing one needs the optional
``pdf`` extra and this module must import without it.

See Also:
    :mod:`cadrumo.application.modelo.calculation_report`:
        Builds the typed report this module renders.
    :func:`~cadrumo.application.export.tabular.serialize_tabular_rows`:
        The one tabular serialiser the row table is produced by.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, Field, NonNegativeInt, model_validator

from ...core.calculation_report_format import CalculationReportDocumentFormat
from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.external_constants import CSV_MIME_TYPE, PDF_MIME_TYPE, UTF_8_ENCODING
from ...core.hashing import sha256_hex
from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.optional_extras import PDF_EXTRA, MissingOptionalExtraError, require_optional_extra
from ...core.product_identity import PRODUCT_IDENTITY
from ...core.type_guards import is_str_keyed_dict
from ...domain.modelos.errors import ModeloExportError
from ..export.errors import ExportFormatError
from ..export.tabular import ExportSerializationFormat, serialize_tabular_rows
from .calculation_report import (
    ModeloCalculationReport,
    ModeloCalculationReportRow,
)
from .calculation_report_certification import (
    CalculationReportCertification,
    certify_calculation_report,
    signing_key_fingerprint,
)
from .calculation_summary_pdf_ports import CalculationSummaryPdfRequest, CalculationSummaryPdfWriter
from .calculation_summary_presentation import build_calculation_summary_presentation

if TYPE_CHECKING:
    from .review_package_signing import ReviewPackageSigningKeypair

CALCULATION_REPORT_CSV_FIELDNAMES: Final[tuple[str, ...]] = (
    "casilla_id",
    "casilla_number",
    "section_path",
    "label",
    "row_role",
    "semantic_role",
    "declared_input_kind",
    "formula_id",
    "realised_kind",
    "value_state",
    "value",
    "legal_refs",
    "source_refs",
    "source_provenance",
)
"""The fixed columns of a calculation report CSV table, in order.

``casilla_id`` leads deliberately. The product's tabular reader classifies a
data row whose leading cell folds to an aggregate word -- ``total``, ``suma`` --
as an appended summary rather than a movement, so a leading section or label
column would make some modelos' own section names disappear from a parse-back.

``row_role`` is what lets a reader separate an operator input from a derived
figure, a settlement subtotal and the declaration's result without consulting the
registry; ``semantic_role``, ``declared_input_kind`` and ``formula_id`` follow it
as the registry declarations that role was derived from.
"""

CALCULATION_REPORT_CSV_PREAMBLE_PREFIX: Final[str] = "# "
"""Marker that makes a header-fact line metadata rather than a table row."""

CALCULATION_REPORT_DIGEST_PREAMBLE_KEY: Final[str] = "report_sha256"
"""Preamble key carrying the report's own content digest.

The digest is derived from the report rather than stored on its header, so it is
named here as the one preamble line that is not a header field.
"""

_SECTION_PATH_SEPARATOR: Final[str] = " / "
_REFERENCE_SEPARATOR: Final[str] = " "
_PROVENANCE_FIELD_SEPARATOR: Final[str] = "|"
_PROVENANCE_ROW_SEPARATOR: Final[str] = " "

_FORMAT_WIRE_NAMES: Final[Mapping[CalculationReportDocumentFormat, tuple[str, str]]] = {
    CalculationReportDocumentFormat.CSV: (CSV_MIME_TYPE, "csv"),
    CalculationReportDocumentFormat.PDF: (PDF_MIME_TYPE, "pdf"),
}
"""Media type and filename extension each document format is named by on the wire."""

_REFUSED_DOCUMENT_FORMAT_MESSAGE = "errors.refused.refused_export_format"


class CalculationSummaryPdfUnavailableError(ModeloExportError):
    """This installation cannot write a calculation summary PDF.

    Raised when the optional ``pdf`` extra is not installed, before any profile
    state is read, so an operator learns the destination is unavailable -- and
    how to make it available -- rather than meeting a late import failure after
    taxpayer figures were assembled. Verifying a summary needs no extra and is
    never refused for this reason.
    """


def require_calculation_summary_pdf_available() -> None:
    """Refuse the summary PDF destination when its optional extra is absent.

    Raises:
        CalculationSummaryPdfUnavailableError: The ``pdf`` extra is not installed.
    """
    try:
        require_optional_extra(PDF_EXTRA)
    except MissingOptionalExtraError as exc:
        raise CalculationSummaryPdfUnavailableError(
            translated_message="application.modelo.errors.calculation_summary_pdf_unavailable",
            context={"extra": PDF_EXTRA.extra, "import_name": PDF_EXTRA.import_name},
        ) from exc


@dataclass(frozen=True, slots=True)
class CalculationSummaryPdfRendering:
    """What producing a summary PDF needs beyond the report itself.

    ``writer`` is the outbound adapter that draws and assembles the pages;
    ``keypair`` is the profile's signing keypair, held in memory for the one
    signature the summary carries and never passed to the writer.
    """

    writer: CalculationSummaryPdfWriter
    keypair: ReviewPackageSigningKeypair


class CalculationReportDocument(BaseModel):
    """One serialised calculation report and the facts that identify its bytes.

    The facts are validated against the payload they describe, so a caller that
    logs or publishes the digest cannot report the digest of something else. The
    payload carries taxpayer figures and the filer's own identity: it is returned
    to the caller, never written or logged here.
    """

    model_config = STRICT_FROZEN_CONFIG

    document_format: CalculationReportDocumentFormat
    media_type: str = Field(min_length=1)
    filename_extension: str = Field(min_length=1)
    payload: bytes
    byte_size: NonNegativeInt
    sha256: ContentDigest
    #: Rows of the report the payload carries, excluding any header or preamble.
    row_count: NonNegativeInt
    #: Fingerprint of the key the document's integrity statement is signed with,
    #: for the formats that carry one; ``None`` for a format that is not signed.
    signing_key_fingerprint: ContentDigest | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _facts_describe_the_payload(self) -> CalculationReportDocument:
        if self.byte_size != len(self.payload):
            raise ValueError(
                f"calculation report byte_size {self.byte_size} does not match the payload length {len(self.payload)}",
            )
        if self.sha256 != sha256_hex(self.payload):
            raise ValueError("calculation report sha256 does not match the payload digest")
        wire_names = _FORMAT_WIRE_NAMES.get(self.document_format)
        if wire_names is None:
            raise ValueError(f"calculation report format {self.document_format.value!r} declares no wire names")
        expected_media_type, expected_extension = wire_names
        if self.media_type != expected_media_type:
            raise ValueError("calculation report media type does not match its document format")
        if self.filename_extension != expected_extension:
            raise ValueError("calculation report filename extension does not match its document format")
        return self


def calculation_report_csv_row(row: ModeloCalculationReportRow) -> dict[str, str]:
    """Render one report row as the fixed CSV columns.

    An absent or not-applicable row leaves ``value`` empty and says which state
    it is in ``value_state``, so it stays distinguishable from the proven zero
    that renders as ``value_state=value`` with ``value=0``.
    """
    return {
        "casilla_id": str(row.casilla_id),
        "casilla_number": row.number,
        "section_path": _SECTION_PATH_SEPARATOR.join(row.section_path),
        "label": row.label,
        "row_role": row.row_role.value,
        "semantic_role": row.semantic_role or "",
        "declared_input_kind": row.declared_input_kind.value,
        "formula_id": "" if row.formula_id is None else str(row.formula_id),
        "realised_kind": row.realised_kind.value,
        "value_state": row.value_state.value,
        "value": "" if row.value is None else str(row.value),
        "legal_refs": _REFERENCE_SEPARATOR.join(str(ref) for ref in row.legal_refs),
        "source_refs": _REFERENCE_SEPARATOR.join(str(ref) for ref in row.source_refs),
        "source_provenance": _PROVENANCE_ROW_SEPARATOR.join(
            _PROVENANCE_FIELD_SEPARATOR.join(
                (
                    trace.resolver_id,
                    trace.contributor_source_kind,
                    trace.lineage_role.value,
                    trace.source_ref_digest,
                    trace.source_content_digest or "",
                ),
            )
            for trace in row.source_provenance
        ),
    }


def calculation_report_csv_preamble_lines(report: ModeloCalculationReport) -> tuple[str, ...]:
    """Render the report's header facts and content digest as commented lines.

    Every line is one ``# key: value`` pair carrying no delimiter, which is what
    keeps the facts above the table addressable by a reader and out of the
    rectangle the table occupies. The content digest joins the header facts under
    its own key so a reader can check the rows they received against it.
    """
    facts: dict[str, object] = dict(report.header.model_dump(mode="json"))
    facts[CALCULATION_REPORT_DIGEST_PREAMBLE_KEY] = report.report_sha256
    return tuple(
        f"{CALCULATION_REPORT_CSV_PREAMBLE_PREFIX}{key}: {_preamble_value(facts[key])}" for key in sorted(facts)
    )


def _preamble_value(value: object) -> str:
    """Render one header fact for a single-field preamble line."""
    if value is None:
        return ""
    if is_str_keyed_dict(value):
        return _REFERENCE_SEPARATOR.join(f"{key}={value[key]}" for key in sorted(value))
    return str(value)


def _serialize_csv(report: ModeloCalculationReport) -> bytes:
    preamble = "".join(f"{line}\n" for line in calculation_report_csv_preamble_lines(report))
    table = serialize_tabular_rows(
        [calculation_report_csv_row(row) for row in report.rows],
        fieldnames=CALCULATION_REPORT_CSV_FIELDNAMES,
        export_format=ExportSerializationFormat.CSV,
    )
    return preamble.encode(UTF_8_ENCODING) + table.payload


def serialize_calculation_report_csv(report: ModeloCalculationReport) -> bytes:
    """Return the CSV document's bytes: the preamble, then the fixed-column table.

    Public because the summary PDF embeds exactly these bytes, and a verifier
    proves an embedded CSV was derived from the embedded report by re-running it.
    """
    return _serialize_csv(report)


def _serialize_pdf(report: ModeloCalculationReport, rendering: CalculationSummaryPdfRendering) -> bytes:
    """Render the summary PDF, embedding the report and its CSV and signing both."""
    csv_bytes = _serialize_csv(report)
    csv_sha256 = sha256_hex(csv_bytes)
    keypair = rendering.keypair

    def certify(visible_layer_sha256: str, /) -> CalculationReportCertification:
        return certify_calculation_report(
            report,
            csv_sha256=csv_sha256,
            visible_layer_sha256=visible_layer_sha256,
            keypair=keypair,
        )

    request = CalculationSummaryPdfRequest(
        presentation=build_calculation_summary_presentation(
            report,
            csv_sha256=csv_sha256,
            signing_key_fingerprint=signing_key_fingerprint(keypair.public_key_hex),
            brand=PRODUCT_IDENTITY.display_name,
        ),
        report_bytes=report.canonical_bytes(),
        report_sha256=report.report_sha256,
        csv_bytes=csv_bytes,
        exported_at=report.header.exported_at,
    )
    return rendering.writer(request, certify=certify)


def _csv_document(report: ModeloCalculationReport, _rendering: CalculationSummaryPdfRendering | None) -> bytes:
    return _serialize_csv(report)


def _pdf_document(report: ModeloCalculationReport, rendering: CalculationSummaryPdfRendering | None) -> bytes:
    if rendering is None:
        # A surface that offers the PDF must supply its writer and the profile
        # key; one that does not is refused as not offering the format.
        raise ExportFormatError(
            translated_message=_REFUSED_DOCUMENT_FORMAT_MESSAGE,
            context={"export_format": str(CalculationReportDocumentFormat.PDF)},
        )
    return _serialize_pdf(report, rendering)


DOCUMENT_SERIALIZERS: Final[
    Mapping[
        CalculationReportDocumentFormat,
        Callable[[ModeloCalculationReport, CalculationSummaryPdfRendering | None], bytes],
    ]
] = {
    CalculationReportDocumentFormat.CSV: _csv_document,
    CalculationReportDocumentFormat.PDF: _pdf_document,
}
"""The serialiser enrolled for each document format.

Declared as a table rather than a chain of branches so a format without a
serialiser is a missing enrolment the owning test detects, not a branch a reader
has to find.
"""


def serialize_calculation_report(
    report: ModeloCalculationReport,
    *,
    document_format: CalculationReportDocumentFormat,
    pdf_rendering: CalculationSummaryPdfRendering | None = None,
) -> CalculationReportDocument:
    """Serialise ``report`` into ``document_format``.

    Args:
        report: The typed calculation report to render. Its content is rendered
            as-is; nothing is added, derived or omitted here.
        document_format: The serialisation the operator asked for.
        pdf_rendering: The writer and signing keypair a PDF needs; ignored by
            every other format.

    Returns:
        :class:`CalculationReportDocument`: The payload with the byte size,
        digest and row count it carries.

    Raises:
        ExportFormatError: ``document_format`` has no serialiser, or is the PDF
            and no rendering was supplied.
    """
    serializer = DOCUMENT_SERIALIZERS.get(document_format)
    wire_names = _FORMAT_WIRE_NAMES.get(document_format)
    if serializer is None or wire_names is None:
        raise ExportFormatError(
            translated_message=_REFUSED_DOCUMENT_FORMAT_MESSAGE,
            context={"export_format": str(document_format)},
        )
    payload = serializer(report, pdf_rendering)
    media_type, extension = wire_names
    return CalculationReportDocument(
        document_format=document_format,
        media_type=media_type,
        filename_extension=extension,
        payload=payload,
        byte_size=len(payload),
        sha256=sha256_hex(payload),
        row_count=len(report.rows),
        signing_key_fingerprint=(
            None
            if pdf_rendering is None or document_format is not CalculationReportDocumentFormat.PDF
            else signing_key_fingerprint(pdf_rendering.keypair.public_key_hex)
        ),
    )


__all__ = [
    "CALCULATION_REPORT_CSV_FIELDNAMES",
    "CALCULATION_REPORT_CSV_PREAMBLE_PREFIX",
    "CALCULATION_REPORT_DIGEST_PREAMBLE_KEY",
    "DOCUMENT_SERIALIZERS",
    "CalculationReportDocument",
    "CalculationSummaryPdfRendering",
    "CalculationSummaryPdfUnavailableError",
    "calculation_report_csv_preamble_lines",
    "calculation_report_csv_row",
    "require_calculation_summary_pdf_available",
    "serialize_calculation_report",
    "serialize_calculation_report_csv",
]
