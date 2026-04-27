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
from ._rulesets.modelo_111_2024 import RULESET as MODELO_111_2024
from ._rulesets.modelo_111_2025 import RULESET as MODELO_111_2025
from ._rulesets.modelo_115_2024 import RULESET as MODELO_115_2024
from ._rulesets.modelo_115_2025 import RULESET as MODELO_115_2025
from ._rulesets.modelo_123_2024 import RULESET as MODELO_123_2024
from ._rulesets.modelo_123_2025 import RULESET as MODELO_123_2025
from ._rulesets.modelo_130_2024 import RULESET as MODELO_130_2024
from ._rulesets.modelo_130_2025 import RULESET as MODELO_130_2025
from ._rulesets.modelo_131_2024 import RULESET as MODELO_131_2024
from ._rulesets.modelo_131_2025 import RULESET as MODELO_131_2025
from ._rulesets.modelo_180_2024 import RULESET as MODELO_180_2024
from ._rulesets.modelo_180_2025 import RULESET as MODELO_180_2025

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
        "modelo_111.2024",
        "modelo_111.2025",
        "modelo_115.2024",
        "modelo_115.2025",
        "modelo_123.2024",
        "modelo_123.2025",
        "modelo_130.2024",
        "modelo_130.2025",
        "modelo_130.2026",
        "modelo_131.2024",
        "modelo_131.2025",
        "modelo_180.2024",
        "modelo_180.2025",
        "modelo_200.2024",
        "modelo_202.2025",
        "modelo_303.2024",
        "modelo_303.2025",
        "modelo_303.2026",
        "modelo_390.2025",
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
def test_resolve_115_backfill_binds_2024() -> None:
    """Wave 43: Modelo 115 2024 backfill resolves for 2024-Q4 complementarias."""
    registry = get_registry()
    ruleset_2024 = registry.resolve(
        modelo=ModeloCode.MODELO_115,
        period=FiscalPeriod(year=2024, quarter=Quarter.Q4),
    )
    ruleset_2025 = registry.resolve(
        modelo=ModeloCode.MODELO_115,
        period=FiscalPeriod(year=2025, quarter=Quarter.Q1),
    )
    assert ruleset_2024 is MODELO_115_2024
    assert ruleset_2025 is MODELO_115_2025


@pytest.mark.unit
def test_resolve_180_backfill_binds_2024() -> None:
    """Wave 43: Modelo 180 2024 backfill resolves for ejercicio-2024 annual filings."""
    registry = get_registry()
    # Annual filings use quarter=None (a FiscalPeriod with only a year).
    ruleset_2024 = registry.resolve(
        modelo=ModeloCode.MODELO_180,
        period=FiscalPeriod(year=2024),
    )
    ruleset_2025 = registry.resolve(
        modelo=ModeloCode.MODELO_180,
        period=FiscalPeriod(year=2025),
    )
    assert ruleset_2024 is MODELO_180_2024
    assert ruleset_2025 is MODELO_180_2025


@pytest.mark.unit
def test_resolve_111_backfill_binds_2024() -> None:
    """Wave 44/45: Modelo 111 2024 backfill resolves for 2024-period complementarias."""
    registry = get_registry()
    ruleset_2024 = registry.resolve(
        modelo=ModeloCode.MODELO_111,
        period=FiscalPeriod(year=2024, quarter=Quarter.Q3),
    )
    ruleset_2025 = registry.resolve(
        modelo=ModeloCode.MODELO_111,
        period=FiscalPeriod(year=2025, quarter=Quarter.Q1),
    )
    assert ruleset_2024 is MODELO_111_2024
    assert ruleset_2025 is MODELO_111_2025


@pytest.mark.unit
def test_resolve_123_backfill_binds_2024() -> None:
    """Wave 44/45: Modelo 123 2024 backfill resolves for 2024-period filings."""
    registry = get_registry()
    ruleset_2024 = registry.resolve(
        modelo=ModeloCode.MODELO_123,
        period=FiscalPeriod(year=2024, quarter=Quarter.Q2),
    )
    ruleset_2025 = registry.resolve(
        modelo=ModeloCode.MODELO_123,
        period=FiscalPeriod(year=2025, quarter=Quarter.Q2),
    )
    assert ruleset_2024 is MODELO_123_2024
    assert ruleset_2025 is MODELO_123_2025


@pytest.mark.unit
def test_resolve_modelo_100_summary_via_variant() -> None:
    """Wave 47: Modelo 100 summary ruleset is reachable via variant="summary"."""
    from ._rulesets.modelo_100_summary_2025 import (
        RULESET as MODELO_100_SUMMARY_2025,
    )

    registry = get_registry()
    ruleset = registry.resolve(
        modelo=ModeloCode.MODELO_100,
        period=FiscalPeriod(year=2025),
        variant="summary",
    )
    assert ruleset is MODELO_100_SUMMARY_2025


@pytest.mark.unit
def test_resolve_default_variant_misses_summary() -> None:
    """Wave 47: default variant does NOT resolve the summary-only ruleset.

    Absent a canonical (default-variant) Modelo 100 ruleset, resolving
    without specifying ``variant`` must raise. This proves the axis
    actually partitions the registry — otherwise the summary ruleset
    would leak through default-variant lookups.
    """
    registry = get_registry()
    with pytest.raises(MissingRulesetError):
        registry.resolve(
            modelo=ModeloCode.MODELO_100,
            period=FiscalPeriod(year=2025),
        )


@pytest.mark.unit
def test_resolve_131_backfill_binds_2024() -> None:
    """Wave 44/45: Modelo 131 2024 backfill resolves for 2024-period módulos filings."""
    registry = get_registry()
    ruleset_2024 = registry.resolve(
        modelo=ModeloCode.MODELO_131,
        period=FiscalPeriod(year=2024, quarter=Quarter.Q1),
    )
    ruleset_2025 = registry.resolve(
        modelo=ModeloCode.MODELO_131,
        period=FiscalPeriod(year=2025, quarter=Quarter.Q1),
    )
    assert ruleset_2024 is MODELO_131_2024
    assert ruleset_2025 is MODELO_131_2025


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
