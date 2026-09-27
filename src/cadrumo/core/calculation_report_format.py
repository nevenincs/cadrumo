"""The document format one modelo calculation report is serialised into.

A calculation report is a local record of what a verified or filed calculation
revision holds: header facts plus one row per casilla the revision carries. The
report is built once and serialised per format, so this closed axis names the
serialisation a caller asked for and nothing about the report's content.

The axis is declared in ``core`` per the core-authority discipline: closed
operator-facing axes live here, are hydrated at the command boundary, and are
asserted as members rather than strings in tests. It is deliberately distinct
from :class:`~application.export.tabular.ExportSerializationFormat`, which names
the backend serialisations of an arbitrary ledger row set; a calculation report
is one typed document whose formats are chosen by an operator.
"""

from __future__ import annotations

from enum import StrEnum


class CalculationReportDocumentFormat(StrEnum):
    """Closed set of serialisations of one modelo calculation report.

    Attributes:
        CSV: The report's rows as a delimited table with fixed columns, above a
            commented preamble carrying the report's header facts. Machine
            readable, and the format a reviewer diffs or loads into a sheet.
    """

    CSV = "csv"


__all__ = ["CalculationReportDocumentFormat"]
