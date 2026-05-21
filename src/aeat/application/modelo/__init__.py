"""Application services for modelo work-unit lifecycle.

The modelo work-unit verbs (``create``, ``list``, ``status``,
``rename``) call into this package. The CLI layer at
``aeat.entrypoints.cli._modelo`` is a thin Typer transport over
the services exposed here.

Bucket scoping is honoured at the API boundary: every action
accepts an explicit ``bucket_id`` rather than implicitly reading
the active profile. The CLI layer derives ``bucket_id`` from the
active profile when the caller did not pass one explicitly; this
keeps the application service unit-testable without a workflow-
state fixture.
"""

from __future__ import annotations

from ._actions import (
    AmendmentEvidenceMissingError,
    AmendmentOverrideCasillaError,
    AmendmentTargetStateError,
    AmendmentVerificationRefusedError,
    CalculationRegistryUnavailableError,
    CalculationRevisionNotFoundError,
    CalculationRevisionStateError,
    CasillaProvenanceMissingError,
    ExternalModeloImportError,
    ModeloAggregationBindingError,
    ModeloIvaWalletReconciliationBlocked,
    ModeloRecordNotFoundError,
    ModeloWorkflowGateError,
    VerificationReportNotFoundError,
    WorkUnitAlreadyDiscardedError,
    WorkUnitMutationRefusedError,
    WorkUnitNotFoundError,
    amend_modelo_revision,
    calculate_modelo_revision,
    calculate_modelo_revision_from_bucket_aggregation,
    create_work_unit,
    discard_work_unit,
    file_modelo_revision,
    get_calculation_revision,
    get_filing_record,
    get_verification_report,
    get_work_unit,
    import_external_filing_evidence,
    list_calculation_revisions,
    list_filing_records,
    list_verification_reports,
    list_work_units,
    mark_revision_verificado_completo,
    rename_work_unit,
    verify_modelo_revision,
)
from ._borrador_binding import (
    Modelo100BorradorBindingCommand,
    Modelo100BorradorBindingError,
    Modelo100BorradorBindingResult,
    resolve_modelo_100_borrador_bindings,
)
from ._history import (
    WorkUnitHistory,
    WorkUnitHistoryEvent,
    assemble_work_unit_history,
)

__all__ = [
    "AmendmentEvidenceMissingError",
    "AmendmentOverrideCasillaError",
    "AmendmentTargetStateError",
    "AmendmentVerificationRefusedError",
    "CalculationRegistryUnavailableError",
    "CalculationRevisionNotFoundError",
    "CalculationRevisionStateError",
    "CasillaProvenanceMissingError",
    "ExternalModeloImportError",
    "Modelo100BorradorBindingCommand",
    "Modelo100BorradorBindingError",
    "Modelo100BorradorBindingResult",
    "ModeloAggregationBindingError",
    "ModeloIvaWalletReconciliationBlocked",
    "ModeloRecordNotFoundError",
    "ModeloWorkflowGateError",
    "VerificationReportNotFoundError",
    "WorkUnitAlreadyDiscardedError",
    "WorkUnitHistory",
    "WorkUnitHistoryEvent",
    "WorkUnitMutationRefusedError",
    "WorkUnitNotFoundError",
    "amend_modelo_revision",
    "assemble_work_unit_history",
    "calculate_modelo_revision",
    "calculate_modelo_revision_from_bucket_aggregation",
    "create_work_unit",
    "discard_work_unit",
    "file_modelo_revision",
    "get_calculation_revision",
    "get_filing_record",
    "get_verification_report",
    "get_work_unit",
    "import_external_filing_evidence",
    "list_calculation_revisions",
    "list_filing_records",
    "list_verification_reports",
    "list_work_units",
    "mark_revision_verificado_completo",
    "rename_work_unit",
    "resolve_modelo_100_borrador_bindings",
    "verify_modelo_revision",
]
