"""Tests for Modelo 303 monthly snapshots and filing-schedule applicability."""

from __future__ import annotations

import pytest

from . import modelo_303_registry_schedules_scenarios as scenarios

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("operation")]


def test_modelo_303_monthly_snapshot_resolves_for_each_period() -> None:
    scenarios.check_modelo_303_monthly_snapshot_resolves_for_each_period()


def test_modelo_303_monthly_filing_schedule_matches_monthly_liquidation_profiles() -> None:
    scenarios.check_modelo_303_monthly_filing_schedule_matches_monthly_liquidation_profiles()
