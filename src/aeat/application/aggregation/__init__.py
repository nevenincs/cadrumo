"""Financial aggregation value models."""

from __future__ import annotations

from ._errors import (
    AggregationCategoryCoverageError,
    AggregationError,
    AggregationMissingClassificationError,
    AggregationPeriodError,
    AggregationUnsupportedModeloError,
    AggregationValidationError,
)
from ._iva_ledger import (
    IvaLedgerAggregation,
    IvaLedgerAggregationIssue,
    IvaLedgerAggregationIssueReason,
    ProrrataLedgerReference,
    aggregate_iva_ledger_observations,
    aggregate_iva_ledger_observations_from_repositories,
    iva_ledger_missing_fact_reasons,
)
from ._modelo_bindings import (
    ModeloLedgerBindingAggregation,
    aggregation_period_for_modelo,
    resolve_modelo_ledger_binding_values_from_repositories,
)
from ._models import CasillaAggregation, CasillaProvenance, Period, PeriodKind, Quarter
from ._oss_ioss import (
    OssIossLedgerCandidate,
    aggregate_oss_ioss_bindings,
    validate_oss_ioss_observation,
    validate_oss_ioss_observations,
)
from ._prorrata import (
    ProrrataAggregation,
    VatOperation,
    VatOperationKind,
    aggregate_definitiva_prorrata,
    aggregate_prorrata_inputs,
    aggregate_provisional_prorrata,
)
from ._renta_ledger import (
    RentaLedgerAggregationIssue,
    RentaLedgerAggregationIssueReason,
    RentaLedgerExpenseAggregation,
    aggregate_renta_ledger_expenses,
    aggregate_renta_ledger_expenses_from_repositories,
)

__all__ = [
    "AggregationCategoryCoverageError",
    "AggregationError",
    "AggregationMissingClassificationError",
    "AggregationPeriodError",
    "AggregationUnsupportedModeloError",
    "AggregationValidationError",
    "CasillaAggregation",
    "CasillaProvenance",
    "IvaLedgerAggregation",
    "IvaLedgerAggregationIssue",
    "IvaLedgerAggregationIssueReason",
    "ModeloLedgerBindingAggregation",
    "OssIossLedgerCandidate",
    "Period",
    "PeriodKind",
    "ProrrataAggregation",
    "ProrrataLedgerReference",
    "Quarter",
    "RentaLedgerAggregationIssue",
    "RentaLedgerAggregationIssueReason",
    "RentaLedgerExpenseAggregation",
    "VatOperation",
    "VatOperationKind",
    "aggregate_definitiva_prorrata",
    "aggregate_iva_ledger_observations",
    "aggregate_iva_ledger_observations_from_repositories",
    "aggregate_oss_ioss_bindings",
    "aggregate_prorrata_inputs",
    "aggregate_provisional_prorrata",
    "aggregate_renta_ledger_expenses",
    "aggregate_renta_ledger_expenses_from_repositories",
    "aggregation_period_for_modelo",
    "iva_ledger_missing_fact_reasons",
    "resolve_modelo_ledger_binding_values_from_repositories",
    "validate_oss_ioss_observation",
    "validate_oss_ioss_observations",
]
