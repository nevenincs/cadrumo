"""Hardening checks for the calc-sheets parity harness."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core import CasillaId, validated_casilla_id
from .....core.config import override_settings
from .....domain.calculations.registry.authority import bundled_authority
from .._engine import build_export_plan
from .._parity_harness import (
    OperatorInputScenario,
    _build_operator_inputs,
    _seed_inputs_into_sheet,
    _sheets_recalc_delay_seconds,
)
from ..errors import CalcSheetsParityError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
_UNKNOWN_SCENARIO_CASILLA: CasillaId = validated_casilla_id(
    "private-casilla-id",
    surface="_UNKNOWN_SCENARIO_CASILLA",
)
_UNKNOWN_EXPECTED_CASILLA: CasillaId = validated_casilla_id(
    "private-expected-casilla-id",
    surface="_UNKNOWN_EXPECTED_CASILLA",
)


def _m130_snapshot():
    return bundled_authority().snapshot("130", filing_year=2025, period="1T", on=date(2025, 4, 1))


def test_recalc_delay_uses_central_settings_override() -> None:
    with override_settings(cadrumo_calc_sheets_recalc_delay_s=0.125):
        assert _sheets_recalc_delay_seconds() == 0.125


def test_unknown_scenario_casilla_ids_do_not_render_raw_values() -> None:
    snapshot = _m130_snapshot()
    sensitive_casilla_id = _UNKNOWN_SCENARIO_CASILLA
    scenario = OperatorInputScenario(inputs_by_casilla_id={sensitive_casilla_id: Decimal("1")})

    with pytest.raises(CalcSheetsParityError) as raised:
        _build_operator_inputs(snapshot, scenario)

    error = raised.value
    assert str(error) == "scenario references unknown casilla ids"
    assert sensitive_casilla_id not in str(error)
    assert sensitive_casilla_id not in str(error.context)
    assert error.context == {"unknown_count": 1, "modelo": "130"}
    assert error.translated_message == "application.storage.calc_sheets.parity.errors.unknown_casilla_ids"


def test_unknown_expected_casilla_ids_fail_before_false_oracle_green() -> None:
    snapshot = _m130_snapshot()
    sensitive_casilla_id = _UNKNOWN_EXPECTED_CASILLA
    scenario = OperatorInputScenario(expected_by_casilla_id={sensitive_casilla_id: Decimal("1")})

    with pytest.raises(CalcSheetsParityError) as raised:
        _build_operator_inputs(snapshot, scenario)

    error = raised.value
    assert str(error) == "scenario references unknown casilla ids"
    assert sensitive_casilla_id not in str(error)
    assert sensitive_casilla_id not in str(error.context)
    assert error.context == {"unknown_count": 1, "modelo": "130"}
    assert error.translated_message == "application.storage.calc_sheets.parity.errors.unknown_casilla_ids"


def test_missing_binding_seed_anchor_is_not_silently_skipped() -> None:
    snapshot = _m130_snapshot()
    plan = build_export_plan(snapshot)
    scenario = OperatorInputScenario(bindings={"private-binding-token": Decimal("1")})

    with pytest.raises(CalcSheetsParityError) as raised:
        _seed_inputs_into_sheet(object(), "spreadsheet-id", plan, scenario, snapshot)

    error = raised.value
    assert str(error) == "parity scenario input has no seed cell"
    assert "private-binding-token" not in str(error)
    assert "private-binding-token" not in str(error.context)
    assert error.context == {"input_kind": "binding"}
    assert error.translated_message == "application.storage.calc_sheets.parity.errors.seed_anchor_missing"
