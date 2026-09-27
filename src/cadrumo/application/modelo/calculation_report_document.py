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

See Also:
    :mod:`cadrumo.application.modelo.calculation_report`:
        Builds the typed report this module renders.
    :func:`~cadrumo.application.export.tabular.serialize_tabular_rows`:
        The one tabular serialiser the row table is produced by.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Final

from pydantic import BaseModel, Field, NonNegativeInt, model_validator

from ...core.calculation_report_format import CalculationReportDocumentFormat
from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.external_constants import CSV_MIME_TYPE, UTF_8_ENCODING
from ...core.hashing import sha256_hex
from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_CONFIG
from ..export.errors import ExportFormatError
from ..export.tabular import ExportSerializationFormat, serialize_tabular_rows
from .calculation_report import (
    ModeloCalculationReport,
    ModeloCalculationReportRow,
)

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
}
"""Media type and filename extension each document format is named by on the wire."""

_REFUSED_DOCUMENT_FORMAT_MESSAGE = "errors.refused.refused_export_format"


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
    if isinstance(value, Mapping):
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


DOCUMENT_SERIALIZERS: Final[Mapping[CalculationReportDocumentFormat, Callable[[ModeloCalculationReport], bytes]]] = {
    CalculationReportDocumentFormat.CSV: _serialize_csv,
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
) -> CalculationReportDocument:
    """Serialise ``report`` into ``document_format``.

    Args:
        report: The typed calculation report to render. Its content is rendered
            as-is; nothing is added, derived or omitted here.
        document_format: The serialisation the operator asked for.

    Returns:
        :class:`CalculationReportDocument`: The payload with the byte size,
        digest and row count it carries.

    Raises:
        ExportFormatError: ``document_format`` has no serialiser.
    """
    serializer = DOCUMENT_SERIALIZERS.get(document_format)
    wire_names = _FORMAT_WIRE_NAMES.get(document_format)
    if serializer is None or wire_names is None:
        raise ExportFormatError(
            translated_message=_REFUSED_DOCUMENT_FORMAT_MESSAGE,
            context={"export_format": str(document_format)},
        )
    payload = serializer(report)
    media_type, extension = wire_names
    return CalculationReportDocument(
        document_format=document_format,
        media_type=media_type,
        filename_extension=extension,
        payload=payload,
        byte_size=len(payload),
        sha256=sha256_hex(payload),
        row_count=len(report.rows),
    )


__all__ = [
    "CALCULATION_REPORT_CSV_FIELDNAMES",
    "CALCULATION_REPORT_CSV_PREAMBLE_PREFIX",
    "CALCULATION_REPORT_DIGEST_PREAMBLE_KEY",
    "DOCUMENT_SERIALIZERS",
    "CalculationReportDocument",
    "calculation_report_csv_preamble_lines",
    "calculation_report_csv_row",
    "serialize_calculation_report",
]
