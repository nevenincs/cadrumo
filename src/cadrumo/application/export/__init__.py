"""Application-level export serialization helpers.

Serializes tabular application data into the operator-chosen output format
for the export verbs, separate from the registry-driven fichero-BOE modelo
export. Pure value logic with no I/O.

The package returns payload bytes plus integrity metadata to its caller;
the caller owns any destination path, bucket event, or secure-storage
state. That keeps generic CSV/JSONL/XLSX rendering distinct from modelo
BOE exports and calculation workbook exports.

Major declarations:

* :func:`application.export.serialize_tabular_rows` — render rows into a
  :class:`application.export.TabularExportResult`.
* :class:`application.export.ExportSerializationFormat` — the closed set
  of supported output formats.
* :class:`application.export._errors.ExportFieldError` and
  :class:`application.export._errors.ExportFormatError` — typed
  validation failures for export callers.

See Also:
    :func:`application.ledger.actions_export.export_ledger_transactions`
        Ledger command service that calls this serializer, then owns bucket
        events and operator output paths.
    :func:`application.modelo.export_modelo_revision`
        Registry-driven fichero-BOE export for verified or filed modelo
        revisions.
    :mod:`application.storage.calc_sheets`
        Registry workbook export-plan surface for offline and Sheets transports.
"""

from __future__ import annotations

from ._google_operation import (
    GOOGLE_SHEETS_EXPORT_OPERATION_DEFINITION_ID,
    GOOGLE_SHEETS_EXPORT_PHASE_APPLY,
    GOOGLE_SHEETS_EXPORT_PHASE_PLAN,
    GOOGLE_SHEETS_EXPORT_PHASE_PREFLIGHT,
    GoogleSheetsExportCapabilityDisabledError,
    GoogleSheetsExportOperationRequest,
    GoogleSheetsExportOperationResult,
    GoogleSheetsExportRemoteResult,
    GoogleSheetsExportRootFolderRequiredError,
    GoogleSheetsExportService,
    build_google_sheets_export_operation_definition,
    build_google_sheets_export_operation_registration,
    build_google_sheets_export_service,
)
from ._tabular import (
    ExportSerializationFormat,
    TabularExportResult,
    serialize_tabular_rows,
    verify_export_metadata,
)

__all__ = [
    "GOOGLE_SHEETS_EXPORT_OPERATION_DEFINITION_ID",
    "GOOGLE_SHEETS_EXPORT_PHASE_APPLY",
    "GOOGLE_SHEETS_EXPORT_PHASE_PLAN",
    "GOOGLE_SHEETS_EXPORT_PHASE_PREFLIGHT",
    "ExportSerializationFormat",
    "GoogleSheetsExportCapabilityDisabledError",
    "GoogleSheetsExportOperationRequest",
    "GoogleSheetsExportOperationResult",
    "GoogleSheetsExportRemoteResult",
    "GoogleSheetsExportRootFolderRequiredError",
    "GoogleSheetsExportService",
    "TabularExportResult",
    "build_google_sheets_export_operation_definition",
    "build_google_sheets_export_operation_registration",
    "build_google_sheets_export_service",
    "serialize_tabular_rows",
    "verify_export_metadata",
]
