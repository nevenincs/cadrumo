"""Tests for Modelo 303 compensation relation and calculation behavior."""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.tests import modelo_303_registry_compensation_scenarios as scenarios

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_modelo_303_compensation_chain_uses_current_record_design_casillas() -> None:
    scenarios.check_modelo_303_compensation_chain_uses_current_record_design_casillas()


def test_modelo_303_previous_quarter_compensation_binding_resolves_from_source_casilla_id() -> None:
    scenarios.check_modelo_303_previous_quarter_compensation_binding_resolves_from_source_casilla_id()


def test_modelo_303_first_quarter_compensation_resolves_from_previous_year_fourth_quarter() -> None:
    scenarios.check_modelo_303_first_quarter_compensation_resolves_from_previous_year_fourth_quarter()


def test_modelo_303_compensation_calculation_applies_available_balance_and_carries_remainder() -> None:
    scenarios.check_modelo_303_compensation_calculation_applies_available_balance_and_carries_remainder()
