"""The artefact one modelo export produces.

A modelo export reads one selected saved calculation revision and publishes
to one operator-chosen file. Sealed reports and filing files retain their own
verification gates; saved review XLSX also permits provisional drafts.
What differs is the artefact: the AEAT-compatible
filing file the operator presents, or a local record of the calculation for review
and archiving. This closed axis names that choice once, so a surface offering it
renders the set rather than inventing its own vocabulary.

Each member names exactly one artefact in exactly one serialisation, so a surface
never has to decide whether a second field applies to the choice the operator
made. A new serialisation of an existing artefact family is a new member here.

The axis is declared in ``core`` per the core-authority discipline: closed
operator-facing axes live here, are hydrated at the request boundary, and are
asserted as members rather than strings in tests.
"""

from __future__ import annotations

from enum import StrEnum


class ModeloExportArtefact(StrEnum):
    """Closed set of artefacts a modelo export can publish.

    Attributes:
        FICHERO_BOE: The AEAT-compatible fixed-width or XML filing file for the
            revision's modelo and period. This is the artefact an operator
            presents at AEAT; it is refused when the revision's registry
            snapshot renders no such layout.
        CALCULATION_REPORT_CSV: The revision's calculation report as a delimited
            table with fixed columns. A local record of what the calculation
            holds, never presentable at AEAT.
        CALCULATION_REPORT_PDF: The revision's calculation report as the signed
            calculation summary: pages a person reads, carrying the report's own
            data and a signed integrity statement. A local record, never
            presentable at AEAT, and publishable only where the optional ``pdf``
            extra is installed.
        CALCULATION_REVIEW_XLSX: An immutable saved review workbook, including
            original form geometry where retained. Drafts remain provisional;
            this workbook is never presentable at AEAT.
    """

    FICHERO_BOE = "fichero_boe"
    CALCULATION_REPORT_CSV = "calculation_report_csv"
    CALCULATION_REPORT_PDF = "calculation_report_pdf"
    CALCULATION_REVIEW_XLSX = "calculation_review_xlsx"


__all__ = ["ModeloExportArtefact"]
