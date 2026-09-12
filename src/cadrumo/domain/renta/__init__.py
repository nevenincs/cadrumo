"""Public facade for the Renta (IRPF / Modelo 100) substrate.

This package owns the first-slice Modelo 100 ledger-expense observation
surface and the maritime worker exemption selectors used by application
calculation previews.

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
The M130 retenciones-a-cuenta route is selected from governed registry data
and validated by the same cross-domain mechanism.

The maritime surface exposes :class:`MaritimeWorkerFacts`, Art. 7.p and REBECA
eligibility/calculation helpers, the inactive DA 41 guard, and the RETMAR
mandatory-filing completeness gate. Exemption calculations resolve their
target from registry authority and return
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

__all__: tuple[str, ...] = ()
