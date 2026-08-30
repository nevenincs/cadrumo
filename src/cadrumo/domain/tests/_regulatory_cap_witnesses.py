"""Runtime witnesses proving each enrolled regulatory cap can bind.

Where a computed amount is ``min(value, cap)``, the cap only protects a taxpayer if
some reachable input makes the cap the BINDING term. A cap that no input can reach is
dead code wearing a regulatory name, and — the failure this gate exists for — a test
that CLAIMS to exercise the cap while its fixture lets the other term win reads as
coverage and is worth none.

That failure is not hypothetical here. Three tests were found in one evening reaching a
correct AEAT figure through a mechanism other than the one they claimed: a guardería
proration that bound on the declared-month count rather than the cap, an oracle built on
a child two years younger than the manual's, and a deceased-descendant suite whose
1 January birth dates made the straddle it named unreachable. Each passed before and
after the defect it was supposed to guard.

So this gate asks a question no test-name audit can: for every ``min``/``max`` in
production whose bound reads as a regulatory cap, is there a live, checked-in case where
varying the cap CHANGES the result? A witness that answers yes proves the term binds.

What this gate does NOT claim:

* It does not prove the cap's VALUE is right. That is external grounding, asserted
  against the registry parameters and their corpus anchors, and it is a different job.
* It does not prove every consumer of the cap is covered — only that the cap is
  reachable at the site, by at least one input.
* Its detector is a NAME heuristic over AST, so a cap passed as a bare literal, or held
  in a variable whose name does not read as a bound, is invisible to it. The enrolment
  maps below are therefore a floor on the population, never a census of it.

Exemptions are keyed by ``(module path, enclosing function)`` rather than by line
number, so moving code inside a function cannot silently retire an entry, and each one
states its reason. No count is asserted anywhere: the gate is on the property, so the
maps may grow or shrink freely without anyone editing a tally.

See Also:
    :mod:`~cadrumo.tests.test_classification_enrollment_inventory`
        The enrolment-ratchet precedent whose shape this follows.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import date
from decimal import Decimal

from ..categories import SpendingCategory, resolve_category_profiles
from ..contribuyente.deduccion_maternidad import compute_deduccion_maternidad_0611
from ..contribuyente.descendant import DescendantInfo
from ..contribuyente.family_profile import RentaFamilyProfile
from ..contribuyente.family_types import MinimoDescendientesThresholds
from ..fincas.amortization_ledger import compute_amortization_for_year
from ..fincas.enums import ExpenseCategory, UseType
from ..fincas.expense_rollup import CarryForwardEntry, compute_gastos_for_year
from ..fincas.models import Finca, FincaGasto, FincaRendimientoRecord
from ..renta import (
    MaritimeWorkerFacts,
    RentaDeductibilityContext,
    RentaDeductibleExpenseFact,
    calculate_art_7p_exemption,
    evaluate_renta_deductibility,
)

_SiteKey = tuple[str, str]

# ---------------------------------------------------------------------------
# Witnesses: each proves its site's cap is a term that can bind, by varying the
# cap and showing the result moves. None asserts a regulatory FIGURE — the caps
# here are supplied as probe inputs, so nothing in this module restates a value
# the registry owns (`aeat-registry-authority-flow`).
# ---------------------------------------------------------------------------

#: Synthetic eligibility ceilings. NOT the registry's figures and not a claim about
#: them: the descendants below declare no rentas, so any positive bound admits them,
#: and the witness is about the guardería cap rather than these.
_PROBE_THRESHOLDS = MinimoDescendientesThresholds(
    rentas_anuales_limite=Decimal("1"),
    declaracion_propia_rentas_limite=Decimal("1"),
)


def _witness_guarderia_prorated_cap() -> tuple[object, object]:
    """Spend far above the prorated cap, so ``min`` must take the cap."""
    child = DescendantInfo(
        birth_date=date(2022, 5, 1),
        meses_madre_trabajo=tuple(range(1, 13)),
        gastos_guarderia_mensuales=(),
        gastos_guarderia_euros=99_000,
    )
    profile = RentaFamilyProfile(descendientes=(child,))

    def total(cap_anual: Decimal) -> Decimal:
        return profile.incremento_guarderia_0613(2024, thresholds=_PROBE_THRESHOLDS, cap_anual=cap_anual)

    return total(Decimal("1000")), total(Decimal("400"))


def _witness_maternidad_anual_cap() -> tuple[object, object]:
    """An over-year accrual is reduced by the shipped annual cap."""
    uncapped_monthly_accrual = 13 * 100
    capped = compute_deduccion_maternidad_0611([("hijo-1", 13)], filing_year=2024)
    return uncapped_monthly_accrual, capped


def _witness_art_7p_exemption_cap() -> tuple[object, object]:
    """A salary whose pro-rata exceeds the Art. 7.p) ceiling."""
    facts = MaritimeWorkerFacts(
        worker_class="trabajador_del_mar",
        vessel_flag="foreign",
        waters_type="international",
    )

    uncapped_prorata = Decimal("200000")
    observation = calculate_art_7p_exemption(
        annual_salary=uncapped_prorata,
        qualifying_days=365,
        facts=facts,
    )
    assert observation.value is not None
    return uncapped_prorata, observation.value


def _witness_amortizacion_remaining_cap() -> tuple[object, object]:
    """Accrual against a construction-cost cap already nearly consumed."""
    finca = Finca(
        id=1,
        identifier="term-dominance",
        address="X",
        valor_catastral_total=Decimal("100000.00"),
        valor_catastral_construccion=Decimal("80000.00"),
        coste_adquisicion=Decimal("150000.00"),
        coste_adquisicion_construccion=Decimal("100000.00"),
        acquisition_date=date(2020, 1, 1),
        use_type=UseType.VIVIENDA_ARRENDADA,
    )
    income = FincaRendimientoRecord(
        contract_id=1,
        period_year=2025,
        gross_rent_received=Decimal("12000.00"),
        dias_alquilados=365,
    )

    def accrual(consumed: Decimal) -> Decimal:
        return compute_amortization_for_year(
            finca,
            income,
            cumulative_through_prior_year=consumed,
        ).capped_amortization

    # Almost the whole cap consumed leaves less headroom than one year's gross accrual,
    # so the remaining-cap term wins; an unconsumed cap leaves the gross accrual intact.
    return accrual(Decimal("0.00")), accrual(Decimal("99900.00"))


def _witness_art_23_1_capped_subtotal() -> tuple[object, object]:
    """Capped-category spend above gross rent, which art. 23.1 bounds it by."""
    expenses = [
        FincaGasto(
            finca_id=1,
            period_year=2025,
            category=ExpenseCategory.FINANCIACION_INTERESES,
            amount=Decimal("9000.00"),
        )
    ]

    def applied(ingresos: Decimal) -> Decimal:
        return compute_gastos_for_year(
            expenses,
            period_year=2025,
            ingresos_for_period=ingresos,
        ).capped_categories_applied

    return applied(Decimal("12000.00")), applied(Decimal("2000.00"))


def _witness_art_23_1_carry_capacity() -> tuple[object, object]:
    """Carry-forward consumption bounded by the capacity gross rent leaves."""
    carry = (CarryForwardEntry(origination_year=2023, remaining_amount=Decimal("5000.00")),)
    expenses = [
        FincaGasto(
            finca_id=1,
            period_year=2025,
            category=ExpenseCategory.FINANCIACION_INTERESES,
            amount=Decimal("1000.00"),
        )
    ]

    def applied(ingresos: Decimal) -> Decimal:
        return compute_gastos_for_year(
            expenses,
            period_year=2025,
            ingresos_for_period=ingresos,
            carry_forward_in=carry,
        ).capped_categories_applied

    # Wide capacity consumes the whole carry; narrow capacity is the binding term.
    return applied(Decimal("12000.00")), applied(Decimal("1500.00"))


def _witness_renta_statutory_cap() -> tuple[object, object]:
    """A per-person statutory cap, varied by the person count that scales it."""
    fact = RentaDeductibleExpenseFact(
        transaction_id="a" * 64,
        invoice_id="b" * 64,
        catalogue_id="ledger-2025",
        operation_date=date(2025, 3, 8),
        invoice_issue_date=date(2025, 3, 7),
        posting_date=date(2025, 3, 9),
        payment_date=date(2025, 3, 10),
        gross_amount=Decimal("800.00"),
        taxable_base=Decimal("779.00"),
        iva_amount=Decimal("21.00"),
        category=SpendingCategory.SEGUROS_SALUD_AUTONOMO,
        activity_key="main",
    )
    profile = resolve_category_profiles(2025)[SpendingCategory.SEGUROS_SALUD_AUTONOMO]

    def deductible(person_count: int) -> Decimal:
        context = RentaDeductibilityContext.model_validate(
            {"profile_year": 2025, "statutory_cap_person_count": person_count},
        )
        return evaluate_renta_deductibility(fact, profile, context).deductible_amount

    return deductible(1), deductible(4)


#: Regulatory cap sites, each bound to the witness proving its cap can bind.
REGULATORY_CAP_WITNESSES: Mapping[_SiteKey, Callable[..., tuple[object, object]]] = {
    ("domain/contribuyente/_family_profile.py", "incremento_guarderia_0613"): _witness_guarderia_prorated_cap,
    (
        "domain/contribuyente/_deduccion_maternidad.py",
        "compute_deduccion_maternidad_0611",
    ): _witness_maternidad_anual_cap,
    ("domain/renta/_maritime_exemption.py", "calculate_art_7p_exemption"): _witness_art_7p_exemption_cap,
    ("domain/fincas/_amortization_ledger.py", "compute_amortization_for_year"): _witness_amortizacion_remaining_cap,
    ("domain/fincas/_expense_rollup.py", "compute_gastos_for_year"): _witness_art_23_1_capped_subtotal,
    ("domain/fincas/_expense_rollup.py", "_consume_carry"): _witness_art_23_1_carry_capacity,
    ("domain/renta/_ledger_expenses.py", "evaluate_renta_deductibility"): _witness_renta_statutory_cap,
}
