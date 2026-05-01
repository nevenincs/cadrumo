"""Tests for :class:`RulesetRegistry`."""

from __future__ import annotations

from datetime import date

import pytest

from ...core.errors import (
    MissingRulesetError,
    RulesetValidationError,
)
from ..modelos import ModeloCode
from ._codes import Quarter
from ._period import FiscalPeriod
from ._registry import RulesetRegistry, get_registry
from ._rulesets.modelo_111_2024 import RULESET as MODELO_111_2024
from ._rulesets.modelo_111_2025 import RULESET as MODELO_111_2025
from ._rulesets.modelo_115_2024 import RULESET as MODELO_115_2024
from ._rulesets.modelo_115_2025 import RULESET as MODELO_115_2025
from ._rulesets.modelo_123_2024 import RULESET as MODELO_123_2024
from ._rulesets.modelo_123_2025 import RULESET as MODELO_123_2025
from ._rulesets.modelo_123_2026 import RULESET as MODELO_123_2026
from ._rulesets.modelo_130_2024 import RULESET as MODELO_130_2024
from ._rulesets.modelo_130_2025 import RULESET as MODELO_130_2025
from ._rulesets.modelo_131_2024 import RULESET as MODELO_131_2024
from ._rulesets.modelo_131_2025 import RULESET as MODELO_131_2025
from ._rulesets.modelo_131_2026 import RULESET as MODELO_131_2026
from ._rulesets.modelo_180_2024 import RULESET as MODELO_180_2024
from ._rulesets.modelo_180_2025 import RULESET as MODELO_180_2025
from ._rulesets.modelo_180_2026 import RULESET as MODELO_180_2026
from ._rulesets.modelo_200_2024 import RULESET as MODELO_200_2024
from ._rulesets.modelo_200_2025 import RULESET as MODELO_200_2025
from ._rulesets.modelo_200_2026 import RULESET as MODELO_200_2026

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


@pytest.mark.unit
def test_registry_ships_modelo_130_and_303_rulesets() -> None:
    """The registry contains every shipped ruleset.

     (#173) added the Modelo 130 2024+2025 pair;
    (#183) added the Modelo 303 2024+2025 pair. EPIC #305
    extends the fleet with the Modelo 115 2025 ruleset.
    """
    registry = get_registry()
    ids = sorted(r.ruleset_id for r in registry.rulesets)
    assert ids == [
        "modelo_100.2024",
        "modelo_100.2025",
        "modelo_100.2026",
        "modelo_100.summary.2025",
        "modelo_111.2024",
        "modelo_111.2025",
        "modelo_111.2026",
        "modelo_115.2024",
        "modelo_115.2025",
        "modelo_115.2026",
        "modelo_123.2024",
        "modelo_123.2025",
        "modelo_123.2026",
        "modelo_130.2024",
        "modelo_130.2025",
        "modelo_130.2026",
        "modelo_131.2024",
        "modelo_131.2025",
        "modelo_131.2026",
        "modelo_180.2024",
        "modelo_180.2025",
        "modelo_180.2026",
        "modelo_200.2024",
        "modelo_200.2025",
        "modelo_200.2026",
        "modelo_202.2025",
        "modelo_303.2024",
        "modelo_303.2025",
        "modelo_303.2026",
        "modelo_390.2024",
        "modelo_390.2025",
        "modelo_390.2026",
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
    """Modelo 115 2024 backfill resolves for 2024-Q4 complementarias."""
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
    """Modelo 180 2024 backfill resolves for ejercicio-2024 annual filings."""
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
def test_resolve_180_binds_2026() -> None:
    """Issue #323: Modelo 180 resolves for 2026 annual filings."""
    registry = get_registry()
    ruleset = registry.resolve(
        modelo=ModeloCode.MODELO_180,
        period=FiscalPeriod(year=2026),
    )
    assert ruleset is MODELO_180_2026


@pytest.mark.unit
def test_resolve_200_binds_each_annual_year() -> None:
    """Issue #324: Modelo 200 resolves 2024, 2025, and 2026 annual filings."""
    registry = get_registry()
    ruleset_2024 = registry.resolve(
        modelo=ModeloCode.MODELO_200,
        period=FiscalPeriod(year=2024),
    )
    ruleset_2025 = registry.resolve(
        modelo=ModeloCode.MODELO_200,
        period=FiscalPeriod(year=2025),
    )
    ruleset_2026 = registry.resolve(
        modelo=ModeloCode.MODELO_200,
        period=FiscalPeriod(year=2026),
    )
    assert ruleset_2024 is MODELO_200_2024
    assert ruleset_2025 is MODELO_200_2025
    assert ruleset_2026 is MODELO_200_2026


@pytest.mark.unit
def test_resolve_111_backfill_binds_2024() -> None:
    """/45: Modelo 111 2024 backfill resolves for 2024-period complementarias."""
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
    """/45: Modelo 123 2024 backfill resolves for 2024-period filings."""
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
def test_resolve_123_binds_2026() -> None:
    """Issue #320: Modelo 123 resolves for 2026-period filings."""
    registry = get_registry()
    ruleset = registry.resolve(
        modelo=ModeloCode.MODELO_123,
        period=FiscalPeriod(year=2026, quarter=Quarter.Q2),
    )
    assert ruleset is MODELO_123_2026


@pytest.mark.unit
def test_resolve_modelo_100_summary_via_variant() -> None:
    """Modelo 100 summary ruleset is reachable via variant="summary"."""
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
def test_resolve_default_variant_returns_full_form_not_summary() -> None:
    """Issue #317: default variant resolves to the full-form ruleset.

    Default-variant lookup now binds to the full-form
    ``modelo_100.<year>`` ruleset (landed by the M100 RENTA megaproject),
    NOT the partial ``modelo_100.summary.2025``. The summary variant
    remains reachable explicitly via ``variant="summary"``.
    """
    from ._rulesets.modelo_100_2025 import RULESET as MODELO_100_2025
    from ._rulesets.modelo_100_summary_2025 import (
        RULESET as MODELO_100_SUMMARY_2025,
    )

    registry = get_registry()
    ruleset = registry.resolve(
        modelo=ModeloCode.MODELO_100,
        period=FiscalPeriod(year=2025),
    )
    assert ruleset is MODELO_100_2025
    assert ruleset is not MODELO_100_SUMMARY_2025


@pytest.mark.unit
def test_resolve_131_backfill_binds_2024() -> None:
    """Modelo 131 resolves each covered year to its annual ruleset."""
    registry = get_registry()
    ruleset_2024 = registry.resolve(
        modelo=ModeloCode.MODELO_131,
        period=FiscalPeriod(year=2024, quarter=Quarter.Q1),
    )
    ruleset_2025 = registry.resolve(
        modelo=ModeloCode.MODELO_131,
        period=FiscalPeriod(year=2025, quarter=Quarter.Q1),
    )
    ruleset_2026 = registry.resolve(
        modelo=ModeloCode.MODELO_131,
        period=FiscalPeriod(year=2026, quarter=Quarter.Q1),
    )
    assert ruleset_2024 is MODELO_131_2024
    assert ruleset_2025 is MODELO_131_2025
    assert ruleset_2026 is MODELO_131_2026


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
    """The registry uses ``aeat.domain.modelos.ModeloCode`` (not the casillas enum)."""
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
