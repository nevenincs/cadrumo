"""Financial aggregation: roll classified ledger entries into casilla inputs.

Turns the classified ledger and profile facts into the per-casilla and
per-binding values a modelo calculation consumes, with one aggregation
family per AEAT surface (IVA, retenciones, third-party operations, foreign
assets, prorrata, OSS / IOSS, renta expenses). Pure value logic; the
repositories it reads are injected.

Major declarations:

* :func:`aggregate_per_modelo` with :class:`PerModeloAggregationProvider`
  and :class:`PerModeloAggregationResult` — the unified per-modelo entry
  point.
* :func:`aggregate_iva_ledger_observations` with :class:`IvaLedgerAggregation`
  — the IVA (Modelo 303 family) rollup.
* :func:`aggregate_retenciones_111` and its 115 / 123 / 180 / 190 / 193
  siblings, with :class:`RetencionesAggregation` — withholding rollups.
* :func:`aggregate_counterpart_347`, :func:`aggregate_counterpart_349`, and
  :func:`aggregate_foreign_assets_720` — informativa rollups.
* :class:`CasillaAggregation` and :class:`CasillaProvenance` — the typed
  aggregated value plus the source provenance it carries.
* :class:`ModeloSourceResolver` and :class:`CalculationSourceResolution` —
  the source mesh that reconciles ledger, profile, and registry sources.
* :class:`AggregationError` and its subclasses — the failure taxonomy.
"""

from __future__ import annotations

from ...core.aggregation import ForeignAssetClass, OperationKind347, OperationKind349, RetencionScheme
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
    LedgerRentaIncomeAggregationSourceResolver,
    ModeloLedgerBindingAggregation,
    aggregation_period_for_modelo,
)
from ._models import CasillaAggregation, CasillaProvenance, Period, PeriodKind, Quarter
from ._oss_ioss import (
    OssIossLedgerCandidate,
    OssIossLedgerSourceResolver,
    aggregate_oss_ioss_bindings,
    validate_oss_ioss_observation,
    validate_oss_ioss_observations,
)
from ._prorrata import (
    IvaOperation,
    IvaOperationKind,
    ProrrataAggregation,
    aggregate_definitiva_prorrata,
    aggregate_prorrata_inputs,
    aggregate_provisional_prorrata,
)
from ._registry_provider import (
    PerModeloRegistryBindingResolution,
    resolve_per_modelo_registry_binding_values,
)
from ._renta_ledger import (
    RentaLedgerAggregationIssue,
    RentaLedgerAggregationIssueReason,
    RentaLedgerExpenseAggregation,
    aggregate_renta_ledger_expenses,
    aggregate_renta_ledger_expenses_from_repositories,
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
    AggregationSourceKind,
    PerModeloAggregationCommand,
    PerModeloAggregationLogFields,
    PerModeloAggregationProvider,
    PerModeloAggregationResult,
    aggregate_per_modelo,
    get_per_modelo_aggregation_contract,
)
from ._source_mesh import (
    DEFERRED_SOURCE_KINDS,
    CalculationSourceContext,
    CalculationSourceDiagnostic,
    CalculationSourceDiagnosticReason,
    CalculationSourceProvenance,
    CalculationSourceResolution,
    ModeloSourceResolver,
    collect_unhandled_source_diagnostics,
    merge_source_resolutions,
    storage_degradation_resolution,
)
from ._source_profile import ProfileSourceResolver

__all__ = [
    "ACCEPTED_SOURCE_KINDS",
    "DEFERRED_SOURCE_KINDS",
    "MISSING_TRANSACTION_EVIDENCE_SOURCE_KIND",
    "AggregationCategoryCoverageError",
    "AggregationConfigError",
    "AggregationError",
    "AggregationErrorCodes",
    "AggregationMissingClassificationError",
    "AggregationPeriodError",
    "AggregationSourceKind",
    "AggregationUnsupportedModeloError",
    "AggregationValidationError",
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
    "IvaOperation",
    "IvaOperationKind",
    "LedgerIvaAggregationSourceResolver",
    "LedgerRentaExpenseAggregationSourceResolver",
    "LedgerRentaIncomeAggregationSourceResolver",
    "ModeloLedgerBindingAggregation",
    "ModeloSourceResolver",
    "OperationKind347",
    "OperationKind349",
    "OssIossLedgerCandidate",
    "OssIossLedgerSourceResolver",
    "PerModeloAggregationCommand",
    "PerModeloAggregationLogFields",
    "PerModeloAggregationProvider",
    "PerModeloAggregationResult",
    "PerModeloRegistryBindingResolution",
    "Period",
    "PeriodKind",
    "ProfileSourceResolver",
    "ProrrataAggregation",
    "ProrrataLedgerReference",
    "Quarter",
    "RentaLedgerAggregationIssue",
    "RentaLedgerAggregationIssueReason",
    "RentaLedgerExpenseAggregation",
    "RetencionObservation",
    "RetencionPerceptorRollup",
    "RetencionScheme",
    "RetencionesAggregation",
    "aggregate_counterpart_347",
    "aggregate_counterpart_349",
    "aggregate_definitiva_prorrata",
    "aggregate_foreign_assets_720",
    "aggregate_iva_ledger_candidate_bindings",
    "aggregate_iva_ledger_candidates",
    "aggregate_iva_ledger_observations",
    "aggregate_iva_ledger_observations_from_repositories",
    "aggregate_oss_ioss_bindings",
    "aggregate_per_modelo",
    "aggregate_prorrata_inputs",
    "aggregate_provisional_prorrata",
    "aggregate_renta_ledger_expenses",
    "aggregate_renta_ledger_expenses_from_repositories",
    "aggregate_retenciones_111",
    "aggregate_retenciones_115",
    "aggregate_retenciones_123",
    "aggregate_retenciones_180",
    "aggregate_retenciones_190",
    "aggregate_retenciones_193",
    "aggregation_period_for_modelo",
    "collect_unhandled_source_diagnostics",
    "declarable_asset_classes_720",
    "declarable_class",
    "declarable_counterparty_nifs_347",
    "declarable_for_347",
    "get_per_modelo_aggregation_contract",
    "iva_ledger_missing_fact_reasons",
    "merge_source_resolutions",
    "missing_evidence_advisory_observations",
    "resolve_per_modelo_registry_binding_values",
    "stale_filed_revisions",
    "storage_degradation_resolution",
    "validate_iva_ledger_observation",
    "validate_iva_ledger_observations",
    "validate_oss_ioss_observation",
    "validate_oss_ioss_observations",
]
