"""Hardening checks for the calc-sheets parity harness."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core.config import override_settings
from .....core.resources import resources
from .._engine import build_export_plan
from .._errors import CalcSheetsParityError
from .._parity_harness import (
    OperatorInputScenario,
    _build_operator_inputs,
    _seed_inputs_into_sheet,
    _sheets_recalc_delay_seconds,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _m130_snapshot():
    return resources().modelos.authority.snapshot("130", filing_year=2025, period="1T", on=date(2025, 4, 1))


def test_recalc_delay_uses_central_settings_override() -> None:
    with override_settings(aeat_calc_sheets_recalc_delay_s=0.125):
        assert _sheets_recalc_delay_seconds() == 0.125


def test_unknown_scenario_casilla_numbers_do_not_render_raw_values() -> None:
    snapshot = _m130_snapshot()
    sensitive_number = "private-casilla-number"
    scenario = OperatorInputScenario(inputs_by_number={sensitive_number: Decimal("1")})

    with pytest.raises(CalcSheetsParityError) as raised:
        _build_operator_inputs(snapshot, scenario)

    error = raised.value
    assert str(error) == "scenario references unknown casilla numbers"
    assert sensitive_number not in str(error)
    assert sensitive_number not in str(error.context)
    assert error.context == {"unknown_count": 1, "modelo": "130"}
    assert error.translated_message == "application.storage.calc_sheets.parity.errors.unknown_casilla_numbers"


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
