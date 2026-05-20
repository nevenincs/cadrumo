"""Public surface for the Renta (IRPF / Modelo 100) substrate.

Re-exports the closed-membership classification enums that downstream
consumers (formula bindings, CCAA-conditional deductions, application-
layer extractors) use to tag a Renta domain value.
"""

from __future__ import annotations

# Importing this module registers the first-slice routing referential-
# integrity check with the registry validator (Protocol-based dependency
# inversion -- the registry never imports renta). Imported for the
# registration side effect; no symbols are re-exported.
from . import _first_slice_routing_integrity as _first_slice_routing_integrity
from ._ledger_expenses import (
    LEDGER_RENTA_EXPENSE_SOURCE,
    RENTA_100_FIRST_SLICE_EXPENSE_CASILLAS,
    RentaDeductibilityContext,
    RentaDeductibilityResult,
    RentaDeductibilityStatus,
    RentaDeductibleExpenseFact,
    RentaDeductibleExpenseObservation,
    RentaExpenseDirection,
    RentaInvoiceEvidenceStatus,
    RentaReconciliationStatus,
    build_renta_deductible_expense_observation,
    evaluate_renta_deductibility,
    normalize_spending_category,
)
from ._substrate import EstimacionDirectaModalidad, RentaIncomeType

__all__ = [
    "LEDGER_RENTA_EXPENSE_SOURCE",
    "RENTA_100_FIRST_SLICE_EXPENSE_CASILLAS",
    "EstimacionDirectaModalidad",
    "RentaDeductibilityContext",
    "RentaDeductibilityResult",
    "RentaDeductibilityStatus",
    "RentaDeductibleExpenseFact",
    "RentaDeductibleExpenseObservation",
    "RentaExpenseDirection",
    "RentaIncomeType",
    "RentaInvoiceEvidenceStatus",
    "RentaReconciliationStatus",
    "build_renta_deductible_expense_observation",
    "evaluate_renta_deductibility",
    "normalize_spending_category",
]
