"""Structural tests for the Modelo 303 rulesets (#183)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ...financial.vat import EUMemberState, VATRateKind, lookup_rate
from ...modelos import ModeloCode
from .._codes import Quarter
from .._period import FiscalPeriod
from .._registry import RulesetRegistry
from .modelo_303_2024 import RULESET as MODELO_303_2024
from .modelo_303_2025 import RULESET as MODELO_303_2025

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]


def test_modelo_303_2024_loads() -> None:
    """The 2024 ruleset validates at import time."""
    assert MODELO_303_2024.ruleset_id == "modelo_303.2024"
    assert MODELO_303_2024.modelo is ModeloCode.MODELO_303
    assert MODELO_303_2024.effective_from == date(2024, 1, 1)
    assert MODELO_303_2024.effective_to == date(2024, 12, 31)


def test_modelo_303_2025_loads() -> None:
    """The 2025 ruleset validates at import time."""
    assert MODELO_303_2025.ruleset_id == "modelo_303.2025"
    assert MODELO_303_2025.modelo is ModeloCode.MODELO_303
    assert MODELO_303_2025.effective_from == date(2025, 1, 1)
    assert MODELO_303_2025.effective_to == date(2025, 12, 31)


def test_modelo_303_rulesets_have_25_casillas() -> None:
    """v1 coverage: 25 casillas — 01-09, 28-45, 64, 65, 66, 67, 69, 71."""
    expected_ids = {
        "01",
        "02",
        "03",
        "04",
        "05",
        "06",
        "07",
        "08",
        "09",
        "28",
        "29",
        "30",
        "31",
        "32",
        "33",
        "34",
        "35",
        "36",
        "37",
        "38",
        "39",
        "40",
        "41",
        "42",
        "43",
        "44",
        "45",
        "64",
        "65",
        "66",
        "67",
        "69",
        "71",
    }
    for ruleset in (MODELO_303_2024, MODELO_303_2025):
        actual_ids = {c.casilla_id for c in ruleset.casillas}
        assert actual_ids == expected_ids, ruleset.ruleset_id


def test_modelo_303_rulesets_have_12_formulas() -> None:
    """Twelve computed casillas: 02, 03, 05, 06, 08, 09, 44, 45, 64, 66, 69, 71."""
    expected_ids = {"02", "03", "05", "06", "08", "09", "44", "45", "64", "66", "69", "71"}
    for ruleset in (MODELO_303_2024, MODELO_303_2025):
        actual_ids = {f.casilla_id for f in ruleset.formulas}
        assert actual_ids == expected_ids, ruleset.ruleset_id


def test_modelo_303_evaluation_order_is_deterministic() -> None:
    """Two consecutive ``evaluation_order()`` calls return the same tuple."""
    first = MODELO_303_2025.evaluation_order()
    second = MODELO_303_2025.evaluation_order()
    assert first == second


def test_modelo_303_registry_resolution_2024() -> None:
    """The registry returns the 2024 ruleset for a 2024 period."""
    registry = RulesetRegistry(rulesets=(MODELO_303_2024, MODELO_303_2025))
    period = FiscalPeriod(year=2024, quarter=Quarter.Q3)
    resolved = registry.resolve(modelo=ModeloCode.MODELO_303, period=period)
    assert resolved.ruleset_id == "modelo_303.2024"


def test_modelo_303_registry_resolution_2025() -> None:
    """The registry returns the 2025 ruleset for a 2025 period."""
    registry = RulesetRegistry(rulesets=(MODELO_303_2024, MODELO_303_2025))
    period = FiscalPeriod(year=2025, quarter=Quarter.Q1)
    resolved = registry.resolve(modelo=ModeloCode.MODELO_303, period=period)
    assert resolved.ruleset_id == "modelo_303.2025"


@pytest.mark.parametrize(
    ("ruleset_param_id", "rate_kind"),
    [
        ("iva.rate_general", VATRateKind.GENERAL),
        ("iva.rate_reducido", VATRateKind.REDUCED),
        ("iva.rate_superreducido", VATRateKind.SUPER_REDUCED),
    ],
)
def test_modelo_303_2024_rate_consistency_with_substrate(ruleset_param_id: str, rate_kind: VATRateKind) -> None:
    """Ruleset rate parameters must match the VAT substrate's ES rates for 2024."""
    on_date = MODELO_303_2024.effective_from
    rate = lookup_rate(EUMemberState.ES, rate_kind, on_date)
    param_value = MODELO_303_2024.parameters.resolve(ruleset_param_id, on=on_date)
    assert param_value == rate.pct / Decimal("100"), (
        f"ruleset {ruleset_param_id}={param_value} diverges from VAT_RATE_TABLE pct={rate.pct} (kind={rate_kind.value})"
    )


@pytest.mark.parametrize(
    ("ruleset_param_id", "rate_kind"),
    [
        ("iva.rate_general", VATRateKind.GENERAL),
        ("iva.rate_reducido", VATRateKind.REDUCED),
        ("iva.rate_superreducido", VATRateKind.SUPER_REDUCED),
    ],
)
def test_modelo_303_2025_rate_consistency_with_substrate(ruleset_param_id: str, rate_kind: VATRateKind) -> None:
    """Ruleset rate parameters must match the VAT substrate's ES rates for 2025."""
    on_date = MODELO_303_2025.effective_from
    rate = lookup_rate(EUMemberState.ES, rate_kind, on_date)
    param_value = MODELO_303_2025.parameters.resolve(ruleset_param_id, on=on_date)
    assert param_value == rate.pct / Decimal("100"), (
        f"ruleset {ruleset_param_id}={param_value} diverges from VAT_RATE_TABLE pct={rate.pct} (kind={rate_kind.value})"
    )


def test_modelo_303_2024_and_2025_share_casilla_definitions() -> None:
    """The 2024 and 2025 rulesets carry equal casilla definitions.

    Identity (``is``) does not survive pydantic's strict model
    validation (the tuple is rebuilt at construction time), so the
    invariant is asserted with ``==`` on the tuple of frozen
    ``CasillaDefinition`` records.
    """
    assert MODELO_303_2024.casillas == MODELO_303_2025.casillas


def test_modelo_303_2024_and_2025_share_citation_records() -> None:
    """The 2024 and 2025 rulesets carry equal legal citations."""
    assert MODELO_303_2024.legal_citations == MODELO_303_2025.legal_citations
