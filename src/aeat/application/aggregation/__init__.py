"""Public aggregation facade for rollup helpers and typed source-mesh resolvers.

This package exposes two related surfaces. The pure aggregation helpers
(``aggregate_*`` functions plus value records such as :class:`CasillaAggregation`
and :class:`RetencionesAggregation`) roll classified observations into
family-specific totals. The live calculation surface is the source mesh:
:class:`ModeloSourceResolver` implementations claim one or more
:class:`~aeat.core.BindingSourceKind` members and return the canonical
:class:`CalculationSourceResolution` envelope consumed by the modelo calculate
path.

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
:class:`OssIossLedgerSourceResolver`, :class:`ProfileSourceResolver`, and
:class:`WithholdingSourceResolver`. The calculation path also composes
prior-filing, relation-prefill, invoice, borrador, and IVA-wallet resolvers from
neighboring application packages; their shared contract is still
:class:`CalculationSourceResolution`, not :class:`CasillaAggregation`.

Aggregation resolvers prepare provenance-carrying source values; they do not
execute registry formulas, decide filing readiness, or mutate work-unit filing
state. Those steps remain in :mod:`aeat.domain.calculations.registry` and
:mod:`aeat.application.modelo`.

The facade also re-exports encrypted observation repositories for the
retenciones and withholding stores, informativa rollups, and the shared
:class:`AggregationError` failure taxonomy.
"""

from __future__ import annotations

from ...core import Period, PeriodKind
from ...core.aggregation import ForeignAssetClass, OperationKind347, OperationKind349, RetencionScheme
from ...domain.calculations.registry import WithholdingObservation
from ._counterpart import (
    CounterpartAggregation,
    CounterpartObservation,
    aggregate_counterpart_347,
    aggregate_counterpart_349,
    declarable_counterparty_nifs_347,
    declarable_for_347,
)
from ._errors import (
    AggregationCategoryCoverageError,
    AggregationConfigError,
    AggregationError,
    AggregationMissingClassificationError,
    AggregationPeriodError,
    AggregationUnsupportedModeloError,
    AggregationValidationError,
)
from ._evidence_advisory import (
    MISSING_TRANSACTION_EVIDENCE_SOURCE_KIND,
    missing_evidence_advisory_observations,
)
from ._foreign_assets import (
    ForeignAssetClassRollup,
    ForeignAssetIngestObservation,
    ForeignAssetsAggregation,
    aggregate_foreign_assets_720,
    declarable_asset_classes_720,
    declarable_class,
)
from ._iva_ledger import (
    IvaLedgerAggregation,
    IvaLedgerAggregationIssue,
    IvaLedgerAggregationIssueReason,
    IvaLedgerCandidate,
    IvaLedgerInputKind,
    ProrrataLedgerReference,
    aggregate_iva_ledger_candidate_bindings,
    aggregate_iva_ledger_candidates,
    aggregate_iva_ledger_observations,
    aggregate_iva_ledger_observations_from_repositories,
    iva_ledger_missing_fact_reasons,
    validate_iva_ledger_observation,
    validate_iva_ledger_observations,
)
from ._ledger_filing_snapshot import stale_filed_revisions
from ._modelo_bindings import (
    LedgerIvaAggregationSourceResolver,
    LedgerRentaExpenseAggregationSourceResolver,
    LedgerRentaGastoAggregationSourceResolver,
    LedgerRentaIncomeAggregationSourceResolver,
    RetencionesAggregationSourceResolver,
    aggregation_period_for_modelo,
)
from ._models import CasillaAggregation, CasillaProvenance
from ._oss_ioss import (
    OssIossLedgerCandidate,
    OssIossLedgerSourceResolver,
    aggregate_oss_ioss_bindings,
    aggregate_oss_ioss_from_repositories,
    oss_ioss_candidates_from_repositories,
    validate_oss_ioss_observation,
    validate_oss_ioss_observations,
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
from ._retenciones import (
    RetencionesAggregation,
    RetencionObservation,
    RetencionPerceptorRollup,
    aggregate_retenciones_111,
    aggregate_retenciones_115,
    aggregate_retenciones_123,
    aggregate_retenciones_180,
    aggregate_retenciones_190,
    aggregate_retenciones_193,
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
    RESERVED_SOURCE_KINDS,
    BindingSourceDisposition,
    BorradorSourceProvenance,
    CalculationSourceContext,
    CalculationSourceDiagnostic,
    CalculationSourceDiagnosticReason,
    CalculationSourceProvenance,
    CalculationSourceResolution,
    ModeloSourceResolver,
    build_binding_source_dispositions,
    collect_unhandled_source_diagnostics,
    merge_source_resolutions,
    merge_source_resolutions_by_precedence,
    storage_degradation_resolution,
)
from ._source_profile import ProfileSourceResolver
from ._withholding_observations_repository import (
    WithholdingObservationRepository,
    persist_withholding_observations,
    withholding_observation_key,
)
from ._withholding_source import WithholdingSourceResolver

__all__ = [
    "ACCEPTED_SOURCE_KINDS",
    "DEFERRED_SOURCE_KINDS",
    "MISSING_TRANSACTION_EVIDENCE_SOURCE_KIND",
    "RESERVED_SOURCE_KINDS",
    "AggregationCategoryCoverageError",
    "AggregationConfigError",
    "AggregationError",
    "AggregationErrorCodes",
    "AggregationMissingClassificationError",
    "AggregationPeriodError",
    "AggregationUnsupportedModeloError",
    "AggregationValidationError",
    "BindingSourceDisposition",
    "BorradorSourceProvenance",
    "CalculationSourceContext",
    "CalculationSourceDiagnostic",
    "CalculationSourceDiagnosticReason",
    "CalculationSourceProvenance",
    "CalculationSourceResolution",
    "CasillaAggregation",
    "CasillaProvenance",
    "CounterpartAggregation",
    "CounterpartObservation",
    "ForeignAssetClass",
    "ForeignAssetClassRollup",
    "ForeignAssetIngestObservation",
    "ForeignAssetsAggregation",
    "IvaLedgerAggregation",
    "IvaLedgerAggregationIssue",
    "IvaLedgerAggregationIssueReason",
    "IvaLedgerCandidate",
    "IvaLedgerInputKind",
    "LedgerIvaAggregationSourceResolver",
    "LedgerRentaExpenseAggregationSourceResolver",
    "LedgerRentaGastoAggregationSourceResolver",
    "LedgerRentaIncomeAggregationSourceResolver",
    "ModeloSourceResolver",
    "OperationKind347",
    "OperationKind349",
    "OssIossLedgerCandidate",
    "OssIossLedgerSourceResolver",
    "PerModeloAggregationCommand",
    "PerModeloAggregationContributor",
    "PerModeloAggregationLogFields",
    "PerModeloAggregationResult",
    "Period",
    "PeriodKind",
    "ProfileSourceResolver",
    "ProrrataLedgerReference",
    "RentaLedgerAggregationIssue",
    "RentaLedgerAggregationIssueReason",
    "RentaLedgerExpenseAggregation",
    "RetencionObservation",
    "RetencionObservationRepository",
    "RetencionPerceptorRollup",
    "RetencionScheme",
    "RetencionesAggregation",
    "RetencionesAggregationSourceResolver",
    "WithholdingObservation",
    "WithholdingObservationRepository",
    "WithholdingSourceResolver",
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
    "aggregate_renta_ledger_expenses",
    "aggregate_renta_ledger_expenses_from_repositories",
    "aggregate_retenciones_111",
    "aggregate_retenciones_115",
    "aggregate_retenciones_123",
    "aggregate_retenciones_180",
    "aggregate_retenciones_190",
    "aggregate_retenciones_193",
    "aggregation_period_for_modelo",
    "build_binding_source_dispositions",
    "collect_unhandled_source_diagnostics",
    "declarable_asset_classes_720",
    "declarable_class",
    "declarable_counterparty_nifs_347",
    "declarable_for_347",
    "get_per_modelo_aggregation_contract",
    "iva_ledger_missing_fact_reasons",
    "merge_source_resolutions",
    "merge_source_resolutions_by_precedence",
    "missing_evidence_advisory_observations",
    "oss_ioss_candidates_from_repositories",
    "persist_retencion_observations",
    "persist_withholding_observations",
    "retencion_observation_key",
    "stale_filed_revisions",
    "storage_degradation_resolution",
    "validate_iva_ledger_observation",
    "validate_iva_ledger_observations",
    "validate_oss_ioss_observation",
    "validate_oss_ioss_observations",
    "withholding_observation_key",
]
