"""Legal-entity calendar coverage for the overview application facade."""

from __future__ import annotations

from datetime import date

import pytest

from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.contribuyente.entity_type import EntityType
from ....domain.contribuyente.renta_codes import FiscalResidency
from ....domain.deadlines.models import IVARegime, ModeloEnrollment, TaxpayerProfile
from ..calendar import build_overview_calendar
from ..calendar_models import OverviewCalendarRange

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_YEAR = filing_year_envelope().horizon


def _legal_entity() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="B00015016",
        entity_type=EntityType.from_registry("legal_entity"),
        iva_regime=IVARegime("GENERAL"),
        has_employees=False,
        pays_professionals_with_retencion=False,
        art109_activity_income_withholding_ge_70pct=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        third_party_transactions_above_347_threshold=False,
        bienes_extranjero_above_threshold=False,
        fiscal_residency=FiscalResidency.from_registry("resident_irpf"),
        enrollment=ModeloEnrollment(large_company=False),
    )


def test_calendar_legal_entity_shows_modelo_202_pagos_fraccionados(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    rng = OverviewCalendarRange(from_date=date(_YEAR, 1, 1), to_date=date(_YEAR, 12, 31))
    cal = build_overview_calendar(_legal_entity(), rng, operation=authority_operation, today=date(_YEAR, 4, 1))

    surfaced = {entry.modelo for entry in cal.entries}
    assert "202" in surfaced, (
        "M202 (pago fraccionado IS) must appear for a LEGAL_ENTITY profile; "
        "absent means filing-schedule profile-condition cannot resolve taxpayer.entity_type"
    )
    assert cal.taxpayer_model_declared is True


def test_calendar_legal_entity_shows_modelo_200_impuesto_sociedades(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    rng = OverviewCalendarRange(from_date=date(_YEAR, 1, 1), to_date=date(_YEAR, 12, 31))
    cal = build_overview_calendar(_legal_entity(), rng, operation=authority_operation, today=date(_YEAR, 4, 1))

    surfaced = {entry.modelo for entry in cal.entries}
    assert "200" in surfaced, (
        "M200 (IS annual) must appear for a LEGAL_ENTITY profile querying its filing year; "
        "absent means covered_years() did not include the prior fiscal year"
    )
