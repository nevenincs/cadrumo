"""Tests for Modelo 303 monthly snapshots and filing-schedule applicability."""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.tests import modelo_303_registry_schedules_scenarios as scenarios

from .modelo_303_registry_support import load_modelo_303

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("governed_fact_scope")]


def test_modelo_303_monthly_snapshot_resolves_for_each_period() -> None:
    scenarios.check_modelo_303_monthly_snapshot_resolves_for_each_period(load_modelo_303)


def test_modelo_303_monthly_filing_schedule_matches_monthly_liquidation_profiles() -> None:
    scenarios.check_modelo_303_monthly_filing_schedule_matches_monthly_liquidation_profiles(load_modelo_303)
