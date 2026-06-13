"""Modelo work-unit lifecycle actions.

Each action loads the catalogue, applies a single mutation in
memory (or returns a read view), and writes the catalogue back.
The catalogue is content-addressed by ``work_unit_id`` so
deterministic derivation lets ``create_work_unit`` be idempotent:
calling it twice with the same four-axis key returns the same
record without producing a duplicate.

The action signatures take an explicit ``bucket_id`` so the
service layer is unit-testable without a workflow-state fixture.

Actions obtain a :class:`RegistrySnapshot` for the target revision from a
:class:`ValidatedRegistryAuthority`, then feed :class:`ModeloRevision` data
into the formula engine to produce or amend a calculation revision. Invoice
evidence is loaded from an :class:`InvoiceCatalogueRepository` when the
revision's source mesh includes invoice-backed bindings, and the
:class:`TransactionCatalogue` is consumed by the ledger aggregation step.
Ledger transactions are loaded via :class:`TransactionCatalogueRepository`.
Every mutating action emits a typed event to :class:`BucketEventHistoryRepository`.
The deadline window is derived from a :class:`TaxpayerProfile` when the
modelo has an obligation schedule.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...domain.modelos._errors import ModeloError
from ..workflow import (
    WorkflowInputMismatchError as WorkflowInputMismatchError,
)
from . import _iva_wallet_gate
from . import _m210_rate as _m210_rate
from ._action_errors import (
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
    ModeloApplicabilityFilterError,
    ModeloCrossPeriodCleanStateError,
    ModeloRecordNotFoundError,
    ModeloWorkflowGateError,
    StoredCalculationDriftError,
    VerificationReportNotFoundError,
    WorkUnitAlreadyDiscardedError,
    WorkUnitMutationRefusedError,
    WorkUnitNotFoundError,
)
from ._amendment_actions import (
    amend_modelo_revision as amend_modelo_revision,
)
from ._calculation_actions import (
    _IVA_LEDGER_EXEMPT_REGIMES as _IVA_LEDGER_EXEMPT_REGIMES,
)
from ._calculation_actions import (
    _iva_wallet_blocked_message as _iva_wallet_blocked_message,
)
from ._calculation_actions import (
    _raise_if_ledger_preflight_blocks_calculation as _raise_if_ledger_preflight_blocks_calculation,
)
from ._calculation_actions import (
    _reject_caller_overrides_of_source_bindings as _reject_caller_overrides_of_source_bindings,
)
from ._calculation_actions import (
    calculate_modelo_revision as calculate_modelo_revision,
)
from ._calculation_actions import (
    calculate_modelo_revision_from_bucket_aggregation as calculate_modelo_revision_from_bucket_aggregation,
)
from ._calculation_actions import (
    get_calculation_revision as get_calculation_revision,
)
from ._calculation_actions import (
    list_calculation_revisions as list_calculation_revisions,
)
from ._calculation_actions import (
    mark_revision_verificado_completo as mark_revision_verificado_completo,
)
from ._calculation_helpers import (
    amendment_observations as _amendment_observations,
)
from ._calculation_helpers import (
    build_typed_observations as _build_typed_observations,
)
from ._calculation_helpers import (
    resolve_registry_snapshot_for_work_unit as _resolve_registry_snapshot_for_work_unit,
)
from ._external_import_actions import (
    import_external_filing_evidence as import_external_filing_evidence,
)
from ._filing_actions import (
    file_modelo_revision as file_modelo_revision,
)
from ._filing_actions import (
    get_filing_record as get_filing_record,
)
from ._filing_actions import (
    get_verification_report as get_verification_report,
)
from ._filing_actions import (
    list_filing_records as list_filing_records,
)
from ._filing_actions import (
    list_verification_reports as list_verification_reports,
)
from ._registry_helpers import (
    assert_revision_content_integrity as _assert_revision_content_integrity,
)
from ._verification_actions import (
    _PREDICATE_ADVISORY_WHEN_RATIO_GE as _PREDICATE_ADVISORY_WHEN_RATIO_GE,
)
from ._verification_actions import (
    _PREDICATE_ALL_NONZERO as _PREDICATE_ALL_NONZERO,
)
from ._verification_actions import (
    _PREDICATE_ANY_NONZERO as _PREDICATE_ANY_NONZERO,
)
from ._verification_actions import (
    _PREDICATE_CAP_LE_WHEN_POSITIVE as _PREDICATE_CAP_LE_WHEN_POSITIVE,
)
from ._verification_actions import (
    _PREDICATE_IMPLIES_ANY_NONZERO as _PREDICATE_IMPLIES_ANY_NONZERO,
)
from ._verification_actions import (
    _PREDICATE_IMPLIES_NONZERO as _PREDICATE_IMPLIES_NONZERO,
)
from ._verification_actions import (
    _PREDICATE_PROFILE_FIELD_REQUIRED as _PREDICATE_PROFILE_FIELD_REQUIRED,
)
from ._verification_actions import (
    _assert_evidence_covers_snapshot as _assert_evidence_covers_snapshot,
)
from ._verification_actions import (
    _collect_revision_verification_findings as _collect_revision_verification_findings,
)
from ._verification_actions import (
    _cross_period_clean_state_next_action as _cross_period_clean_state_next_action,
)
from ._verification_actions import (
    _dt12_reduccion_advisory_finding as _dt12_reduccion_advisory_finding,
)
from ._verification_actions import (
    _evaluate_advisory_predicate_fires as _evaluate_advisory_predicate_fires,
)
from ._verification_actions import (
    _evaluate_applicability_filter as _evaluate_applicability_filter,
)
from ._verification_actions import (
    _evaluate_predicate_expression as _evaluate_predicate_expression,
)
from ._verification_actions import (
    _evaluate_verification_predicates as _evaluate_verification_predicates,
)
from ._verification_actions import (
    _iva_wallet_blocking_verification_finding as _iva_wallet_blocking_verification_finding,
)
from ._verification_actions import (
    _missing_required_casilla_finding as _missing_required_casilla_finding,
)
from ._verification_actions import (
    _require_cross_period_clean_state as _require_cross_period_clean_state,
)
from ._verification_actions import (
    _rewrite_m210_sentinels as _rewrite_m210_sentinels,
)
from ._verification_actions import (
    verify_modelo_revision as verify_modelo_revision,
)
from ._work_lifecycle import (
    create_work_unit as create_work_unit,
)
from ._work_lifecycle import (
    discard_work_unit as discard_work_unit,
)
from ._work_lifecycle import (
    get_work_unit as get_work_unit,
)
from ._work_lifecycle import (
    list_work_units as list_work_units,
)
from ._work_lifecycle import (
    rename_work_unit as rename_work_unit,
)
from ._workflow_gate import (
    _RevisionInputsProvider as _RevisionInputsProvider,
)
from ._workflow_gate import (
    workflow_period_for_work_unit,
)

if TYPE_CHECKING:
    pass

ModeloIvaWalletReconciliationBlocked = _iva_wallet_gate.ModeloIvaWalletReconciliationBlocked
ModeloIvaWalletReconciliationBlockedError = _iva_wallet_gate.ModeloIvaWalletReconciliationBlockedError
_apply_iva_compensation_decision_binding = _iva_wallet_gate.apply_iva_compensation_decision_binding
_require_iva_compensation_revision_match = _iva_wallet_gate.require_persisted_iva_compensation_decision_matches_revision
_require_persisted_iva_compensation_decision_matches_revision = _require_iva_compensation_revision_match
_taxpayer_nif_for_bucket = _iva_wallet_gate.taxpayer_nif_for_bucket
iva_wallet_blocked_message = _iva_wallet_gate.iva_wallet_blocked_message
resolve_iva_compensation_decision_for_calculation = _iva_wallet_gate.resolve_iva_compensation_decision_for_calculation
_resolve_m210_rate = _m210_rate.resolve_m210_rate


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
    "ModeloAggregationBindingError",
    "ModeloApplicabilityFilterError",
    "ModeloCrossPeriodCleanStateError",
    "ModeloError",
    "ModeloIvaWalletReconciliationBlocked",
    "ModeloIvaWalletReconciliationBlockedError",
    "ModeloRecordNotFoundError",
    "ModeloWorkflowGateError",
    "StoredCalculationDriftError",
    "VerificationReportNotFoundError",
    "WorkUnitAlreadyDiscardedError",
    "WorkUnitMutationRefusedError",
    "WorkUnitNotFoundError",
    "_amendment_observations",
    "_assert_evidence_covers_snapshot",
    "_assert_revision_content_integrity",
    "_build_typed_observations",
    "_resolve_registry_snapshot_for_work_unit",
    "amend_modelo_revision",
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
    "verify_modelo_revision",
    "workflow_period_for_work_unit",
]
