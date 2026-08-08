"""Term-dominance gate: every regulatory cap must be a term that can actually bind.

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

import ast
from collections.abc import Callable, Mapping
from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from ..domain.categories import SpendingCategory, resolve_category_profiles
from ..domain.contribuyente import (
    DescendantInfo,
    MinimoDescendientesThresholds,
    RentaFamilyProfile,
    compute_deduccion_maternidad_0611,
)
from ..domain.fincas import (
    CarryForwardEntry,
    ExpenseCategory,
    Finca,
    FincaGasto,
    FincaRendimientoRecord,
    UseType,
    compute_amortization_for_year,
    compute_gastos_for_year,
)
from ..domain.renta import (
    MaritimeWorkerFacts,
    RentaDeductibilityContext,
    RentaDeductibleExpenseFact,
    calculate_art_7p_exemption,
    evaluate_renta_deductibility,
)
from ._inventory import aeat_relative, production_ast_items

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@contextmanager
def _replacing(target: object, name: str, value: object):
    """Replace ``target.name`` for the scope, restoring the original on exit."""
    original = getattr(target, name)
    setattr(target, name, value)
    try:
        yield
    finally:
        setattr(target, name, original)


_SiteKey = tuple[str, str]

#: Substrings that make an operand name read as a BOUND rather than a quantity.
#: Deliberately generous — a false positive costs one reasoned exemption line, while a
#: false negative silently drops a regulatory cap out of the gate's population.
_BOUND_NAME_FRAGMENTS = (
    "CAP",
    "CEILING",
    "LIMIT",
    "LIMITE",
    "MAX_",
    "_MAX",
    "THRESHOLD",
    "TOPE",
    "MINIMO",
    "FLOOR",
)


def _bound_operand_name(node: ast.expr) -> str | None:
    """Return the operand's name when it reads as a bound, else ``None``."""
    if isinstance(node, ast.Name):
        name = node.id
    elif isinstance(node, ast.Attribute):
        name = node.attr
    else:
        return None
    return name if any(fragment in name.upper() for fragment in _BOUND_NAME_FRAGMENTS) else None


def _enclosing_function_by_line(tree: ast.AST) -> Mapping[int, str]:
    """Map every line owned by a function body to that function's name.

    Innermost wins, which is what makes the key stable: a cap inside a nested helper is
    attributed to the helper, so extracting or inlining that helper is a visible
    enrolment change rather than a silent one.
    """
    owner: dict[int, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            for child in ast.walk(node):
                lineno = getattr(child, "lineno", None)
                if lineno is not None:
                    owner[lineno] = node.name
    return owner


def _discovered_cap_sites() -> dict[_SiteKey, set[str]]:
    """Every production ``min``/``max`` call whose bound operand reads as a cap."""
    sites: dict[_SiteKey, set[str]] = {}
    for path, tree in production_ast_items():
        owner = _enclosing_function_by_line(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            if node.func.id not in {"min", "max"}:
                continue
            for arg in node.args:
                name = _bound_operand_name(arg)
                if name is None:
                    continue
                key = (aeat_relative(Path(path)), owner.get(node.lineno, "<module>"))
                sites.setdefault(key, set()).add(name)
    return sites


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
    """Twelve months of deducción, which the annual cap is there to bound."""
    from ..domain.contribuyente import _deduccion_maternidad as module

    def total(cap: int) -> int:
        with _replacing(module, "DEDUCCION_MATERNIDAD_ANUAL_CAP_EUR", cap):
            return compute_deduccion_maternidad_0611([("hijo-1", 12)], filing_year=2024)

    return total(1_200), total(300)


def _witness_art_7p_exemption_cap() -> tuple[object, object]:
    """A salary whose pro-rata exceeds the Art. 7.p) ceiling."""
    from ..domain.renta import _maritime_exemption as module

    facts = MaritimeWorkerFacts(
        worker_class="trabajador_del_mar",
        vessel_flag="foreign",
        waters_type="international",
    )

    def exempt(cap: Decimal) -> Decimal:
        with _replacing(module, "ART_7P_EXEMPTION_CAP_EUR", cap):
            observation = calculate_art_7p_exemption(
                annual_salary=Decimal("200000"),
                qualifying_days=365,
                facts=facts,
            )
        assert observation.value is not None
        return observation.value

    return exempt(Decimal("60100")), exempt(Decimal("30000"))


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
        transaction_id="tx-1",
        invoice_id="inv-1",
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
_REGULATORY_CAP_WITNESSES: Mapping[_SiteKey, Callable[..., tuple[object, object]]] = {
    ("domain/contribuyente/family.py", "incremento_guarderia_0613"): _witness_guarderia_prorated_cap,
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

#: Sites the detector finds whose bound is not a regulatory cap, each with its reason.
_NON_REGULATORY_EXEMPTIONS: Mapping[_SiteKey, str] = {
    ("adapters/outbound/google/_calc_sheets_apply.py", "_condition_for_constraint"): (
        "Spreadsheet data-validation bounds rendered into a Sheets condition. The floor "
        "and ceiling are presentation constraints on a cell, not a tax limit."
    ),
    ("adapters/persistence/storage/attachment.py", "_merge_with_stored_manifest"): (
        "Name matches the 'CAP' fragment by accident: 'captured_at' is a timestamp, and "
        "the min picks the earlier capture instant when merging two manifests."
    ),
    ("adapters/persistence/storage/master_key/_login_throttle.py", "_required_wait_seconds"): (
        "Authentication backoff bounds (exponent and wait ceiling). A security control "
        "on retry rate with no regulatory figure behind it."
    ),
    ("llm/_client.py", "backoff_for"): (
        "Exponential retry-backoff delay clamped to a maximum wait between LLM transport "
        "attempts. A transport-engineering ceiling with no regulatory figure behind it, "
        "the same shape as the auth-throttle wait ceiling above."
    ),
    ("application/flows/_engine.py", "set_instance_count"): (
        "Repeating-section instance count clamped to the flow's declared maximum — a "
        "form-authoring bound, not a tax cap."
    ),
    ("application/flows/_engine.py", "_instance_count"): (
        "Same flow-authoring instance bound as set_instance_count, read rather than set."
    ),
    ("application/flows/_engine.py", "_refresh_instance_counts"): (
        "Same flow-authoring instance bound, re-applied when the section list changes."
    ),
    ("application/flows/_resume.py", "_seed_counts"): (
        "Same flow-authoring instance bound, applied when a saved flow is resumed."
    ),
    ("application/user_profile/_section_rows.py", "next_section_row_index"): (
        "Row-index floor keeping the next index non-negative. An indexing invariant."
    ),
}


def test_every_discovered_cap_site_is_enrolled() -> None:
    """A new ``min``/``max`` over a cap-named bound must be classified before it lands.

    Either it is a regulatory cap and needs a witness proving it can bind, or it is not
    and needs a stated reason. The failure mode this refuses is a cap arriving with
    neither, which is how a bound nothing exercises becomes indistinguishable from one
    that is load-bearing.
    """
    discovered = _discovered_cap_sites()
    enrolled = set(_REGULATORY_CAP_WITNESSES) | set(_NON_REGULATORY_EXEMPTIONS)
    unenrolled = sorted(key for key in discovered if key not in enrolled)
    if unenrolled:
        listed = "\n  ".join(
            f"{path}::{function}  bound={sorted(discovered[(path, function)])}" for path, function in unenrolled
        )
        raise AssertionError(
            f"{len(unenrolled)} unenrolled min/max cap site(s):\n  {listed}\n\n"
            "If the bound is a regulatory cap, add it to _REGULATORY_CAP_WITNESSES with "
            "a witness that varies the cap and shows the result move. If it is not, add "
            "it to _NON_REGULATORY_EXEMPTIONS with the reason it is not a tax limit.",
        )


def test_no_enrolment_outlives_its_site() -> None:
    """A witness or exemption for a site that no longer exists is stale and must go.

    Without this, a refactor that deletes a cap leaves its entry behind, and the next
    reader takes the entry as evidence the cap is still guarded.
    """
    discovered = set(_discovered_cap_sites())
    stale = sorted(
        key for key in (set(_REGULATORY_CAP_WITNESSES) | set(_NON_REGULATORY_EXEMPTIONS)) if key not in discovered
    )
    if stale:
        listed = "\n  ".join(f"{path}::{function}" for path, function in stale)
        raise AssertionError(
            f"{len(stale)} enrolment(s) name a site the detector no longer finds:\n  {listed}\n\n"
            "Remove the entry, or restore the site it was written for.",
        )


@pytest.mark.parametrize(
    "site",
    sorted(_REGULATORY_CAP_WITNESSES),
    ids=lambda site: f"{site[0]}::{site[1]}",
)
def test_each_regulatory_cap_is_a_term_that_binds(site: _SiteKey) -> None:
    """Varying the cap must change the result, or the cap is not the binding term.

    This is the behavioural half. Enrolment alone would be bookkeeping: it would record
    that someone classified the site, never that the cap does anything. Two results that
    agree mean every input the witness supplies is decided by the OTHER term, which is
    precisely the shape that let a substituted fixture read as cap coverage.
    """
    witness = _REGULATORY_CAP_WITNESSES[site]
    wide, narrow = witness()

    assert wide != narrow, (
        f"{site[0]}::{site[1]}: the cap is not the binding term for this witness — "
        f"both cap values yield {wide!r}. Either the witness's other term dominates "
        "(fix the witness inputs) or the cap has stopped being applied (fix the code)."
    )
