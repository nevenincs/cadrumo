"""Application-level export serialization helpers.

Serializes tabular application data into the operator-chosen output format
for the export verbs, separate from the registry-driven fichero-BOE modelo
export. Pure value logic with no I/O.

The package returns payload bytes plus integrity metadata to its caller;
the caller owns any destination path, bucket event, or secure-storage
state. That keeps generic CSV/JSONL/XLSX rendering distinct from modelo
BOE exports and calculation workbook exports.

Major declarations:

* :func:`serialize_tabular_rows` — render rows into a
  :class:`TabularExportResult`.
* :class:`ExportSerializationFormat` — the closed set of supported output
  formats.
* :class:`~aeat.application.export._errors.ExportFieldError` and
  :class:`~aeat.application.export._errors.ExportFormatError` — typed
  validation failures for export callers.

See Also:
    :func:`aeat.application.ledger.export_ledger_transactions`
        Ledger command service that calls this serializer, then owns bucket
        events and operator output paths.
    :func:`aeat.application.modelo.export_modelo_revision`
        Registry-driven fichero-BOE export for verified or filed modelo
        revisions.
    :mod:`aeat.application.storage.calc_sheets`
        Registry workbook export-plan surface for offline and Sheets transports.
"""

from __future__ import annotations

from ._tabular import ExportSerializationFormat, TabularExportResult, serialize_tabular_rows

__all__ = [
    "ExportSerializationFormat",
    "TabularExportResult",
    "serialize_tabular_rows",
]
