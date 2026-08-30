"""Reverse-charge and import ledger IVA aggregation binding tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core import IvaDeductionFactKind
from .....core.casilla_id import validated_casilla_id
from ....iva.classification import CustomerTaxStatus, InvoiceKind, IvaInvoiceClassificationCriteria, IvaTerritorialScope, TransactionKind, classify_iva
from ....iva.components import category_cuota_is_zero_by_law
from ....iva.flow import IvaFlowDirection, derive_flow_for_classification
from ....iva.schema import CUOTA_LESS_M303_IVA_CATEGORIES, EUMemberState, IvaCategory, IvaRateKind
from ..ledger_bindings import resolve_ledger_iva_aggregation_binding_values, unsupported_ledger_iva_observations
from ._ledger_iva_aggregation_support import (
    _M303_AUTOREPERCUTIDO_INTRACOMUNITARIA_DEDUCIBLE_CASILLA,
    _M303_AUTOREPERCUTIDO_INTRACOMUNITARIA_DEVENGADO_CASILLA,
    _M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA,
    _M303_CUOTA_DEVENGADA_TOTAL_CASILLA,
    _M303_RESULTADO_REGIMEN_GENERAL_CASILLA,
    _M303_SOPORTADO_IMPORTACIONES_CASILLA,
    _binding,
    _calculate_303_from_observations,
    _modelo_303_revision,
    _observation,
    _revision_with_bindings,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# The official AEAT box numbers this file asserts against, read from the modelo
# 303 diseño de registros: box [11] "Adquisiciones intracomunitarias de bienes y
# servicios - Cuota" on the devengado side, box [37] "En adquisiciones
# intracomunitarias de bienes y servicios corrientes - Cuota" on the deducible
# side. Both titles cover goods AND services; box [13] is "Otras operaciones con
# inversión del sujeto pasivo (excepto. adq. intracom)", which excludes them.
_OFFICIAL_AIC_DEVENGADO_CUOTA_BOX = validated_casilla_id("11")
_OFFICIAL_AIC_DEDUCIBLE_CUOTA_BOX = validated_casilla_id("37")
_OFFICIAL_OTRAS_ISP_DEVENGADO_CUOTA_BOX = validated_casilla_id("13")


def test_resolve_aic_official_box_parity_routes_devengado_and_deducible_net_zero() -> None:
    """AIC official-box parity: boxes 10/11 devengado + 36/37 deducible, net-zero.

    An ``INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE`` observation on the
        ``INVERSION_SUJETO_PASIVO`` flow is consumed by BOTH new official-box parity
    bindings: the devengado parity binding (official boxes 10/11, LIVA art. 13 +
    art. 15 + art. 84.Uno.2) and the deducible parity binding (official boxes
    36/37, + art. 92). Each resolves the same self-assessed cuota, so the pair
    nets to zero — mirroring the autorepercutido-interior pair. A ``SOPORTADO``
    domestic recipient reverse-charge row must NOT leak in (different category).
    """
    revision = _revision_with_bindings(
        _binding("modelo-303-iva-autorepercutido-intracomunitaria-devengado-cuota"),
        _binding("modelo-303-iva-autorepercutido-intracomunitaria-deducible-cuota"),
    )
    observations = [
        _observation(
            applied_rate=Decimal("0.21"),
            ledger_id="aic-isp",
            category=IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
            flow=IvaFlowDirection.INVERSION_SUJETO_PASIVO,
            iva=Decimal("84.00"),
            deduction_fact_kind=IvaDeductionFactKind.INTRA_EU_CURRENT,
        ),
        _observation(
            applied_rate=Decimal("0.21"),
            ledger_id="domestic-isp-stray",
            category=IvaCategory.DOMESTIC_REVERSE_CHARGE,
            flow=IvaFlowDirection.INVERSION_SUJETO_PASIVO,
            iva=Decimal("99.00"),
            deduction_fact_kind=IvaDeductionFactKind.DOMESTIC_CURRENT,
        ),
    ]
    result = resolve_ledger_iva_aggregation_binding_values(revision, observations)
    assert result == {
        "modelo-303-iva-autorepercutido-intracomunitaria-devengado-cuota": Decimal("84.00"),
        "modelo-303-iva-autorepercutido-intracomunitaria-deducible-cuota": Decimal("84.00"),
    }
    devengado = result["modelo-303-iva-autorepercutido-intracomunitaria-devengado-cuota"]
    deducible = result["modelo-303-iva-autorepercutido-intracomunitaria-deducible-cuota"]
    assert devengado - deducible == Decimal("0")


def test_calculate_303_aic_official_box_parity_books_boxes_and_leaves_resultado_unchanged() -> None:
    """End-to-end: an AIC ISP observation books the parity casillas and nets to zero.

    The AIC self-assessed cuota lands on the official-box parity casillas
    (``iva.autorepercutido.intracomunitaria.devengado`` = boxes 10/11,
    ``...deducible`` = boxes 36/37), each echoing the observation's own
    ``iva_amount`` (the binding copies the ledger fact). Because the existing
    ``iva.autorepercutido.intracomunitaria`` semantic casilla already books the
    AIC cuota into the resultado, the parity casillas are NOT in the resultado
    formula — so adding the AIC observation changes the resultado by exactly the
    already-net-zero ISP contribution, i.e. leaves it unchanged versus a filing
    with no AIC. Deltas are computed by comparison, never by summing literals
    (aeat-quality-gates).
    """
    aic_cuota = Decimal("84.00")
    domestic_only = _calculate_303_from_observations(
        filing_year=2025,
        period="1T",
        observations=(
            _observation(
                applied_rate=Decimal("0.21"), ledger_id="sale", txn_date=date(2025, 2, 15), iva=Decimal("21.00")
            ),
        ),
    )
    with_aic = _calculate_303_from_observations(
        filing_year=2025,
        period="1T",
        observations=(
            _observation(
                applied_rate=Decimal("0.21"), ledger_id="sale", txn_date=date(2025, 2, 15), iva=Decimal("21.00")
            ),
            _observation(
                applied_rate=Decimal("0.21"),
                ledger_id="aic-isp",
                txn_date=date(2025, 3, 1),
                category=IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
                flow=IvaFlowDirection.INVERSION_SUJETO_PASIVO,
                iva=aic_cuota,
                deduction_fact_kind=IvaDeductionFactKind.INTRA_EU_CURRENT,
            ),
        ),
    )
    assert with_aic.values[_M303_AUTOREPERCUTIDO_INTRACOMUNITARIA_DEVENGADO_CASILLA] == aic_cuota
    assert with_aic.values[_M303_AUTOREPERCUTIDO_INTRACOMUNITARIA_DEDUCIBLE_CASILLA] == aic_cuota
    # The AIC contribution nets to zero in the resultado (the semantic
    # intracomunitaria casilla feeds both totals equally); the parity casillas
    # are pure official-box exposure, not in the resultado formula.
    assert (
        with_aic.values[_M303_RESULTADO_REGIMEN_GENERAL_CASILLA]
        == domestic_only.values[_M303_RESULTADO_REGIMEN_GENERAL_CASILLA]
    )


def _received_from_eu_criteria(*, kind: TransactionKind) -> IvaInvoiceClassificationCriteria:
    """EU_MEMBER -> ES B2B RECEIVED criteria differing only by supply ``kind``."""
    return IvaInvoiceClassificationCriteria.model_validate(
        {
            "transaction_date": date(2025, 3, 1),
            "issuer_residency": IvaTerritorialScope.EU_MEMBER,
            "issuer_identification_state": EUMemberState.DE,
            "customer_residency": IvaTerritorialScope.ES_MAINLAND,
            "customer_tax_status": CustomerTaxStatus.B2B_IVA_REGISTERED,
            "kind": kind,
            "direction": InvoiceKind.RECEIVED,
            "rate_tier": IvaRateKind.GENERAL,
        },
    )


def test_intracom_goods_and_services_share_the_combined_official_casilla_10_11() -> None:
    """Issue #566: intra-community GOODS and SERVICES share ONE M303 casilla, not two.

    The official AEAT Modelo 303 diseño de registros (``aeat-dr-303-2025``) titles
    boxes 10/11 "Adquisiciones intracomunitarias de bienes y servicios" and boxes
    36/37 "adquisiciones intracomunitarias corrientes" — goods AND services are
    combined by design, not split across distinct boxes. This is the deliberate
    official structure (``modelo-export-mirrors-official-structure``), so the
    classifier collapses both legs onto one category and the aggregation sums them
    into one casilla.

    The two legs carry DISTINCT categories, because Modelo 349 files them under
    distinct claves ("A" for adquisiciones intracomunitarias sujetas, "I" for
    adquisiciones intracomunitarias de servicios). What the combined M303 box
    requires is not one category but one DESTINATION: the classifier keeps the
    legs apart and the aggregation sums them onto the same casilla. Asserting
    they share a category would be asserting the wrong invariant — it held only
    while the services leg was resolved to the goods category, which filed it as
    an adquisición de bienes against VIES.

    Booking one goods leg and one services leg therefore sums BOTH cuotas into
    the single devengado box-10/11 parity casilla (and the box-36/37 deducible
    casilla). The combined value is derived by summing the two input legs (the
    ``op = "sum"`` aggregation contract), never from the registry formula
    (``aeat-quality-gates``). Dropping either category from the
    selectors, or splitting them onto separate casillas, breaks this.
    """
    goods = classify_iva(_received_from_eu_criteria(kind=TransactionKind.GOODS))
    services = classify_iva(_received_from_eu_criteria(kind=TransactionKind.SERVICES_GENERAL))
    assert goods.category is IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE
    assert services.category is IvaCategory.INTRA_COMMUNITY_SERVICE_ACQUISITION_REVERSE_CHARGE
    assert goods.category is not services.category
    assert goods.matched_rule_id == "R11_intra_community_acquisition"
    assert services.matched_rule_id == "R13_services_b2b_eu_inbound"

    goods_cuota = Decimal("63.00")
    services_cuota = Decimal("21.00")
    combined = goods_cuota + services_cuota
    revision = _revision_with_bindings(
        _binding("modelo-303-iva-autorepercutido-intracomunitaria-devengado-cuota"),
        _binding("modelo-303-iva-autorepercutido-intracomunitaria-deducible-cuota"),
    )
    observations = [
        _observation(
            applied_rate=Decimal("0.21"),
            ledger_id="aic-goods-leg",
            category=goods.category,
            flow=IvaFlowDirection.INVERSION_SUJETO_PASIVO,
            iva=goods_cuota,
            deduction_fact_kind=IvaDeductionFactKind.INTRA_EU_CURRENT,
        ),
        _observation(
            applied_rate=Decimal("0.21"),
            ledger_id="aic-services-leg",
            category=services.category,
            flow=IvaFlowDirection.INVERSION_SUJETO_PASIVO,
            iva=services_cuota,
            deduction_fact_kind=IvaDeductionFactKind.INTRA_EU_CURRENT,
        ),
    ]
    result = resolve_ledger_iva_aggregation_binding_values(revision, observations)
    assert result == {
        "modelo-303-iva-autorepercutido-intracomunitaria-devengado-cuota": combined,
        "modelo-303-iva-autorepercutido-intracomunitaria-deducible-cuota": combined,
    }


def test_resolve_import_third_country_routes_deducible_only() -> None:
    """Third-country import deducible routing: box 33, real deduction.

    An ``IMPORT_THIRD_COUNTRY`` observation on the ``SOPORTADO`` flow (the only
    leg that reaches M303 — output IVA is settled at customs/DUA) is consumed by
    the new ``modelo-303-iva-soportado-importaciones-cuota`` binding (official box
    33, LIVA art. 17 hecho imponible + art. 92 cuotas deducibles). Unlike the
    reverse-charge pairs this is NOT net-zero: there is no offsetting devengado
    binding for imports.
    """
    revision = _revision_with_bindings(_binding("modelo-303-iva-soportado-importaciones-cuota"))
    observations = [
        _observation(
            applied_rate=Decimal("0.21"),
            ledger_id="import",
            category=IvaCategory.IMPORT_THIRD_COUNTRY,
            flow=IvaFlowDirection.SOPORTADO,
            iva=Decimal("33.00"),
            deduction_fact_kind=IvaDeductionFactKind.IMPORT_CURRENT,
        ),
    ]
    result = resolve_ledger_iva_aggregation_binding_values(revision, observations)
    assert result == {"modelo-303-iva-soportado-importaciones-cuota": Decimal("33.00")}


def test_calculate_303_import_deducible_reduces_resultado_by_its_cuota() -> None:
    """End-to-end: an import deducible observation lowers the resultado by its cuota.

    The import IVA borne at customs is genuinely deductible (LIVA art. 92), so
    booking an ``IMPORT_THIRD_COUNTRY`` SOPORTADO observation raises the
    cuota-deducible-total by the observation's own ``iva_amount`` and lowers the
    resultado régimen general by the same amount versus a filing without the
    import. Both deltas are computed by comparison, not by summing literals.
    """
    import_cuota = Decimal("33.00")
    without_import = _calculate_303_from_observations(
        filing_year=2025,
        period="1T",
        observations=(
            _observation(
                applied_rate=Decimal("0.21"), ledger_id="sale", txn_date=date(2025, 2, 15), iva=Decimal("210.00")
            ),
        ),
    )
    with_import = _calculate_303_from_observations(
        filing_year=2025,
        period="1T",
        observations=(
            _observation(
                applied_rate=Decimal("0.21"), ledger_id="sale", txn_date=date(2025, 2, 15), iva=Decimal("210.00")
            ),
            _observation(
                applied_rate=Decimal("0.21"),
                ledger_id="import",
                txn_date=date(2025, 3, 1),
                category=IvaCategory.IMPORT_THIRD_COUNTRY,
                flow=IvaFlowDirection.SOPORTADO,
                iva=import_cuota,
                deduction_fact_kind=IvaDeductionFactKind.IMPORT_CURRENT,
            ),
        ),
    )
    assert with_import.values[_M303_SOPORTADO_IMPORTACIONES_CASILLA] == import_cuota
    assert (
        with_import.values[_M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA]
        - without_import.values[_M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA]
        == import_cuota
    )
    assert (
        without_import.values[_M303_RESULTADO_REGIMEN_GENERAL_CASILLA]
        - with_import.values[_M303_RESULTADO_REGIMEN_GENERAL_CASILLA]
        == import_cuota
    )


def test_64_advisory_no_longer_fires_on_aic_or_import() -> None:
    """#64 advisory: the routed AIC + import observations are no longer flagged.

    With the AIC official-box parity bindings and the import deducible binding in
    place, an ``INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE`` ISP observation and an
    ``IMPORT_THIRD_COUNTRY`` SOPORTADO observation are both consumed by a binding,
    so neither appears in the unconsumed-declarable advisory's flagged set.
    """
    revision = _modelo_303_revision()
    aic = _observation(
        applied_rate=Decimal("0.21"),
        ledger_id="aic",
        category=IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
        flow=IvaFlowDirection.INVERSION_SUJETO_PASIVO,
        iva=Decimal("84.00"),
        deduction_fact_kind=IvaDeductionFactKind.INTRA_EU_CURRENT,
    )
    import_row = _observation(
        applied_rate=Decimal("0.21"),
        ledger_id="import",
        category=IvaCategory.IMPORT_THIRD_COUNTRY,
        flow=IvaFlowDirection.SOPORTADO,
        iva=Decimal("33.00"),
        deduction_fact_kind=IvaDeductionFactKind.IMPORT_CURRENT,
    )
    assert unsupported_ledger_iva_observations(revision, (aic, import_row)) == ()


def test_64_advisory_residual_flagged_set_is_empty_for_all_declarable_categories() -> None:
    """#64 advisory residual is empty for every realistically-classifiable category.

    For each declarable :class:`IvaCategory` (excluding the cuota-less-by-law set
    and the non-declarable sentinels) projected on the canonical flow the
    application classifier emits for it (via ``derive_flow_for_classification``,
    with the rate kind that matches the category), no observation lands in the
    unconsumed-declarable advisory's flagged set — the M303 routing tail (reverse-charge
    + AIC parity + import deducible routing) leaves no
    cuota-bearing declarable category unrouted.

    The synthesised observation uses the rate kind the category implies
    (reduced/super-reduced map to their tier; all others to general) and the
    invoice direction the operation occurs under (imports are received; supplies
    and sales are issued), so the projection matches what the live classifier
    would emit rather than an impossible combination.
    """
    revision = _modelo_303_revision()
    non_declarable = {
        IvaCategory.RECARGO_EQUIVALENCIA,
        IvaCategory.UNKNOWN,
        IvaCategory.ERRONEOUS_INVOICE,
    }
    rate_for_category = {
        IvaCategory.DOMESTIC_REDUCED: IvaRateKind.REDUCED,
        IvaCategory.DOMESTIC_SUPER_REDUCED: IvaRateKind.SUPER_REDUCED,
    }
    # The rate each probe row states it carried. Stated rather than inferred from
    # the tier: this sweep is about routing, so the ordinary rate is the truthful
    # one here, and a probe that ever means a transitional rate must say so.
    ordinary_rate_for_tier = {
        IvaRateKind.GENERAL: Decimal("0.21"),
        IvaRateKind.REDUCED: Decimal("0.10"),
        IvaRateKind.SUPER_REDUCED: Decimal("0.04"),
    }
    # Imports are an inbound purchase the operator received; everything else here
    # is an outbound sale/supply the operator issued. This is the realistic
    # invoice direction the live classifier produces per category.
    received_categories = {IvaCategory.IMPORT_THIRD_COUNTRY}
    deduction_kind_by_input_category = {
        IvaCategory.DOMESTIC_REVERSE_CHARGE: IvaDeductionFactKind.DOMESTIC_CURRENT,
        IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE: IvaDeductionFactKind.INTRA_EU_CURRENT,
        IvaCategory.INTRA_COMMUNITY_SERVICE_ACQUISITION_REVERSE_CHARGE: IvaDeductionFactKind.INTRA_EU_CURRENT,
        IvaCategory.IMPORT_THIRD_COUNTRY: IvaDeductionFactKind.IMPORT_CURRENT,
    }

    flagged: list[tuple[str, str]] = []
    for category in IvaCategory:
        if category in non_declarable or category in CUOTA_LESS_M303_IVA_CATEGORIES:
            continue
        invoice_direction = InvoiceKind.RECEIVED if category in received_categories else InvoiceKind.ISSUED
        # Cuota-less-by-law is a (category, SIDE) fact, while
        # CUOTA_LESS_M303_IVA_CATEGORIES is keyed on the category alone, so the
        # skip above cannot express it. Domestic reverse charge forces the
        # distinction: the recipient self-assesses a real cuota, while the
        # supplier repercutes nothing under LIVA art. 84.Uno.2. Synthesising a
        # cuota on the supplier's side builds an operation that cannot exist --
        # the row the ingest guard refuses -- so the advisory would flag an
        # impossible probe rather than an unrouted euro.
        #
        # Flip to the side that bears the cuota rather than dropping the category:
        # skipping it would leave the reverse-charge tail probed on NEITHER side,
        # which is the coverage this module exists to assert.
        if category_cuota_is_zero_by_law(category, invoice_direction):
            invoice_direction = InvoiceKind.RECEIVED if invoice_direction is InvoiceKind.ISSUED else InvoiceKind.ISSUED
            if category_cuota_is_zero_by_law(category, invoice_direction):
                continue
        flow = derive_flow_for_classification(category=category, invoice_direction=invoice_direction)
        probe_tier = rate_for_category.get(category, IvaRateKind.GENERAL)
        observation = _observation(
            ledger_id=f"probe-{category.value}",
            category=category,
            rate_kind=probe_tier,
            applied_rate=ordinary_rate_for_tier[probe_tier],
            flow=flow,
            iva=Decimal("10.00"),
            deduction_fact_kind=deduction_kind_by_input_category.get(category),
        )
        if unsupported_ledger_iva_observations(revision, (observation,)):
            flagged.append((category.value, flow.value))

    assert flagged == [], f"#64 advisory residual must be empty; still flagged: {sorted(flagged)}"


def test_eu_service_acquisition_books_official_boxes_11_and_37_and_nets_to_zero() -> None:
    """An EU services reverse charge lands on official boxes 11/37, netting to zero.

    A Spanish taxpayer buying a B2B service from an EU-established supplier (AWS
    Ireland, a German consultant) self-assesses the cuota: LIVA art. 69.Uno.1.º
    locates the service in the TAI because the recipient is established here, and
    art. 84.Uno.2.a) makes that recipient the sujeto pasivo. AEAT reports the
    resulting cuota on the SAME line as the goods acquisition — the diseño de
    registros titles box [11] "Adquisiciones intracomunitarias de bienes y
    servicios - Cuota" and box [37] "En adquisiciones intracomunitarias de bienes
    y servicios corrientes - Cuota", while box [13] is expressly "excepto. adq.
    intracom". The box numbers asserted here come from that official design, not
    from the bindings under test.

    Both declared figures must be non-zero (booking neither would under-declare on
    the devengada side and over-state nothing on the deducible side, yet leave the
    M349/VIES cross-check unbacked), and the two must cancel so the cash resultado
    is identical to a filing without the EU service. The deltas are computed by
    comparing two calculates, never by summing literals.
    """
    service_cuota = Decimal("21.00")
    sale = _observation(
        applied_rate=Decimal("0.21"), ledger_id="sale", txn_date=date(2025, 2, 15), iva=Decimal("210.00")
    )
    without_service = _calculate_303_from_observations(
        filing_year=2025,
        period="1T",
        observations=(sale,),
    )
    with_service = _calculate_303_from_observations(
        filing_year=2025,
        period="1T",
        observations=(
            sale,
            _observation(
                applied_rate=Decimal("0.21"),
                ledger_id="eu-service",
                txn_date=date(2025, 3, 1),
                category=IvaCategory.INTRA_COMMUNITY_SERVICE_ACQUISITION_REVERSE_CHARGE,
                flow=IvaFlowDirection.INVERSION_SUJETO_PASIVO,
                iva=service_cuota,
                deduction_fact_kind=IvaDeductionFactKind.INTRA_EU_CURRENT,
            ),
        ),
    )

    assert with_service.values[_OFFICIAL_AIC_DEVENGADO_CUOTA_BOX] == service_cuota
    assert with_service.values[_OFFICIAL_AIC_DEDUCIBLE_CUOTA_BOX] == service_cuota
    # Box 13 excludes adquisiciones intracomunitarias, so the service must not
    # leak onto the "otras operaciones con inversión del sujeto pasivo" line.
    assert (
        with_service.values[_OFFICIAL_OTRAS_ISP_DEVENGADO_CUOTA_BOX]
        == without_service.values[_OFFICIAL_OTRAS_ISP_DEVENGADO_CUOTA_BOX]
    )
    # Both declared figures move; only the resultado stays put.
    assert (
        with_service.values[_M303_CUOTA_DEVENGADA_TOTAL_CASILLA]
        - without_service.values[_M303_CUOTA_DEVENGADA_TOTAL_CASILLA]
        == service_cuota
    )
    assert (
        with_service.values[_M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA]
        - without_service.values[_M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA]
        == service_cuota
    )
    assert (
        with_service.values[_M303_RESULTADO_REGIMEN_GENERAL_CASILLA]
        == without_service.values[_M303_RESULTADO_REGIMEN_GENERAL_CASILLA]
    )


def test_eu_service_and_goods_legs_sum_onto_the_one_official_intracom_line() -> None:
    """A goods leg and a services leg add up on the single official box 11/37 line.

    The two legs carry DIFFERENT categories — goods rest on LIVA arts. 13/15,
    services on art. 69.Uno.1.º — but AEAT reports them on one combined line
    ("de bienes y servicios"). Booking one of each must therefore produce the sum
    of the two cuotas on box 11 and on box 37, proving the services leg is neither
    dropped nor split onto a second box. The expected figure is the sum of the two
    input legs (the ``op = "sum"`` aggregation contract), never a value read back
    from the registry formula.
    """
    goods_cuota = Decimal("63.00")
    service_cuota = Decimal("21.00")
    combined = goods_cuota + service_cuota
    result = _calculate_303_from_observations(
        filing_year=2025,
        period="1T",
        observations=(
            _observation(
                applied_rate=Decimal("0.21"), ledger_id="sale", txn_date=date(2025, 2, 15), iva=Decimal("210.00")
            ),
            _observation(
                applied_rate=Decimal("0.21"),
                ledger_id="eu-goods",
                txn_date=date(2025, 3, 1),
                category=IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
                flow=IvaFlowDirection.INVERSION_SUJETO_PASIVO,
                iva=goods_cuota,
                deduction_fact_kind=IvaDeductionFactKind.INTRA_EU_CURRENT,
            ),
            _observation(
                applied_rate=Decimal("0.21"),
                ledger_id="eu-service",
                txn_date=date(2025, 3, 2),
                category=IvaCategory.INTRA_COMMUNITY_SERVICE_ACQUISITION_REVERSE_CHARGE,
                flow=IvaFlowDirection.INVERSION_SUJETO_PASIVO,
                iva=service_cuota,
                deduction_fact_kind=IvaDeductionFactKind.INTRA_EU_CURRENT,
            ),
        ),
    )
    assert result.values[_OFFICIAL_AIC_DEVENGADO_CUOTA_BOX] == combined
    assert result.values[_OFFICIAL_AIC_DEDUCIBLE_CUOTA_BOX] == combined
