"""Public surface for the Renta (IRPF / Modelo 100) substrate.

Re-exports the closed-membership classification enums that downstream
consumers (formula bindings, CCAA-conditional deductions, application-
layer extractors) use to tag a Renta domain value.

The first-slice ledger-expense surface exports
:class:`RentaDeductibleExpenseFact`, :class:`RentaDeductibilityResult`, and
:class:`RentaDeductibleExpenseObservation` together with
:func:`evaluate_renta_deductibility` and
:func:`build_renta_deductible_expense_observation` for Modelo 100 bindings.
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
from ._maritime_exemption import (
    ART_7P_EXEMPTION_CAP_EUR,
    RENTA_EXENTA_CASILLA,
    MaritimeExemptionInactiveError,
    MaritimeWorkerFacts,
    ProfileCompletenessError,
    art_7p_eligible,
    calculate_art_7p_exemption,
    calculate_rebeca_exemption,
    check_retmar_mandatory_filing,
    da41_eligible,
    guard_da41_inactive,
    rebeca_eligible,
)
from ._substrate import EstimacionDirectaModalidad, RentaIncomeType

__all__ = [
    "ART_7P_EXEMPTION_CAP_EUR",
    "LEDGER_RENTA_EXPENSE_SOURCE",
    "RENTA_100_FIRST_SLICE_EXPENSE_CASILLAS",
    "RENTA_EXENTA_CASILLA",
    "EstimacionDirectaModalidad",
    "MaritimeExemptionInactiveError",
    "MaritimeWorkerFacts",
    "ProfileCompletenessError",
    "RentaDeductibilityContext",
    "RentaDeductibilityResult",
    "RentaDeductibilityStatus",
    "RentaDeductibleExpenseFact",
    "RentaDeductibleExpenseObservation",
    "RentaExpenseDirection",
    "RentaIncomeType",
    "RentaInvoiceEvidenceStatus",
    "RentaReconciliationStatus",
    "art_7p_eligible",
    "build_renta_deductible_expense_observation",
    "calculate_art_7p_exemption",
    "calculate_rebeca_exemption",
    "check_retmar_mandatory_filing",
    "da41_eligible",
    "evaluate_renta_deductibility",
    "guard_da41_inactive",
    "normalize_spending_category",
    "rebeca_eligible",
]
