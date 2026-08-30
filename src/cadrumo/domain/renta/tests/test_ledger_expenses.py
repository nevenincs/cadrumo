"""Tests for Renta ledger-derived deductible expense observations."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....core import BindingSourceKind
from ....core.i18n import Translatable as tr
from ....tests.aeat_literal_fixtures import RENTA_DEDUCIBILIDAD_CITATION_URL_FIXTURE
from ...categories.profile import CategoryProfile
from ...categories.proportionality import CategoryCitation, CategoryCitationSource, ProportionalityKind, ProportionalityRule, parse_http_url
from ...categories.registry import resolve_category_profiles
from ...categories.spending_category import SpendingCategory, SpendingCategoryFamily
from .. import (
    RentaDeductibilityContext,
    RentaDeductibilityStatus,
    RentaDeductibleExpenseFact,
    RentaExpenseDirection,
    RentaInvoiceEvidenceStatus,
    RentaReconciliationStatus,
    build_renta_deductible_expense_observation,
    evaluate_renta_deductibility,
    normalize_spending_category,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _fact(
    *,
    category: SpendingCategory,
    amount: Decimal = Decimal("100.00"),
    taxable_base: Decimal | None = None,
    iva_amount: Decimal | None = None,
    invoice_id: str | None = "inv-1",
    direction: RentaExpenseDirection = RentaExpenseDirection.OUTGOING_EXPENSE,
) -> RentaDeductibleExpenseFact:
    default_has_iva = amount >= Decimal("21.00")
    default_taxable_base = amount - Decimal("21.00") if default_has_iva else amount
    default_iva_amount = Decimal("21.00") if default_has_iva else Decimal("0.00")
    base = taxable_base if taxable_base is not None else default_taxable_base
    iva = iva_amount if iva_amount is not None else default_iva_amount
    return RentaDeductibleExpenseFact(
        transaction_id="a" * 64,
        invoice_id=invoice_id,
        catalogue_id="ledger-2025",
        operation_date=date(2025, 3, 8),
        invoice_issue_date=date(2025, 3, 7) if invoice_id is not None else None,
        posting_date=date(2025, 3, 9),
        payment_date=date(2025, 3, 10),
        gross_amount=amount,
        taxable_base=base,
        iva_amount=iva,
        direction=direction,
        category=category,
        activity_key="main",
    )


def _context(**overrides: object) -> RentaDeductibilityContext:
    payload: dict[str, object] = {"profile_year": 2025}
    payload.update(overrides)
    return RentaDeductibilityContext.model_validate(payload)


def _citation() -> CategoryCitation:
    return CategoryCitation(
        source=CategoryCitationSource.MANUAL_RENTA,
        reference="Manual practico Renta 2025",
        locator="test",
        url=parse_http_url(RENTA_DEDUCIBILIDAD_CITATION_URL_FIXTURE),
        quote=tr("Texto de prueba para una regla de deducibilidad."),
        valid_from=date(2025, 1, 1),
        valid_to=date(2025, 12, 31),
    )


def _profile(category: SpendingCategory, rule: ProportionalityRule) -> CategoryProfile:
    return CategoryProfile(
        category=category,
        display_label=tr(f"Perfil de prueba {category.value}"),
        proportionality=rule,
    )


def test_full_deductible_first_slice_fact_builds_binding_ready_observation() -> None:
    fact = _fact(
        category=SpendingCategory.CUOTAS_AUTONOMOS_SS,
        amount=Decimal("294.00"),
        taxable_base=Decimal("273.00"),
        iva_amount=Decimal("21.00"),
    )
    result = evaluate_renta_deductibility(
        fact,
        resolve_category_profiles(2025)[SpendingCategory.CUOTAS_AUTONOMOS_SS],
        _context(),
    )

    observation = build_renta_deductible_expense_observation(fact, result, tax_year=2025)

    assert result.status is RentaDeductibilityStatus.ELIGIBLE
    assert observation.source_kind is BindingSourceKind.LEDGER_RENTA_GASTOS_ESTIMACION_DIRECTA_AGGREGATION
    assert observation.target_casilla_id == "0186"
    assert observation.filing_date == date(2025, 3, 7)
    assert observation.gross_amount == Decimal("294.00")
    assert observation.taxable_base == Decimal("273.00")
    assert observation.iva_amount == Decimal("21.00")
    assert observation.deductible_amount == Decimal("273.00")
    assert observation.non_deductible_amount == Decimal("21.00")
    assert observation.invoice_evidence_status is RentaInvoiceEvidenceStatus.LINKED
    assert observation.reconciliation_status is RentaReconciliationStatus.LINKED_INVOICE
    assert observation.legal_references


def test_transaction_only_fact_uses_operation_date_and_prevents_invoice_evidence() -> None:
    fact = _fact(
        category=SpendingCategory.GASTOS_BANCARIOS,
        amount=Decimal("48.00"),
        invoice_id=None,
    )
    result = evaluate_renta_deductibility(
        fact,
        resolve_category_profiles(2025)[SpendingCategory.GASTOS_BANCARIOS],
        _context(),
    )

    observation = build_renta_deductible_expense_observation(fact, result, tax_year=2025)

    assert observation.target_casilla_id == "0203"
    assert observation.filing_date == date(2025, 3, 8)
    assert observation.invoice_id is None
    assert observation.invoice_evidence_status is RentaInvoiceEvidenceStatus.NONE
    assert observation.reconciliation_status is RentaReconciliationStatus.TRANSACTION_ONLY


def test_linked_refund_preserves_category_and_becomes_negative_observation() -> None:
    fact = _fact(
        category=SpendingCategory.GASTOS_FINANCIEROS,
        amount=Decimal("35.00"),
        taxable_base=Decimal("14.00"),
        iva_amount=Decimal("21.00"),
        direction=RentaExpenseDirection.REFUND,
    )
    result = evaluate_renta_deductibility(
        fact,
        resolve_category_profiles(2025)[SpendingCategory.GASTOS_FINANCIEROS],
        _context(),
    )

    observation = build_renta_deductible_expense_observation(fact, result, tax_year=2025)

    assert observation.sign == -1
    assert observation.target_casilla_id == "0203"
    assert observation.gross_amount == Decimal("-35.00")
    assert observation.taxable_base == Decimal("-14.00")
    assert observation.iva_amount == Decimal("-21.00")
    assert observation.deductible_amount == Decimal("-14.00")
    assert observation.non_deductible_amount == Decimal("-21.00")


def test_unlinked_refund_is_rejected_before_it_can_enter_calculation() -> None:
    with pytest.raises(ValidationError, match="refund and reversal facts must be linked"):
        _fact(
            category=SpendingCategory.GASTOS_FINANCIEROS,
            invoice_id=None,
            direction=RentaExpenseDirection.REFUND,
        )


def test_wholly_exempt_activity_joins_the_full_iva_amount_to_the_deductible_cost() -> None:
    """A médico radiólogo's non-deductible input IVA becomes part of the gasto.

    AEAT Manual práctico de Renta 2024, Parte 1, Capítulo 7, caso práctico
    "determinación del rendimiento neto derivado de actividad profesional en
    estimación directa, modalidad simplificada" (extracted markdown
    L19807-L19965). The "Gastos" table lists "IVA soportado" as its own line,
    unchanged between "valores registrados" and "valores fiscales" (1.600 -> 1.600,
    L19900), and nota (7) (L19946-19947) states why: "Se deduce como gasto el IVA
    soportado por tratarse de una actividad exenta de este impuesto que no da
    derecho a deducir las cuotas soportadas." A radiólogo's clinical activity is
    exempt (LIVA art. 20.Uno.3.º), so it has NO right to deduct any of its input
    IVA: the whole 1.600 EUR is fiscally deductible cost, not the base alone.

    The 1.600 IVA figure is AEAT's own; the base is an arbitrary fixture amount
    (the manual aggregates a year of "gastos corrientes" into one IVA figure with
    no per-purchase base), so only the addition itself -- not this specific
    base+IVA total -- is checked against the manual.
    """
    fact = _fact(
        category=SpendingCategory.MATERIAL_OFICINA,
        amount=Decimal("9600.00"),
        taxable_base=Decimal("8000.00"),
        iva_amount=Decimal("1600.00"),
    )

    result = evaluate_renta_deductibility(
        fact,
        resolve_category_profiles(2025)[SpendingCategory.MATERIAL_OFICINA],
        _context(iva_deduction_ratio=Decimal("0")),
    )

    assert result.status is RentaDeductibilityStatus.ELIGIBLE
    assert result.deductible_amount == Decimal("9600.00")
    assert result.non_deductible_amount == Decimal("0.00")


def test_prorrata_rationed_activity_joins_only_the_non_deductible_iva_share() -> None:
    """A prorrata-general taxpayer joins only the non-recoverable IVA fraction.

    LIVA art. 104.Uno: under prorrata general a single percentage governs how
    much soportado is deductible; the rest is not recoverable through the IVA
    return and is PGC NRV 12.ª acquisition cost, same as the wholly-exempt case
    above but scaled by the non-deductible share instead of the whole cuota.
    """
    fact = _fact(
        category=SpendingCategory.MATERIAL_OFICINA,
        amount=Decimal("1210.00"),
        taxable_base=Decimal("1000.00"),
        iva_amount=Decimal("210.00"),
    )

    result = evaluate_renta_deductibility(
        fact,
        resolve_category_profiles(2025)[SpendingCategory.MATERIAL_OFICINA],
        _context(iva_deduction_ratio=Decimal("0.70")),
    )

    assert result.status is RentaDeductibilityStatus.ELIGIBLE
    # 30% of the 210.00 cuota (63.00) has no right to deduct and joins the cost.
    assert result.deductible_amount == Decimal("1063.00")
    assert result.non_deductible_amount == Decimal("147.00")


def test_full_deduction_right_and_unevaluated_ratio_both_leave_the_base_untouched() -> None:
    """A ratio of 1 (full right to deduct) and the unset default agree with the historic base-only result."""
    fact = _fact(
        category=SpendingCategory.MATERIAL_OFICINA,
        amount=Decimal("1210.00"),
        taxable_base=Decimal("1000.00"),
        iva_amount=Decimal("210.00"),
    )
    profile = resolve_category_profiles(2025)[SpendingCategory.MATERIAL_OFICINA]

    full_right = evaluate_renta_deductibility(fact, profile, _context(iva_deduction_ratio=Decimal("1")))
    unevaluated = evaluate_renta_deductibility(fact, profile, _context())

    assert full_right.deductible_amount == Decimal("1000.00")
    assert unevaluated.deductible_amount == Decimal("1000.00")


def test_iva_deduction_ratio_is_inert_without_an_invoice_evidenced_base_split() -> None:
    """A fact with no ``taxable_base``/``iva_amount`` split is unaffected by the ratio.

    ``gross_amount`` is already IVA-inclusive when no invoice evidence split it
    into a net base plus a cuota, so folding in a non-deductible IVA share would
    double-count: there is no separately-known ``iva_amount`` to fold.
    """
    fact = RentaDeductibleExpenseFact(
        transaction_id="a" * 64,
        catalogue_id="ledger-2025",
        operation_date=date(2025, 3, 8),
        posting_date=date(2025, 3, 9),
        gross_amount=Decimal("48.00"),
        category=SpendingCategory.GASTOS_BANCARIOS,
        activity_key="main",
    )
    assert fact.taxable_base is None
    assert fact.iva_amount is None

    result = evaluate_renta_deductibility(
        fact,
        resolve_category_profiles(2025)[SpendingCategory.GASTOS_BANCARIOS],
        _context(iva_deduction_ratio=Decimal("0")),
    )

    assert result.deductible_amount == Decimal("48.00")


def test_arrendamiento_vivienda_afecto_is_ineligible_until_user_ratio_exists() -> None:
    """arrendamiento_vivienda_afecto carries no registry default_ratio.

    It is the renter's parallel to amortizacion / ibi / comunidad
    vivienda_afecto (HOME_OFFICE_OWNERSHIP siblings, none of which carry a
    default_ratio either): the raw affectación ratio must come from the
    operator, at no statutory multiplier, exactly like TELEFONIA_MOVIL below.
    A registry-supplied ``default_ratio = "0.30"`` here used to fabricate a
    30% deduction with zero operator input -- not a legally established
    default, just an arbitrary guess that happened to double as the
    suministros-only art. 30.2.5.b figure this category was wrongly grounded
    on.
    """
    fact = _fact(
        category=SpendingCategory.ARRENDAMIENTO_VIVIENDA_AFECTO,
        amount=Decimal("1000.00"),
        taxable_base=Decimal("979.00"),
        iva_amount=Decimal("21.00"),
    )

    missing = evaluate_renta_deductibility(
        fact,
        resolve_category_profiles(2025)[SpendingCategory.ARRENDAMIENTO_VIVIENDA_AFECTO],
        _context(),
    )
    with_ratio = evaluate_renta_deductibility(
        fact,
        resolve_category_profiles(2025)[SpendingCategory.ARRENDAMIENTO_VIVIENDA_AFECTO],
        _context(usage_ratios={SpendingCategory.ARRENDAMIENTO_VIVIENDA_AFECTO: Decimal("0.30")}),
    )

    assert missing.status is RentaDeductibilityStatus.INELIGIBLE
    assert missing.reason == "missing usage ratio"
    assert missing.deductible_amount == Decimal("0.00")

    assert with_ratio.status is RentaDeductibilityStatus.ELIGIBLE
    assert with_ratio.applied_ratio == Decimal("0.30")
    assert with_ratio.deductible_amount == Decimal("293.7000")
    assert with_ratio.non_deductible_amount == Decimal("706.3000")


def test_usage_ratio_without_default_is_ineligible_until_user_ratio_exists() -> None:
    fact = _fact(
        category=SpendingCategory.TELEFONIA_MOVIL,
        amount=Decimal("60.00"),
        taxable_base=Decimal("39.00"),
        iva_amount=Decimal("21.00"),
    )

    missing = evaluate_renta_deductibility(
        fact,
        resolve_category_profiles(2025)[SpendingCategory.TELEFONIA_MOVIL],
        _context(),
    )
    with_ratio = evaluate_renta_deductibility(
        fact,
        resolve_category_profiles(2025)[SpendingCategory.TELEFONIA_MOVIL],
        _context(usage_ratios={SpendingCategory.TELEFONIA_MOVIL: Decimal("0.25")}),
    )

    assert missing.status is RentaDeductibilityStatus.INELIGIBLE
    assert missing.reason == "missing usage ratio"
    assert missing.deductible_amount == Decimal("0.00")
    assert with_ratio.status is RentaDeductibilityStatus.ELIGIBLE
    assert with_ratio.deductible_amount == Decimal("9.7500")
    assert with_ratio.non_deductible_amount == Decimal("50.2500")


def test_statutory_annual_cap_limits_health_insurance_amount() -> None:
    fact = _fact(category=SpendingCategory.SEGUROS_SALUD_AUTONOMO, amount=Decimal("800.00"))

    result = evaluate_renta_deductibility(
        fact,
        resolve_category_profiles(2025)[SpendingCategory.SEGUROS_SALUD_AUTONOMO],
        _context(statutory_cap_person_count=1),
    )

    assert result.status is RentaDeductibilityStatus.ELIGIBLE
    # One insured person and nothing declared about discapacidad: the ordinary limb
    # applies, which is what shipped before the higher limb existed. The lawful sum
    # over both limbs is covered in test_seguro_cap_sums_both_limbs.
    assert result.statutory_cap_applied == Decimal("500")
    assert result.deductible_amount == Decimal("500")
    assert result.non_deductible_amount == Decimal("300.00")


def test_daily_statutory_cap_variant_requires_days_and_variant() -> None:
    fact = _fact(category=SpendingCategory.MANUTENCION_DIETAS_NACIONAL, amount=Decimal("80.00"))
    profile = resolve_category_profiles(2025)[SpendingCategory.MANUTENCION_DIETAS_NACIONAL]

    missing = evaluate_renta_deductibility(fact, profile, _context())
    capped = evaluate_renta_deductibility(
        fact,
        profile,
        _context(statutory_cap_days=Decimal("2"), statutory_cap_variant_id="sin-pernocta"),
    )

    assert missing.status is RentaDeductibilityStatus.INELIGIBLE
    assert capped.status is RentaDeductibilityStatus.ELIGIBLE
    assert capped.statutory_cap_applied == Decimal("53.34")
    assert capped.deductible_amount == Decimal("53.34")
    assert capped.non_deductible_amount == Decimal("26.66")


def test_fixed_percentage_profiles_are_supported_by_the_evaluator() -> None:
    fact = _fact(
        category=SpendingCategory.MATERIAL_OFICINA,
        amount=Decimal("200.00"),
        taxable_base=Decimal("179.00"),
        iva_amount=Decimal("21.00"),
    )
    profile = _profile(
        SpendingCategory.MATERIAL_OFICINA,
        ProportionalityRule(
            kind=ProportionalityKind.FIXED_PERCENTAGE,
            fixed_pct=Decimal("0.40"),
            citations=(_citation(),),
            notes=tr("Regla de porcentaje fijo."),
        ),
    )

    result = evaluate_renta_deductibility(fact, profile, _context())

    assert result.status is RentaDeductibilityStatus.ELIGIBLE
    assert result.deductible_amount == Decimal("71.6000")
    assert result.non_deductible_amount == Decimal("128.4000")


def test_non_deductible_profiles_cannot_become_observations() -> None:
    fact = _fact(category=SpendingCategory.MATERIAL_OFICINA, amount=Decimal("200.00"))
    profile = _profile(
        SpendingCategory.MATERIAL_OFICINA,
        ProportionalityRule(
            kind=ProportionalityKind.NON_DEDUCTIBLE,
            citations=(_citation(),),
            notes=tr("Regla no deducible."),
        ),
    )

    result = evaluate_renta_deductibility(fact, profile, _context())

    assert result.status is RentaDeductibilityStatus.INELIGIBLE
    with pytest.raises(ValueError, match="ineligible deductibility result"):
        build_renta_deductible_expense_observation(fact, result, tax_year=2025)


def test_exclusive_use_profiles_require_confirmation() -> None:
    """Confirmation gates deductibility; it does not widen the basis to the gross.

    The fixture's 200.00 gross is a 179.00 base plus 21.00 of input IVA. That
    IVA is recovered as cuota soportada on Modelo 303, so it is not an IRPF
    gasto: the expected 179.00 is the fact's own IVA-exclusive base, which is
    what every sibling proportionality branch deducts. Asserting the gross here
    would claim the 21.00 twice.
    """
    fact = _fact(category=SpendingCategory.MATERIAL_OFICINA, amount=Decimal("200.00"))
    profile = _profile(
        SpendingCategory.MATERIAL_OFICINA,
        ProportionalityRule(
            kind=ProportionalityKind.REQUIRES_EXCLUSIVE_USE,
            citations=(_citation(),),
            notes=tr("Regla que requiere afectacion exclusiva."),
        ),
    )

    missing = evaluate_renta_deductibility(fact, profile, _context())
    confirmed = evaluate_renta_deductibility(fact, profile, _context(exclusive_use_confirmed=True))

    assert missing.status is RentaDeductibilityStatus.INELIGIBLE
    assert confirmed.status is RentaDeductibilityStatus.ELIGIBLE
    assert confirmed.deductible_amount == fact.taxable_base == Decimal("179.00")
    # The 21.00 of input IVA stays out of the gasto rather than vanishing.
    assert confirmed.non_deductible_amount == Decimal("21.00")


def test_first_slice_routes_every_eligible_category_to_a_real_casilla() -> None:
    """Every :class:`SpendingCategory` builds a real observation.

    ``FIRST_SLICE_EXPENSE_CASILLAS`` is a total mapping: no eligible
    deductibility result is rejected for lacking a first-slice
    casilla. This is the closed-gap counterpart of the routing table's
    own ``test_every_spending_category_routes_to_a_first_slice_casilla``:
    it proves the observation-construction boundary (not just the
    routing table) reflects the closed set for a representative
    previously-unrouted amortizable category.
    """
    fact = _fact(category=SpendingCategory.HARDWARE_AMORTIZABLE, amount=Decimal("55.00"))
    result = evaluate_renta_deductibility(
        fact,
        resolve_category_profiles(2025)[SpendingCategory.HARDWARE_AMORTIZABLE],
        _context(),
    )

    observation = build_renta_deductible_expense_observation(fact, result, tax_year=2025)

    assert observation.target_casilla_id == "0208"


def test_tax_year_mismatch_is_rejected_before_observation_creation() -> None:
    fact = _fact(category=SpendingCategory.ASESORIA_FISCAL, amount=Decimal("120.00"))
    result = evaluate_renta_deductibility(
        fact,
        resolve_category_profiles(2025)[SpendingCategory.ASESORIA_FISCAL],
        _context(),
    )

    with pytest.raises(ValueError, match="outside the requested tax year"):
        build_renta_deductible_expense_observation(fact, result, tax_year=2024)


def test_category_normalization_accepts_closed_values_and_rejects_unknowns() -> None:
    assert normalize_spending_category("gastos_bancarios") is SpendingCategory.GASTOS_BANCARIOS
    assert normalize_spending_category(SpendingCategory.GASTOS_BANCARIOS) is SpendingCategory.GASTOS_BANCARIOS
    with pytest.raises(ValueError, match=r"SpendingCategory|not a valid|gastos_sin_catalogo"):
        normalize_spending_category("gastos_sin_catalogo")


def test_fact_model_rejects_boolean_and_float_amounts() -> None:
    payload = _fact(category=SpendingCategory.ASESORIA_CONTABLE).model_dump()
    payload["gross_amount"] = 100.0
    with pytest.raises(ValidationError, match=r"gross_amount|Decimal|decimal"):
        RentaDeductibleExpenseFact.model_validate(payload)


def test_result_model_rejects_mismatched_category_family() -> None:
    fact = _fact(category=SpendingCategory.GASTOS_BANCARIOS)
    result = evaluate_renta_deductibility(
        fact,
        resolve_category_profiles(2025)[SpendingCategory.GASTOS_BANCARIOS],
        _context(),
    )
    payload = result.model_dump()
    payload["category_family"] = SpendingCategoryFamily.PREMISES

    with pytest.raises(ValidationError, match="category_family must match category"):
        type(result).model_validate(payload)


def test_observation_model_rejects_mismatched_first_slice_casilla() -> None:
    fact = _fact(category=SpendingCategory.GASTOS_BANCARIOS)
    result = evaluate_renta_deductibility(
        fact,
        resolve_category_profiles(2025)[SpendingCategory.GASTOS_BANCARIOS],
        _context(),
    )
    observation = build_renta_deductible_expense_observation(fact, result, tax_year=2025)
    payload = observation.model_dump()
    payload["target_casilla_id"] = "0199"

    with pytest.raises(ValidationError, match="target_casilla_id must match"):
        type(observation).model_validate(payload)


def test_observation_model_rejects_legacy_target_casilla_key() -> None:
    fact = _fact(category=SpendingCategory.GASTOS_BANCARIOS)
    result = evaluate_renta_deductibility(
        fact,
        resolve_category_profiles(2025)[SpendingCategory.GASTOS_BANCARIOS],
        _context(),
    )
    observation = build_renta_deductible_expense_observation(fact, result, tax_year=2025)
    payload = observation.model_dump()
    payload["target_casilla"] = payload.pop("target_casilla_id")

    with pytest.raises(ValidationError) as exc_info:
        type(observation).model_validate(payload)

    detail = str(exc_info.value)
    assert "target_casilla_id" in detail
    assert "target_casilla" in detail
