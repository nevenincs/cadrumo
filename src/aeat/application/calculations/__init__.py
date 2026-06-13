"""Application-layer calculation utilities: observation repository and multi-year resolver for prior-year inputs.

The runtime calc engine (`aeat.domain.calculations.registry._formula_runtime`)
takes pre-resolved `relation_values` and `binding_values` mappings.
This package provides the application-side helpers that produce
those mappings from the operator's local filing history, so annual
modelos (e.g. modelo 200, IS) and multi-year regimes (e.g. IVA
prorrata four-year average, IVA regularización inversiones five-year
straight-line, IS BIN unlimited carryforward) can resolve their
inputs from authoritative prior filings instead of operator
hand-entry.
"""

from ._binding_prefill import (
    BindingPrefillReport,
    LocalIvaCompensationRecurrence,
    PrefilledBinding,
    extract_modelo_303_local_iva_compensation_recurrence,
    resolve_bindings_from_local_store,
)
from ._cross_period_clean_state import (
    CrossPeriodCleanStateBlocker,
    CrossPeriodCleanStateVerdict,
    CrossPeriodDependencyEvidence,
    CrossPeriodDependencyInventory,
    CrossPeriodDependencyInventoryItem,
    CrossPeriodDependencyOrigin,
    CrossPeriodDependencyRequirement,
    CrossPeriodExpectedMemberSet,
    NoPriorObligationProvenance,
    NoPriorObligationProvenanceKind,
    cross_period_dependency_inventory,
    cross_period_dependency_requirements,
    evaluate_cross_period_clean_state,
    partition_cross_period_requirements_by_activity_start,
)
from ._iva_compensation_history import (
    IvaCompensationAnnualCrossCheck,
    IvaCompensationAnnualSummary,
    IvaCompensationHistoryRepository,
    correct_iva_compensation_period,
    cross_check_iva_compensation_annual_summary,
    iva_compensation_annual_summary_from_filed_observation,
    iva_compensation_period_key,
    iva_compensation_state_from_filed_observation,
    seed_iva_compensation_period,
)
from ._iva_wallet_balance import query_iva_wallet_balance
from ._iva_wallet_reconciliation import (
    IvaCompensationReconciliationReport,
    IvaWalletDecisionSourceResolver,
    reconcile_iva_compensation_wallet,
    reconcile_modelo_303_iva_compensation,
)
from ._maritime_exemption_service import resolve_maritime_exemption
from ._multi_year import (
    EnrollmentEvidence,
    EnrollmentEvidenceError,
    EnrollmentRecorder,
    EnrollmentYearObservation,
    MultiYearResolutionReport,
    MultiYearResolutionRequest,
    MultiYearResolver,
    PreviousFilingSourceResolver,
    assert_enrollment_matches_manifest,
    resolve_prior_year_observations,
)
from ._observations_repository import (
    CalculationObservationRepository,
    IvaWalletDecisionRepository,
    iva_wallet_decision_event_key,
    iva_wallet_decision_key,
    observation_key,
)
from ._relation_prefill import RelationPrefillSourceResolver, resolve_relations_from_local_store
from ._row_set_assembly import (
    AssembledObservations,
    assemble_atribucion_observations,
    assemble_foreign_asset_observations,
    assemble_observations_for_grouping,
    assemble_refund_observations,
    assemble_related_party_observations,
    assemble_withholding_observations,
)

# Resolve forward reference: BindingPrefillReport is TYPE_CHECKING-only inside
# _iva_wallet_reconciliation due to a circular import; rebuild after both modules load.
IvaCompensationReconciliationReport.model_rebuild()

__all__ = [
    "AssembledObservations",
    "BindingPrefillReport",
    "CalculationObservationRepository",
    "CrossPeriodCleanStateBlocker",
    "CrossPeriodCleanStateVerdict",
    "CrossPeriodDependencyEvidence",
    "CrossPeriodDependencyInventory",
    "CrossPeriodDependencyInventoryItem",
    "CrossPeriodDependencyOrigin",
    "CrossPeriodDependencyRequirement",
    "CrossPeriodExpectedMemberSet",
    "EnrollmentEvidence",
    "EnrollmentEvidenceError",
    "EnrollmentRecorder",
    "EnrollmentYearObservation",
    "IvaCompensationAnnualCrossCheck",
    "IvaCompensationAnnualSummary",
    "IvaCompensationHistoryRepository",
    "IvaCompensationReconciliationReport",
    "IvaWalletDecisionRepository",
    "IvaWalletDecisionSourceResolver",
    "LocalIvaCompensationRecurrence",
    "MultiYearResolutionReport",
    "MultiYearResolutionRequest",
    "MultiYearResolver",
    "NoPriorObligationProvenance",
    "NoPriorObligationProvenanceKind",
    "PrefilledBinding",
    "PreviousFilingSourceResolver",
    "RelationPrefillSourceResolver",
    "assemble_atribucion_observations",
    "assemble_foreign_asset_observations",
    "assemble_observations_for_grouping",
    "assemble_refund_observations",
    "assemble_related_party_observations",
    "assemble_withholding_observations",
    "assert_enrollment_matches_manifest",
    "correct_iva_compensation_period",
    "cross_check_iva_compensation_annual_summary",
    "cross_period_dependency_inventory",
    "cross_period_dependency_requirements",
    "evaluate_cross_period_clean_state",
    "extract_modelo_303_local_iva_compensation_recurrence",
    "iva_compensation_annual_summary_from_filed_observation",
    "iva_compensation_period_key",
    "iva_compensation_state_from_filed_observation",
    "iva_wallet_decision_event_key",
    "iva_wallet_decision_key",
    "observation_key",
    "partition_cross_period_requirements_by_activity_start",
    "query_iva_wallet_balance",
    "reconcile_iva_compensation_wallet",
    "reconcile_modelo_303_iva_compensation",
    "resolve_bindings_from_local_store",
    "resolve_maritime_exemption",
    "resolve_prior_year_observations",
    "resolve_relations_from_local_store",
    "seed_iva_compensation_period",
]
