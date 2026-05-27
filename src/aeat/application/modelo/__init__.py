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

Verification boundary
---------------------
``verify_modelo_revision`` enforces a four-layer gate before the
``VERIFICADO_COMPLETO`` state transition is granted:

1. **State machine** -- the target revision must be in ``BORRADOR``
   state; any other state raises :exc:`CalculationRevisionStateError`.

2. **Per-casilla required-input gate (Layer 1)** -- every casilla
   declared ``required = true`` and ``input_kind = "manual"`` in the
   registry must be present in the revision's ``inputs_snapshot``.
   Absent casillas produce :attr:`ModeloVerificationFindingKind.MISSING_REQUIRED_CASILLA`
   findings and set ``completeness_status`` to ``INCOMPLETE``.

3. **Cross-casilla predicate gate (Layer 2)** -- each
   :class:`~aeat.domain.calculations.registry.VerificationPredicateDefinition`
   attached to the revision's registry snapshot is evaluated against the
   stored ``casilla_values``.  A failing predicate produces a
   :attr:`ModeloVerificationFindingKind.BLOCKING_RULE` finding.

4. **Provenance re-validation** -- :func:`_assert_revision_content_integrity`
   re-derives the SHA-256 content address from the stored payload and
   raises :exc:`StoredCalculationDriftError` if it does not match the
   persisted ``calculation_revision_id``.  This defends against raw-storage
   tampering or schema-migration bugs that mutate the payload without
   updating the content-addressed id.

Only when layers 1-3 produce zero blocking findings AND layer 4 passes
does ``verify_modelo_revision`` grant ``VERIFICADO_COMPLETO`` and
persist the :class:`~aeat.domain.modelos._verification_report.ModeloVerificationReport`.
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
    StoredCalculationDriftError,
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
    workflow_period_for_work_unit,
)
from ._borrador_binding import (
    Modelo100BorradorBindingCommand,
    Modelo100BorradorBindingError,
    Modelo100BorradorBindingResult,
    Modelo100BorradorSourceResolver,
    resolve_modelo_100_borrador_bindings,
)
from ._history import (
    WorkUnitHistory,
    WorkUnitHistoryEvent,
    assemble_work_unit_history,
)
from ._result_summary import (
    CalculationResultSummary,
    ResultSummaryRow,
    calculation_result_summary,
)

__all__ = [
    "AmendmentEvidenceMissingError",
    "AmendmentOverrideCasillaError",
    "AmendmentTargetStateError",
    "AmendmentVerificationRefusedError",
    "CalculationRegistryUnavailableError",
    "CalculationResultSummary",
    "CalculationRevisionNotFoundError",
    "CalculationRevisionStateError",
    "CasillaProvenanceMissingError",
    "ExternalModeloImportError",
    "Modelo100BorradorBindingCommand",
    "Modelo100BorradorBindingError",
    "Modelo100BorradorBindingResult",
    "Modelo100BorradorSourceResolver",
    "ModeloAggregationBindingError",
    "ModeloIvaWalletReconciliationBlocked",
    "ModeloRecordNotFoundError",
    "ModeloWorkflowGateError",
    "ResultSummaryRow",
    "StoredCalculationDriftError",
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
    "calculation_result_summary",
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
    "workflow_period_for_work_unit",
]
