"""Activity-asset figures reach consumers from the published authority, worked by hand."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.actividad_asset_bindings import (
    resolve_activity_asset_disposal_bounds,
    resolve_activity_asset_schedule_authority,
)
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.ledger_renta_gastos_estimacion_directa_bindings import (
    activity_asset_amortization_casillas,
)
from cadrumo.domain.calculations.registry.ledger_renta_gastos_pago_fraccionado_bindings import (
    renta_gastos_pago_fraccionado_target_casilla,
)
from cadrumo.domain.calculations.registry.ledger_renta_income_bindings import renta_income_target_casilla
from cadrumo.domain.renta.actividad_asset.disposal import (
    ActivityAssetDisposal,
    ActivityAssetDisposalFacts,
    ActivityAssetDisposalReason,
    calculate_disposal,
)
from cadrumo.domain.renta.actividad_asset.lifecycle import AssetKind

from .test_activity_asset_schedule_authority_resolution import _GROWING, _asset, _employment, _linear

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_the_published_2025_edition_supplies_the_boxes_and_the_workforce_cap() -> None:
    with bundled_indexed_authority().operation() as operation:
        modelo_100 = operation.revision_for_context("100", filing_year=2025, period="0A")
        modelo_130 = operation.revision_for_context("130", filing_year=2025, period="1T")
        boxes = activity_asset_amortization_casillas(modelo_100)
        amortization_box = renta_gastos_pago_fraccionado_target_casilla(modelo_130, modelo="130")
        income_box = renta_income_target_casilla(modelo_130, modelo="130")
        authority = resolve_activity_asset_schedule_authority(
            modelo_100,
            tax_year=2025,
            asset_revision=_asset(_employment(), basis="200000", in_service=date(2025, 3, 1)),
            authority_generation=operation.pin().logical_generation,
            workforce=_GROWING,
            legal_reference=operation.legal_reference,
        )

    assert boxes == {AssetKind.MATERIAL: "0208", AssetKind.INTANGIBLE: "0227"}
    assert (amortization_box, income_box) == ("02", "01")
    # 12 months before: 10.00. 24 months after: (12 + 13) / 2 = 12.50. Increase 2.50; 120,000 x 2.50.
    assert authority.free_depreciation_investment_cap == Decimal("300000.00")


@pytest.mark.parametrize(
    ("later_affectation_on", "route_changed"),
    [(date(2022, 7, 1), True), (date(2022, 6, 30), False)],
)
def test_the_published_period_decides_a_sale_after_a_later_affectation(
    later_affectation_on: date,
    route_changed: bool,
) -> None:
    with bundled_indexed_authority().operation() as operation:
        bounds = resolve_activity_asset_disposal_bounds(
            operation.revision_for_context("100", filing_year=2025, period="0A"),
            tax_year=2025,
            asset_revision=_asset(_linear("maquinaria"), basis="1000"),
        )

    # Three years from the affectation end on the same day of 2025: the sale of 30 June 2025 is within
    # a period that began on 1 July 2022 and past one that ran out on 30 June 2025.
    assert bounds.later_affectation_period_years == 3
    calculation = calculate_disposal(
        ActivityAssetDisposalFacts(
            disposal=ActivityAssetDisposal(
                disposal_date=date(2025, 6, 30),
                reason=ActivityAssetDisposalReason.SALE,
                proceeds=Decimal("1.00"),
                transmission_costs=Decimal("0.00"),
                later_affectation_on=later_affectation_on,
            ),
            acquisition_value=Decimal("1000.00"),
            allocation_share=Decimal("1"),
            amortizable_value=Decimal("1000.00"),
            opening_amount=Decimal("0"),
            years=(),
            later_affectation_period_years=bounds.later_affectation_period_years,
        )
    )
    assert calculation.route_changed_by_later_affectation is route_changed
