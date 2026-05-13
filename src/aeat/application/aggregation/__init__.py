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
from ._models import CasillaAggregation, CasillaProvenance, Period, PeriodKind, Quarter
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
    "Period",
    "PeriodKind",
    "ProrrataAggregation",
    "Quarter",
    "RentaLedgerAggregationIssue",
    "RentaLedgerAggregationIssueReason",
    "RentaLedgerExpenseAggregation",
    "VatOperation",
    "VatOperationKind",
    "aggregate_definitiva_prorrata",
    "aggregate_prorrata_inputs",
    "aggregate_provisional_prorrata",
    "aggregate_renta_ledger_expenses",
    "aggregate_renta_ledger_expenses_from_repositories",
]
