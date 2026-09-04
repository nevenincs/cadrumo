"""Legal-entity calendar coverage for the overview application facade."""

from __future__ import annotations

from datetime import date

import pytest

from ....domain.deadlines.models import IVARegime, TaxpayerProfile
from ....domain.contribuyente.entity_type import EntityType
from ..calendar import build_overview_calendar
from ..calendar_models import OverviewCalendarRange

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _legal_entity() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="B12345674",
        entity_type=EntityType.LEGAL_ENTITY,
        iva_regime=IVARegime.GENERAL,
        has_employees=False,
        pays_professionals_with_retencion=False,
        professional_income_withholding_ge_70pct=False,
        art109_activity_income_withholding_ge_70pct=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        third_party_transactions_above_347_threshold=False,
        bienes_extranjero_above_threshold=False,
    )


def test_calendar_legal_entity_shows_modelo_202_pagos_fraccionados() -> None:
    rng = OverviewCalendarRange(from_date=date(2025, 1, 1), to_date=date(2025, 12, 31))
    cal = build_overview_calendar(_legal_entity(), rng, today=date(2025, 4, 1))

    surfaced = {entry.modelo for entry in cal.entries}
    assert "202" in surfaced, (
        "M202 (pago fraccionado IS) must appear for a LEGAL_ENTITY profile; "
        "absent means filing-schedule profile-condition cannot resolve taxpayer.entity_type"
    )
    assert cal.taxpayer_model_declared is True


def test_calendar_legal_entity_shows_modelo_200_impuesto_sociedades() -> None:
    rng = OverviewCalendarRange(from_date=date(2025, 1, 1), to_date=date(2025, 12, 31))
    cal = build_overview_calendar(_legal_entity(), rng, today=date(2025, 4, 1))

    surfaced = {entry.modelo for entry in cal.entries}
    assert "200" in surfaced, (
        "M200 (IS annual) must appear for a LEGAL_ENTITY profile querying 2025; "
        "absent means covered_years() did not include prior fiscal year 2024"
    )
