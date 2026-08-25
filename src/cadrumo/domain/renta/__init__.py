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
:func:`build_renta_deductible_expense_observation`. The context carries
resolved usage-ratio, statutory-cap, and exclusive-use facts; profile
proportionality rules and citations remain in
:mod:`domain.categories`, while persisted operator overrides remain in
:mod:`domain.usage_ratios`. The
:data:`RENTA_100_FIRST_SLICE_EXPENSE_CASILLAS` table is the single Renta-domain
mapping from :class:`domain.categories.SpendingCategory` to registry
casilla ids for the supported first slice; the registry validates those targets
through a cross-domain snapshot check registered at package import time.
:data:`RENTA_130_RETENCIONES_OUTPUT_CASILLA` is the equivalent single-casilla
fact for the M130 retenciones-a-cuenta binding, validated by the same
mechanism.

The maritime surface exposes :class:`MaritimeWorkerFacts`, Art. 7.p and REBECA
eligibility/calculation helpers, the inactive DA 41 guard, and the RETMAR
mandatory-filing completeness gate. Exemption calculations route to
:data:`RENTA_EXENTA_CASILLA` and return
:class:`domain.calculations.registry.CasillaObservation` records with
legal and source provenance. This domain surface is pure substrate logic:
repositories, active-profile reads, CLI transport, and live AEAT access belong
outside :mod:`domain.renta`.

See Also:
    :mod:`domain.categories`
        Declares the spending-category taxonomy, proportionality rules, and
        legal citations that drive Renta deductibility decisions.
    :mod:`domain.usage_ratios`
        Persists operator business-use ratios before application aggregation
        passes them into :class:`RentaDeductibilityContext`.
    :mod:`application.aggregation`
        Loads active ledger and invoice evidence, builds Renta observations,
        and returns registry-ready source resolutions.
    :mod:`domain.calculations.registry`
        Owns binding declarations, casilla formulas, and the snapshot check
        contract that validates this domain's first-slice and retenciones
        routing facts.
"""

from __future__ import annotations

# Importing this module registers the first-slice routing referential-
# integrity check with the registry validator (Protocol-based dependency
# inversion -- the registry never imports renta). Imported for the
# registration side effect; no symbols are re-exported.
from . import _first_slice_routing_integrity as _first_slice_routing_integrity
from .errors import RentaValidationError
from ._ledger_expenses import (
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
    resolve_region_category_profiles,
    select_deductibility_profile,
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

# Importing this module ALSO registers the M130 retenciones output-casilla
# referential-integrity check with the registry validator, the same
# Protocol-based dependency inversion _first_slice_routing_integrity uses
# above. Unlike that module, this one's constant IS re-exported: it is the
# single source of truth application.aggregation reads for the redirect, not
# a mapping consumed only internally.
from ._retenciones_routing_integrity import (
    RENTA_130_RETENCIONES_BINDING_ID,
    RENTA_130_RETENCIONES_OUTPUT_CASILLA,
)
from ._substrate import EstimacionDirectaModalidad, RentaIncomeType

__all__ = [
    "ART_7P_EXEMPTION_CAP_EUR",
    "RENTA_100_FIRST_SLICE_EXPENSE_CASILLAS",
    "RENTA_130_RETENCIONES_BINDING_ID",
    "RENTA_130_RETENCIONES_OUTPUT_CASILLA",
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
    "RentaValidationError",
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
    "resolve_region_category_profiles",
    "select_deductibility_profile",
]
