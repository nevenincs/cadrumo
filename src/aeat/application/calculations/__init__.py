"""Application-layer calculation utilities — observation repository and
the multi-year resolver that lets relation / binding pre-resolution
consult prior years' filings.

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
from ._iva_compensation_history import (
    IvaCompensationCarryForwardLot,
    IvaCompensationCarryForwardPolicyError,
    IvaCompensationCarryForwardReport,
    IvaCompensationExpiryReviewState,
    IvaCompensationHistoryRepository,
    IvaCompensationPeriodState,
    build_iva_compensation_carry_forward_report,
    enforce_iva_compensation_four_year_window,
    iva_compensation_period_key,
    iva_compensation_state_from_filed_observation,
)
from ._iva_wallet_reconciliation import (
    IvaCompensationAuthoritySource,
    IvaCompensationOverride,
    IvaCompensationReconciliationDecision,
    IvaCompensationReconciliationInputError,
    IvaCompensationReconciliationReport,
    reconcile_iva_compensation_wallet,
    reconcile_modelo_303_iva_compensation,
)
from ._multi_year import MultiYearResolver, PreviousFilingSourceResolver, resolve_prior_year_observations
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

__all__ = [
    "AssembledObservations",
    "BindingPrefillReport",
    "CalculationObservationRepository",
    "IvaCompensationAuthoritySource",
    "IvaCompensationCarryForwardLot",
    "IvaCompensationCarryForwardPolicyError",
    "IvaCompensationCarryForwardReport",
    "IvaCompensationExpiryReviewState",
    "IvaCompensationHistoryRepository",
    "IvaCompensationOverride",
    "IvaCompensationPeriodState",
    "IvaCompensationReconciliationDecision",
    "IvaCompensationReconciliationInputError",
    "IvaCompensationReconciliationReport",
    "IvaWalletDecisionRepository",
    "LocalIvaCompensationRecurrence",
    "MultiYearResolver",
    "PrefilledBinding",
    "PreviousFilingSourceResolver",
    "RelationPrefillSourceResolver",
    "assemble_atribucion_observations",
    "assemble_foreign_asset_observations",
    "assemble_observations_for_grouping",
    "assemble_refund_observations",
    "assemble_related_party_observations",
    "assemble_withholding_observations",
    "build_iva_compensation_carry_forward_report",
    "enforce_iva_compensation_four_year_window",
    "extract_modelo_303_local_iva_compensation_recurrence",
    "iva_compensation_period_key",
    "iva_compensation_state_from_filed_observation",
    "iva_wallet_decision_event_key",
    "iva_wallet_decision_key",
    "observation_key",
    "reconcile_iva_compensation_wallet",
    "reconcile_modelo_303_iva_compensation",
    "resolve_bindings_from_local_store",
    "resolve_prior_year_observations",
    "resolve_relations_from_local_store",
]
