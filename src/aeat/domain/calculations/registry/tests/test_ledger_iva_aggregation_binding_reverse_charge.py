"""Reverse-charge and import ledger IVA aggregation binding tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....iva import (
    CUOTA_LESS_M303_IVA_CATEGORIES,
    InvoiceKind,
    IvaCategory,
    IvaFlowDirection,
    IvaRateKind,
    derive_flow_for_classification,
)
from .. import (
    resolve_ledger_iva_aggregation_binding_values,
    unsupported_ledger_iva_observations,
)
from ._ledger_iva_aggregation_support import (
    _M303_AUTOREPERCUTIDO_INTRACOMUNITARIA_DEDUCIBLE_CASILLA,
    _M303_AUTOREPERCUTIDO_INTRACOMUNITARIA_DEVENGADO_CASILLA,
    _M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA,
    _M303_RESULTADO_REGIMEN_GENERAL_CASILLA,
    _M303_SOPORTADO_IMPORTACIONES_CASILLA,
    _binding,
    _calculate_303_from_observations,
    _modelo_303_revision,
    _observation,
    _revision_with_bindings,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_resolve_aic_official_box_parity_routes_devengado_and_deducible_net_zero() -> None:
    """AIC official-box parity: boxes 10/11 devengado + 36/37 deducible, net-zero.

    An ``INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE`` observation on the
    ``INVERSION_SUJETO_PASIVO`` flow is consumed by BOTH new official-box parity
    bindings: the devengado parity binding (official boxes 10/11, LIVA art. 13 +
    art. 15 + art. 84.Uno.2) and the deducible parity binding (official boxes
    36/37, + art. 92). Each resolves the same self-assessed cuota, so the pair
    nets to zero — mirroring the autorepercutido-interior pair. A ``SOPORTADO``
    row on the same category must NOT leak in (different flow).
    """
    revision = _revision_with_bindings(
        _binding("modelo-303-iva-autorepercutido-intracomunitaria-devengado-cuota"),
        _binding("modelo-303-iva-autorepercutido-intracomunitaria-deducible-cuota"),
    )
    observations = [
        _observation(
            ledger_id="aic-isp",
            category=IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
            flow=IvaFlowDirection.INVERSION_SUJETO_PASIVO,
            iva=Decimal("84.00"),
        ),
        _observation(
            ledger_id="aic-stray-soportado",
            category=IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
            flow=IvaFlowDirection.SOPORTADO,
            iva=Decimal("99.00"),
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
    (no-tautological-calculation-tests).
    """
    aic_cuota = Decimal("84.00")
    domestic_only = _calculate_303_from_observations(
        filing_year=2025,
        period="1T",
        observations=(_observation(ledger_id="sale", txn_date=date(2025, 2, 15), iva=Decimal("21.00")),),
    )
    with_aic = _calculate_303_from_observations(
        filing_year=2025,
        period="1T",
        observations=(
            _observation(ledger_id="sale", txn_date=date(2025, 2, 15), iva=Decimal("21.00")),
            _observation(
                ledger_id="aic-isp",
                txn_date=date(2025, 3, 1),
                category=IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
                flow=IvaFlowDirection.INVERSION_SUJETO_PASIVO,
                iva=aic_cuota,
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
            ledger_id="import",
            category=IvaCategory.IMPORT_THIRD_COUNTRY,
            flow=IvaFlowDirection.SOPORTADO,
            iva=Decimal("33.00"),
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
        observations=(_observation(ledger_id="sale", txn_date=date(2025, 2, 15), iva=Decimal("210.00")),),
    )
    with_import = _calculate_303_from_observations(
        filing_year=2025,
        period="1T",
        observations=(
            _observation(ledger_id="sale", txn_date=date(2025, 2, 15), iva=Decimal("210.00")),
            _observation(
                ledger_id="import",
                txn_date=date(2025, 3, 1),
                category=IvaCategory.IMPORT_THIRD_COUNTRY,
                flow=IvaFlowDirection.SOPORTADO,
                iva=import_cuota,
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
        ledger_id="aic",
        category=IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
        flow=IvaFlowDirection.INVERSION_SUJETO_PASIVO,
        iva=Decimal("84.00"),
    )
    import_row = _observation(
        ledger_id="import",
        category=IvaCategory.IMPORT_THIRD_COUNTRY,
        flow=IvaFlowDirection.SOPORTADO,
        iva=Decimal("33.00"),
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
        IvaCategory.DOMESTIC_REDUCED_10: IvaRateKind.REDUCED,
        IvaCategory.DOMESTIC_SUPER_REDUCED_4: IvaRateKind.SUPER_REDUCED,
    }
    # Imports are an inbound purchase the operator received; everything else here
    # is an outbound sale/supply the operator issued. This is the realistic
    # invoice direction the live classifier produces per category.
    received_categories = {IvaCategory.IMPORT_THIRD_COUNTRY}

    flagged: list[tuple[str, str]] = []
    for category in IvaCategory:
        if category in non_declarable or category in CUOTA_LESS_M303_IVA_CATEGORIES:
            continue
        invoice_direction = InvoiceKind.RECEIVED if category in received_categories else InvoiceKind.ISSUED
        flow = derive_flow_for_classification(category=category, invoice_direction=invoice_direction)
        observation = _observation(
            ledger_id=f"probe-{category.value}",
            category=category,
            rate_kind=rate_for_category.get(category, IvaRateKind.GENERAL),
            flow=flow,
            iva=Decimal("10.00"),
        )
        if unsupported_ledger_iva_observations(revision, (observation,)):
            flagged.append((category.value, flow.value))

    assert flagged == [], f"#64 advisory residual must be empty; still flagged: {sorted(flagged)}"
