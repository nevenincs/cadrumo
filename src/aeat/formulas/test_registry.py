"""Tests for :class:`RulesetRegistry`."""

from __future__ import annotations

from datetime import date

import pytest

from ..errors import (
    MissingRulesetError,
    RulesetValidationError,
)
from ..models import ModeloCode
from ._codes import Quarter
from ._period import FiscalPeriod
from ._registry import RulesetRegistry, get_registry
from ._rulesets.modelo_130_2024 import RULESET as MODELO_130_2024
from ._rulesets.modelo_130_2025 import RULESET as MODELO_130_2025

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]


@pytest.mark.unit
def test_registry_ships_modelo_130_and_303_rulesets() -> None:
    """The registry contains every shipped ruleset.

    Wave 1 (#173) added the Modelo 130 2024+2025 pair; wave 2
    (#183) added the Modelo 303 2024+2025 pair. EPIC #305 wave 28
    extends the fleet with the Modelo 115 2025 ruleset.
    """
    registry = get_registry()
    ids = sorted(r.ruleset_id for r in registry.rulesets)
    assert ids == [
        "modelo_100.summary.2025",
        "modelo_111.2025",
        "modelo_115.2025",
        "modelo_123.2025",
        "modelo_130.2024",
        "modelo_130.2025",
        "modelo_202.2025",
        "modelo_303.2024",
        "modelo_303.2025",
    ]


@pytest.mark.unit
def test_resolve_returns_2024_for_q2() -> None:
    """Resolution binds a 2024 period to the 2024 ruleset."""
    registry = get_registry()
    ruleset = registry.resolve(
        modelo=ModeloCode.MODELO_130,
        period=FiscalPeriod(year=2024, quarter=Quarter.Q2),
    )
    assert ruleset is MODELO_130_2024


@pytest.mark.unit
def test_resolve_returns_2025_for_q4() -> None:
    """Resolution binds a 2025 period to the 2025 ruleset."""
    registry = get_registry()
    ruleset = registry.resolve(
        modelo=ModeloCode.MODELO_130,
        period=FiscalPeriod(year=2025, quarter=Quarter.Q4),
    )
    assert ruleset is MODELO_130_2025


@pytest.mark.unit
def test_resolve_missing_ruleset() -> None:
    """Unknown modelo / period combos raise MissingRulesetError."""
    registry = get_registry()
    with pytest.raises(MissingRulesetError):
        registry.resolve(
            modelo=ModeloCode.MODELO_130,
            period=FiscalPeriod(year=2023, quarter=Quarter.Q1),
        )


@pytest.mark.unit
def test_overlapping_rulesets_rejected() -> None:
    """Registry assembly rejects overlapping spans for the same modelo."""
    with pytest.raises(RulesetValidationError):
        RulesetRegistry(rulesets=(MODELO_130_2024, MODELO_130_2024))


@pytest.mark.unit
def test_resolve_binds_to_authoritative_modelo_code() -> None:
    """The registry uses ``aeat.models.ModeloCode`` (not the casillas enum)."""
    registry = get_registry()
    for ruleset in registry.rulesets:
        assert isinstance(ruleset.modelo, ModeloCode)


@pytest.mark.unit
def test_resolve_for_year_only_period() -> None:
    """A year-only period is accepted when the ruleset covers the full year."""
    registry = get_registry()
    ruleset = registry.resolve(
        modelo=ModeloCode.MODELO_130,
        period=FiscalPeriod(year=2024),
    )
    assert ruleset is MODELO_130_2024


@pytest.mark.unit
def test_registry_resolution_consistent_with_effective_dates() -> None:
    """Every ruleset's effective_from must fall inside the registered span."""
    registry = get_registry()
    for ruleset in registry.rulesets:
        assert ruleset.effective_from <= (ruleset.effective_to or date(2100, 12, 31))
