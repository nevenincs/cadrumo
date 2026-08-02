"""Application-layer calculation source stores, proof records, and prefill helpers.

The registry runtime consumes already-resolved ``binding_values`` and
``relation_values`` for
:func:`domain.calculations.registry.calculate_registry_snapshot`. This
package is the public application facade for the stores, source resolvers, and
typed proof records that produce those inputs from local filing history, IVA
wallet reconciliation, relation prefill, row-set detail captures, and
cross-period clean-state evidence.

This facade is not the formula runtime. It owns persisted observations,
source-proof assembly, carry-forward policy, and source resolvers that feed the
registry engine; the registry remains the authority for casilla definitions,
binding declarations, relation closure, and formula execution.

Direct prior-filing bindings and registry relations are deliberately separate
source owners. :class:`PreviousFilingSourceResolver` resolves
:attr:`core.BindingSourceKind.PREVIOUS_FILING` binding carries;
:class:`RelationPrefillSourceResolver` resolves
:attr:`core.BindingSourceKind.RELATION_PREFILL` relation fold-ins and
their materialised target bindings; :class:`IvaWalletDecisionSourceResolver`
resolves the Modelo 303
:attr:`core.BindingSourceKind.IVA_WALLET_DECISION` compensation authority
outside the ordinary previous-filing carry; and
:class:`IvaCompensationAnnualPartitionSourceResolver` resolves Modelo 390
:attr:`core.BindingSourceKind.IVA_COMPENSATION_ANNUAL_PARTITION` boxes 97
and 662 from the same FIFO carry projection.

The main public surfaces are:

* :class:`CalculationObservationRepository` and
  :class:`IvaWalletDecisionRepository`, encrypted stores for prior
  :class:`domain.calculations.registry.RegistryModeloObservation` records,
  plus :class:`IvaCompensationHistoryRepository` for secure Modelo 303
  compensation history.
* :class:`PreviousFilingSourceResolver`,
  :class:`RelationPrefillSourceResolver`, and
  :class:`IvaWalletDecisionSourceResolver`, source-mesh adapters that produce
  :class:`application.aggregation.CalculationSourceResolution` envelopes.
* :func:`resolve_bindings_from_local_store` and
  :func:`resolve_relations_from_local_store`, prefill readers over the same
  local observation substrate; :class:`BindingPrefillReport` and
  :class:`PrefilledBinding` carry the direct previous-filing coverage.
* :func:`cross_period_dependency_requirements` and
  :func:`evaluate_cross_period_clean_state`, the filing-grade dependency proof
  whose
  :class:`CrossPeriodCleanStateVerdict` joins
  :class:`CrossPeriodDependencyRequirement` rows to filing records, revisions,
  verification reports, and justificante evidence.
* Row-set assemblers such as :func:`assemble_withholding_observations`, which
  turn pull-side Detalle cells into ``AssembledObservations`` payloads for
  persistence.

See Also:
    :mod:`application.aggregation`
        Defines the source-mesh contracts consumed by the calculation path.
    :mod:`domain.calculations.registry`
        Owns the pure registry snapshots, binding definitions, relation
        requirements, and formula runtime.
    :mod:`application.modelo`
        Orchestrates these package-level services inside work calculation,
        verification, filing, and export workflows.
"""

from ._bienes_inversion_regularizacion import (
    CASILLA_REGULARIZACION_BIENES_INVERSION,
    BienesInversionRegularizacionSourceResolver,
    build_bienes_inversion_regularizacion_advisory,
    build_bienes_inversion_transmision_advisory,
)
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
    filing_external_evidence_blockers,
    partition_cross_period_requirements_by_activity_start,
)
from ._iva_compensation_annual_partition import (
    IvaCompensationAnnualPartitionSourceResolver,
    resolve_iva_compensation_annual_partition_binding_values,
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
    iva_compensation_state_from_registry_observation,
    seed_iva_compensation_period,
)
from ._iva_wallet_balance import query_iva_wallet_balance
from ._iva_wallet_reconciliation import (
    IvaCompensationReconciliationReport,
    IvaWalletDecisionSourceResolver,
    reconcile_iva_compensation_wallet,
    reconcile_modelo_303_iva_compensation,
)
from ._m111_no_retenciones import (
    M111_NO_RETENCIONES_PROFILE_PATH,
    m111_no_retenciones_periods_for_bucket,
)
from ._maritime_exemption_service import MaritimeExemptionResult, resolve_maritime_exemption
from ._multi_year import (
    EnrollmentEvidence,
    EnrollmentEvidenceError,
    EnrollmentRecorder,
    EnrollmentYearObservation,
    PreviousFilingSourceResolver,
    assert_enrollment_matches_manifest,
)
from ._observations_repository import (
    CalculationObservationRepository,
    IvaWalletDecisionEnvelopePayload,
    IvaWalletDecisionRepository,
    ObservationEnvelopePayload,
    ObservationSourceKind,
    is_official_aeat_observation_source,
    iva_wallet_decision_event_key,
    iva_wallet_decision_key,
    member_observation_key,
    observation_key,
    observation_key_for_token,
)
from ._prorrata_regularizacion import (
    CASILLA_REGULARIZACION_PRORRATA_DEFINITIVA,
    ProrrataApplicabilityProjection,
    ProrrataDeclaredVolumeLedgerRollup,
    ProrrataRegularizacionFeedProjection,
    ProrrataRegularizacionSourceResolver,
    build_prorrata_declared_volume_divergence_advisory,
    build_prorrata_especial_mandatory_advisory,
    build_prorrata_missing_provisional_advisory,
    build_prorrata_regularizacion_advisory,
    derive_prorrata_applicability,
    project_prorrata_regularizacion_feed,
)
from ._relation_prefill import (
    RelationPrefillSourceResolver,
    relation_prefill_period_zero_default_binding_ids,
    resolve_relations_from_local_store,
)
from ._revision_carry_gate import RevisionCarryOutcome, revision_carry_outcome
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
    "CASILLA_REGULARIZACION_BIENES_INVERSION",
    "CASILLA_REGULARIZACION_PRORRATA_DEFINITIVA",
    "M111_NO_RETENCIONES_PROFILE_PATH",
    "AssembledObservations",
    "BienesInversionRegularizacionSourceResolver",
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
    "IvaCompensationAnnualPartitionSourceResolver",
    "IvaCompensationAnnualSummary",
    "IvaCompensationHistoryRepository",
    "IvaCompensationReconciliationReport",
    "IvaWalletDecisionEnvelopePayload",
    "IvaWalletDecisionRepository",
    "IvaWalletDecisionSourceResolver",
    "LocalIvaCompensationRecurrence",
    "MaritimeExemptionResult",
    "NoPriorObligationProvenance",
    "NoPriorObligationProvenanceKind",
    "ObservationEnvelopePayload",
    "ObservationSourceKind",
    "PrefilledBinding",
    "PreviousFilingSourceResolver",
    "ProrrataApplicabilityProjection",
    "ProrrataDeclaredVolumeLedgerRollup",
    "ProrrataRegularizacionFeedProjection",
    "ProrrataRegularizacionSourceResolver",
    "RelationPrefillSourceResolver",
    "RevisionCarryOutcome",
    "assemble_atribucion_observations",
    "assemble_foreign_asset_observations",
    "assemble_observations_for_grouping",
    "assemble_refund_observations",
    "assemble_related_party_observations",
    "assemble_withholding_observations",
    "assert_enrollment_matches_manifest",
    "build_bienes_inversion_regularizacion_advisory",
    "build_bienes_inversion_transmision_advisory",
    "build_prorrata_declared_volume_divergence_advisory",
    "build_prorrata_especial_mandatory_advisory",
    "build_prorrata_missing_provisional_advisory",
    "build_prorrata_regularizacion_advisory",
    "correct_iva_compensation_period",
    "cross_check_iva_compensation_annual_summary",
    "cross_period_dependency_inventory",
    "cross_period_dependency_requirements",
    "derive_prorrata_applicability",
    "evaluate_cross_period_clean_state",
    "extract_modelo_303_local_iva_compensation_recurrence",
    "filing_external_evidence_blockers",
    "is_official_aeat_observation_source",
    "iva_compensation_annual_summary_from_filed_observation",
    "iva_compensation_period_key",
    "iva_compensation_state_from_filed_observation",
    "iva_compensation_state_from_registry_observation",
    "iva_wallet_decision_event_key",
    "iva_wallet_decision_key",
    "m111_no_retenciones_periods_for_bucket",
    "member_observation_key",
    "observation_key",
    "observation_key_for_token",
    "partition_cross_period_requirements_by_activity_start",
    "project_prorrata_regularizacion_feed",
    "query_iva_wallet_balance",
    "reconcile_iva_compensation_wallet",
    "reconcile_modelo_303_iva_compensation",
    "relation_prefill_period_zero_default_binding_ids",
    "resolve_bindings_from_local_store",
    "resolve_iva_compensation_annual_partition_binding_values",
    "resolve_maritime_exemption",
    "resolve_relations_from_local_store",
    "revision_carry_outcome",
    "seed_iva_compensation_period",
]
