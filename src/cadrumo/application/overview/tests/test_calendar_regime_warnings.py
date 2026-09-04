"""Overview calendar regime-warning behaviour."""

from __future__ import annotations

from datetime import date

import pytest

from ....domain.deadlines.models import IrpfEstimationRegime, IrpfIncomeCategory, IVARegime, TaxpayerProfile
from ....domain.contribuyente.entity_type import EntityType
from ..calendar import build_overview_calendar
from ..calendar_models import OverviewCalendarRange

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _autonomo(*, iva_regime: IVARegime) -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="X1234567L",
        entity_type=EntityType.NATURAL_PERSON,
        irpf_income_categories=frozenset({IrpfIncomeCategory.ACTIVIDAD_ECONOMICA}),
        irpf_estimation_regime=IrpfEstimationRegime.DIRECTA_NORMAL,
        iva_regime=iva_regime,
        has_employees=False,
        pays_professionals_with_retencion=False,
        art109_activity_income_withholding_ge_70pct=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        third_party_transactions_above_347_threshold=False,
        bienes_extranjero_above_threshold=False,
    )


def test_calendar_warns_when_m303_simplificado_forfait_engine_is_unavailable() -> None:
    """A SIMPLIFICADO profile must not receive a silent general-regime M303 row."""
    rng = OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 4, 20))

    cal = build_overview_calendar(_autonomo(iva_regime=IVARegime.SIMPLIFICADO), rng, today=date(2026, 4, 1))

    assert any(entry.modelo == "303" for entry in cal.entries)
    warnings = [w for w in cal.warnings if w.code == "iva.regime.m303_simplificado_forfait_unavailable"]
    assert len(warnings) == 1
    warning = warnings[0]
    assert warning.affected_modelos == ("303",)
    assert warning.fix_action.action.action_id == "operator.modelo.describe"
    assert {binding.argument_name: binding.value for binding in warning.fix_action.argument_bindings} == {
        "modelo": "303"
    }


def test_calendar_does_not_emit_simplificado_forfait_warning_for_general_regime() -> None:
    """GENERAL-regime M303 rows do not carry the SIMPLIFICADO forfait warning."""
    rng = OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 4, 20))

    cal = build_overview_calendar(_autonomo(iva_regime=IVARegime.GENERAL), rng, today=date(2026, 4, 1))

    assert any(entry.modelo == "303" for entry in cal.entries)
    assert "iva.regime.m303_simplificado_forfait_unavailable" not in {w.code for w in cal.warnings}
