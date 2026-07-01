"""Public facade for the Renta (IRPF / Modelo 100) substrate.

This package re-exports closed IRPF classifiers such as
:class:`EstimacionDirectaModalidad` and :class:`RentaIncomeType`, the
first-slice Modelo 100 ledger-expense observation surface, and the maritime
worker exemption selectors used by application calculation previews.

The first-slice expense path evaluates :class:`RentaDeductibleExpenseFact`
values with :class:`RentaDeductibilityContext` and category-profile evidence
into :class:`RentaDeductibilityResult` values, then materialises binding-ready
:class:`RentaDeductibleExpenseObservation` records through
:func:`evaluate_renta_deductibility` and
:func:`build_renta_deductible_expense_observation`. The
:data:`RENTA_100_FIRST_SLICE_EXPENSE_CASILLAS` table is the single Renta-domain
mapping from :class:`~aeat.domain.categories.SpendingCategory` to registry
casilla ids for the supported first slice; the registry validates those targets
through a cross-domain snapshot check registered at package import time.

The maritime surface exposes :class:`MaritimeWorkerFacts`, Art. 7.p and REBECA
eligibility/calculation helpers, the inactive DA 41 guard, and the RETMAR
mandatory-filing completeness gate. Exemption calculations route to
:data:`RENTA_EXENTA_CASILLA` and return
:class:`~aeat.domain.calculations.registry.CasillaObservation` records with
legal and source provenance. This domain surface is pure substrate logic:
repositories, active-profile reads, CLI transport, and live AEAT access belong
outside :mod:`aeat.domain.renta`.
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
