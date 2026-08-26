"""Public aggregation facade for rollup helpers and typed source-mesh resolvers.

This package exposes two related surfaces. The pure aggregation helpers
(``aggregate_*`` functions plus value records such as
:class:`CasillaAggregation` and
:class:`RetencionesAggregation`) roll classified
observations into family-specific totals. The live calculation surface is the
source mesh: :class:`ModeloSourceResolver`
implementations claim one or more
:class:`core.BindingSourceKind` members and return the canonical
:class:`CalculationSourceResolution` envelope
consumed by the modelo calculate path.

:func:`aggregate_per_modelo` remains the provider-grouped service for
per-modelo rollup workflows. It is not the resolved-source envelope used by
calculation; mesh helpers such as :func:`merge_source_resolutions`,
:func:`merge_source_resolutions_by_precedence`,
:func:`collect_unhandled_source_diagnostics`, and
:func:`build_binding_source_dispositions` enforce exclusive ownership, declared
precedence, no-silent-blank diagnostics, and the enrolled / deferred / reserved
:class:`BindingSourceDisposition` registry.

Concrete resolvers re-exported here include
:class:`LedgerIvaAggregationSourceResolver`,
:class:`RetencionesAggregationSourceResolver`,
:class:`OssIossLedgerSourceResolver`,
:class:`ProfileSourceResolver`, and
:class:`WithholdingSourceResolver`. The calculation
path also composes prior-filing, relation-prefill, invoice, borrador, and
IVA-wallet resolvers from neighboring application packages; their shared
contract is still
:class:`CalculationSourceResolution`, not
:class:`CasillaAggregation`.

Aggregation resolvers prepare provenance-carrying source values; they do not
execute registry formulas, decide filing readiness, or mutate work-unit filing
state. Those steps remain in :mod:`domain.calculations.registry` and
:mod:`application.modelo`.

The facade also re-exports encrypted observation repositories for the
retenciones and percepciones stores, informativa rollups, and the shared
:class:`AggregationError` failure taxonomy.

See Also:
    :mod:`application.modelo`
        Work-unit calculate services that consume
        :class:`CalculationSourceResolution`
        values and persist contributing ``source_transaction_ids`` on
        calculation revisions.
    :mod:`domain.transactions`
        Ledger transaction catalogue resolved by ledger IVA, Renta, OSS/IOSS,
        evidence-advisory, and filing-snapshot aggregation paths.
    :mod:`domain.invoices`
        Invoice catalogue and purchase-evidence records adapted into invoice
        source resolutions.
    :mod:`domain.attachments`
        Encrypted document bytes referenced by ledger evidence diagnostics and
        advisory surfaces without becoming plaintext calculation inputs.
    :mod:`domain.calculations.registry`
        Pure registry formulas, binding declarations, and observation contracts
        that consume the resolved source payload.
"""

from __future__ import annotations

from ...core.aggregation import (
    CounterpartSourceKind,
    ForeignAssetClass,
    OperationKind347,
    OperationKind349,
    RetencionScheme,
)
from ...domain.calculations import DirectRowMaterializationProvenance, RowCasillaKey
from ...domain.calculations.registry.bindings import WithholdingObservation
from ...domain.modelos import LedgerFilingSnapshot
from ._atribucion_member import AtribucionMemberSourceResolver
from ._business_proportion import business_proportion
from ._counterpart import (
    CounterpartAggregation,
    CounterpartObservation,
    aggregate_counterpart_347,
    aggregate_counterpart_349,
    declarable_counterparty_nifs_347,
    declarable_for_347,
)
from ._evidence_advisory import (
    MISSING_DEDUCTIBLE_IVA_EVIDENCE_SOURCE_KIND,
    missing_evidence_advisory_observations,
)
from ._foreign_assets import (
    ForeignAssetClassRollup,
    ForeignAssetIngestObservation,
    ForeignAssetsAggregation,
    ForeignAssetsAggregationSourceResolver,
    aggregate_foreign_assets_720,
    declarable_asset_classes_720,
    declarable_class,
)
from ._inventory import InventorySourceResolver
from ._invoice_devengo import (
    InvoiceDevengo,
    invoice_devengo_in_period,
    proxy_attributed_invoice_ids,
    resolve_invoice_devengo,
)
from ._invoice_kind import invoice_kind_for_direction
from ._invoice_retencion import (
    INVOICE_RETENCION_DEFECT_GUIDANCE,
    InvoiceRetencionProjection,
    InvoiceRetencionProjectionDefect,
    InvoiceRetencionRouteRequest,
    InvoiceRetencionRouting,
    merge_manual_and_routed_retencion_observations,
    project_received_invoice_retencion,
    route_invoice_retenciones,
)
from ._iva_ledger import (
    IVA_LEDGER_COUNTERPARTY_GATE_REASONS,
    IVA_LEDGER_MISSING_FACT_REASONS,
    AnnualDeducibleTotalsByRegime,
    IvaDifferentiatedDeductionContribution,
    IvaLedgerAggregation,
    IvaLedgerAggregationIssue,
    IvaLedgerAggregationIssueReason,
    IvaLedgerCandidate,
    ProrrataLedgerReference,
    aggregate_iva_ledger_candidate_bindings,
    aggregate_iva_ledger_candidates,
    aggregate_iva_ledger_observations,
    aggregate_iva_ledger_observations_from_repositories,
    compute_annual_deducible_totals_by_regime,
    iva_ledger_missing_fact_reasons,
    resolve_iva_differentiated_deduction_contributions,
    validate_iva_ledger_counterparty_category,
    validate_iva_ledger_observation,
    validate_iva_ledger_observations,
)
from ._ledger_filing_snapshot import (
    assert_evidence_covers_snapshot,
    compute_ledger_filing_evidence,
    compute_ledger_filing_snapshot,
    evaluate_ledger_filing_staleness,
    row_fingerprint,
    stale_filed_revisions,
)
from ._m303_arrivals import (
    M303ProrrataTransitionArrival,
    M303SupplierRegimeArrival,
    resolve_m303_prorrata_transition_arrival,
    resolve_m303_supplier_regime_arrival,
)
from ._modelo_bindings import (
    LedgerImpatriadoIncomeAggregationSourceResolver,
    LedgerIrnrIncomeAggregationSourceResolver,
    LedgerIvaAggregationSourceResolver,
    LedgerRentaGastosEstimacionDirectaAggregationSourceResolver,
    LedgerRentaGastosPagoFraccionadoAggregationSourceResolver,
    LedgerRentaIncomeAggregationSourceResolver,
    RetencionesAggregationSourceResolver,
    aggregation_period_for_modelo,
)
from ._models import CasillaAggregation, CasillaProvenance
from ._oss_ioss import (
    OssIossInvoiceProjection,
    OssIossLedgerCandidate,
    OssIossLedgerSourceResolver,
    aggregate_oss_ioss_bindings,
    aggregate_oss_ioss_from_repositories,
    oss_ioss_candidates_from_repositories,
    project_oss_ioss_invoices_from_repositories,
    validate_oss_ioss_observation,
    validate_oss_ioss_observations,
)
from ._percepciones_observations_repository import (
    PercepcionObservationRepository,
    percepcion_observation_key,
    persist_percepcion_observations,
)
from ._renta_income_ledger import (
    RentaIncomeObservation,
    UnadmittedActivityIncome,
    aggregate_renta_income_ledger,
    aggregate_renta_m100_income_ledger,
    aggregate_renta_m131_agrario_income_ledger,
)
from ._renta_ledger import (
    RentaLedgerAggregationIssue,
    RentaLedgerAggregationIssueReason,
    RentaLedgerExpenseAggregation,
    aggregate_renta_ledger_expenses,
    aggregate_renta_ledger_expenses_from_repositories,
)
from ._retencion_observations_repository import (
    RetencionObservationRepository,
    persist_retencion_observations,
    retencion_observation_key,
)
from ._retencion_rate_advisory import (
    ADMINISTRADOR_RETENCION_RATE_SOURCE_KIND,
    INFERRED_ACTIVIDAD_RETENCION_RATE_SOURCE_KIND,
    INFERRED_SECTORAL_RETENCION_RATE_SOURCE_KIND,
    administrador_retencion_rate_advisory_observations,
    inferred_actividad_retencion_rate_advisory_observations,
)
from ._retenciones import (
    RetencionesAggregation,
    RetencionesTotalsParity,
    RetencionObservation,
    RetencionPerceptorRollup,
    aggregate_retenciones_111,
    aggregate_retenciones_115,
    aggregate_retenciones_123,
    aggregate_retenciones_180,
    aggregate_retenciones_190,
    aggregate_retenciones_193,
    compute_retenciones_totals_parity,
)
from ._service import (
    ACCEPTED_SOURCE_KINDS,
    AggregationErrorCodes,
    PerModeloAggregationCommand,
    PerModeloAggregationContributor,
    PerModeloAggregationLogFields,
    PerModeloAggregationResult,
    aggregate_per_modelo,
    get_per_modelo_aggregation_contract,
)
from ._source_mesh import (
    DEFERRED_SOURCE_KINDS,
    DIAGNOSTIC_MESSAGE_MAX_LENGTH,
    RESERVED_SOURCE_KINDS,
    BindingSourceDisposition,
    BorradorSourceProvenance,
    CalculationSourceContext,
    CalculationSourceDiagnostic,
    CalculationSourceDiagnosticReason,
    CalculationSourceProvenance,
    CalculationSourceResolution,
    CallerOverrideDisposition,
    CompositeSourceResolverId,
    ModeloSourceResolver,
    SourceMeshError,
    build_binding_source_dispositions,
    casilla_registry_legal_refs,
    collect_unhandled_source_diagnostics,
    merge_source_resolutions,
    merge_source_resolutions_by_precedence,
    precedence_ladder_sources,
    storage_degradation_resolution,
)
from ._source_profile import ProfileSourceResolver
from ._undeclared_activity_advisory import (
    UNDECLARED_ACTIVITY_INCOME_SOURCE_KIND,
    undeclared_activity_income_advisory_observations,
)
from ._withholding_source import WithholdingSourceResolver
from .errors import (
    AggregationCategoryCoverageError,
    AggregationConfigError,
    AggregationError,
    AggregationMissingClassificationError,
    AggregationPeriodError,
    AggregationUnsupportedModeloError,
    AggregationValidationError,
)

__all__ = [
    "ACCEPTED_SOURCE_KINDS",
    "ADMINISTRADOR_RETENCION_RATE_SOURCE_KIND",
    "DEFERRED_SOURCE_KINDS",
    "DIAGNOSTIC_MESSAGE_MAX_LENGTH",
    "INFERRED_ACTIVIDAD_RETENCION_RATE_SOURCE_KIND",
    "INFERRED_SECTORAL_RETENCION_RATE_SOURCE_KIND",
    "INVOICE_RETENCION_DEFECT_GUIDANCE",
    "IVA_LEDGER_COUNTERPARTY_GATE_REASONS",
    "IVA_LEDGER_MISSING_FACT_REASONS",
    "MISSING_DEDUCTIBLE_IVA_EVIDENCE_SOURCE_KIND",
    "RESERVED_SOURCE_KINDS",
    "UNDECLARED_ACTIVITY_INCOME_SOURCE_KIND",
    "AggregationCategoryCoverageError",
    "AggregationConfigError",
    "AggregationError",
    "AggregationErrorCodes",
    "AggregationMissingClassificationError",
    "AggregationPeriodError",
    "AggregationUnsupportedModeloError",
    "AggregationValidationError",
    "AnnualDeducibleTotalsByRegime",
    "AtribucionMemberSourceResolver",
    "BindingSourceDisposition",
    "BorradorSourceProvenance",
    "CalculationSourceContext",
    "CalculationSourceDiagnostic",
    "CalculationSourceDiagnosticReason",
    "CalculationSourceProvenance",
    "CalculationSourceResolution",
    "CallerOverrideDisposition",
    "CasillaAggregation",
    "CasillaProvenance",
    "CompositeSourceResolverId",
    "CounterpartAggregation",
    "CounterpartObservation",
    "CounterpartSourceKind",
    "DirectRowMaterializationProvenance",
    "ForeignAssetClass",
    "ForeignAssetClassRollup",
    "ForeignAssetIngestObservation",
    "ForeignAssetsAggregation",
    "ForeignAssetsAggregationSourceResolver",
    "InventorySourceResolver",
    "InvoiceDevengo",
    "InvoiceRetencionProjection",
    "InvoiceRetencionProjectionDefect",
    "InvoiceRetencionRouteRequest",
    "InvoiceRetencionRouting",
    "IvaDifferentiatedDeductionContribution",
    "IvaLedgerAggregation",
    "IvaLedgerAggregationIssue",
    "IvaLedgerAggregationIssueReason",
    "IvaLedgerCandidate",
    "LedgerFilingSnapshot",
    "LedgerImpatriadoIncomeAggregationSourceResolver",
    "LedgerIrnrIncomeAggregationSourceResolver",
    "LedgerIvaAggregationSourceResolver",
    "LedgerRentaGastosEstimacionDirectaAggregationSourceResolver",
    "LedgerRentaGastosPagoFraccionadoAggregationSourceResolver",
    "LedgerRentaIncomeAggregationSourceResolver",
    "M303ProrrataTransitionArrival",
    "M303SupplierRegimeArrival",
    "ModeloSourceResolver",
    "OperationKind347",
    "OperationKind349",
    "OssIossInvoiceProjection",
    "OssIossLedgerCandidate",
    "OssIossLedgerSourceResolver",
    "PerModeloAggregationCommand",
    "PerModeloAggregationContributor",
    "PerModeloAggregationLogFields",
    "PerModeloAggregationResult",
    "PercepcionObservationRepository",
    "ProfileSourceResolver",
    "ProrrataLedgerReference",
    "RentaIncomeObservation",
    "RentaLedgerAggregationIssue",
    "RentaLedgerAggregationIssueReason",
    "RentaLedgerExpenseAggregation",
    "RetencionObservation",
    "RetencionObservationRepository",
    "RetencionPerceptorRollup",
    "RetencionScheme",
    "RetencionesAggregation",
    "RetencionesAggregationSourceResolver",
    "RetencionesTotalsParity",
    "RowCasillaKey",
    "SourceMeshError",
    "UnadmittedActivityIncome",
    "WithholdingObservation",
    "WithholdingSourceResolver",
    "administrador_retencion_rate_advisory_observations",
    "aggregate_counterpart_347",
    "aggregate_counterpart_349",
    "aggregate_foreign_assets_720",
    "aggregate_iva_ledger_candidate_bindings",
    "aggregate_iva_ledger_candidates",
    "aggregate_iva_ledger_observations",
    "aggregate_iva_ledger_observations_from_repositories",
    "aggregate_oss_ioss_bindings",
    "aggregate_oss_ioss_from_repositories",
    "aggregate_per_modelo",
    "aggregate_renta_income_ledger",
    "aggregate_renta_ledger_expenses",
    "aggregate_renta_ledger_expenses_from_repositories",
    "aggregate_renta_m100_income_ledger",
    "aggregate_renta_m131_agrario_income_ledger",
    "aggregate_retenciones_111",
    "aggregate_retenciones_115",
    "aggregate_retenciones_123",
    "aggregate_retenciones_180",
    "aggregate_retenciones_190",
    "aggregate_retenciones_193",
    "aggregation_period_for_modelo",
    "assert_evidence_covers_snapshot",
    "build_binding_source_dispositions",
    "business_proportion",
    "casilla_registry_legal_refs",
    "collect_unhandled_source_diagnostics",
    "compute_annual_deducible_totals_by_regime",
    "compute_ledger_filing_evidence",
    "compute_ledger_filing_snapshot",
    "compute_retenciones_totals_parity",
    "declarable_asset_classes_720",
    "declarable_class",
    "declarable_counterparty_nifs_347",
    "declarable_for_347",
    "evaluate_ledger_filing_staleness",
    "get_per_modelo_aggregation_contract",
    "inferred_actividad_retencion_rate_advisory_observations",
    "invoice_devengo_in_period",
    "invoice_kind_for_direction",
    "iva_ledger_missing_fact_reasons",
    "merge_manual_and_routed_retencion_observations",
    "merge_source_resolutions",
    "merge_source_resolutions_by_precedence",
    "missing_evidence_advisory_observations",
    "oss_ioss_candidates_from_repositories",
    "percepcion_observation_key",
    "persist_percepcion_observations",
    "persist_retencion_observations",
    "precedence_ladder_sources",
    "project_oss_ioss_invoices_from_repositories",
    "project_received_invoice_retencion",
    "proxy_attributed_invoice_ids",
    "resolve_invoice_devengo",
    "resolve_iva_differentiated_deduction_contributions",
    "resolve_m303_prorrata_transition_arrival",
    "resolve_m303_supplier_regime_arrival",
    "retencion_observation_key",
    "route_invoice_retenciones",
    "row_fingerprint",
    "stale_filed_revisions",
    "storage_degradation_resolution",
    "undeclared_activity_income_advisory_observations",
    "validate_iva_ledger_counterparty_category",
    "validate_iva_ledger_observation",
    "validate_iva_ledger_observations",
    "validate_oss_ioss_observation",
    "validate_oss_ioss_observations",
]
