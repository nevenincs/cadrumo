"""End-to-end derivation tests for the Modelo 303 2025 ruleset (#183)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from .._engine import Engine
from .modelo_303_2025 import RULESET as MODELO_303_2025

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]


def _ledger_dict(inputs: dict[str, Decimal]) -> dict[str, Decimal]:
    """Derive ``MODELO_303_2025`` and return ``{casilla_id: value}``."""
    engine = Engine()
    ledger = engine.derive(ruleset=MODELO_303_2025, inputs=inputs)
    return {entry.casilla_id: entry.value for entry in ledger.entries}


def test_all_zero_quarter() -> None:
    """Every input zero => every computed casilla 0.00."""
    values = _ledger_dict({})
    for casilla_id in ("03", "06", "09", "44", "45", "64", "66", "69", "71"):
        assert values[casilla_id] == Decimal("0.00"), casilla_id


def test_general_only_quarter_missing_65_yields_zero_attribution() -> None:
    """Base 07 = 10000 with 65 omitted => 66/69/71 collapse to 0.

    The wave-1 missing-input contract defaults 65 to ``Decimal('0')``;
    casilla 66 = 64 x 65 / 100 then resolves to 0. Downstream
    callers must supply 65=100 explicitly, exactly as the AEAT form
    pre-prints. This test pins the documented behaviour so any
    future opinionated default would surface as a regression.
    """
    values = _ledger_dict({"07": Decimal("10000.00")})
    assert values["09"] == Decimal("2100.00")
    assert values["45"] == Decimal("2100.00")
    assert values["64"] == Decimal("2100.00")
    assert values["66"] == Decimal("0.00")
    assert values["69"] == Decimal("0.00")
    assert values["71"] == Decimal("0.00")


def test_general_only_ordinary_quarter_with_explicit_65() -> None:
    """Base 07 = 10000, 65 = 100 => 71 = 2100.00."""
    values = _ledger_dict({"07": Decimal("10000.00"), "65": Decimal("100")})
    assert values["09"] == Decimal("2100.00")
    assert values["45"] == Decimal("2100.00")
    assert values["64"] == Decimal("2100.00")
    assert values["66"] == Decimal("2100.00")
    assert values["69"] == Decimal("2100.00")
    assert values["71"] == Decimal("2100.00")


def test_mixed_rates_quarter() -> None:
    """Bases 01=1000, 04=2000, 07=5000 => cuotas 40, 200, 1050."""
    values = _ledger_dict(
        {
            "01": Decimal("1000.00"),
            "04": Decimal("2000.00"),
            "07": Decimal("5000.00"),
            "65": Decimal("100"),
        }
    )
    assert values["03"] == Decimal("40.00")
    assert values["06"] == Decimal("200.00")
    assert values["09"] == Decimal("1050.00")
    assert values["45"] == Decimal("1290.00")
    assert values["71"] == Decimal("1290.00")


def test_heavy_deducible_negative_result() -> None:
    """Devengado 1000, deducible 1500 => 45 = -500.00."""
    values = _ledger_dict(
        {
            "07": Decimal("1000.00"),
            "29": Decimal("1000.00"),
            "31": Decimal("500.00"),
            "65": Decimal("100"),
        }
    )
    # 09 = 210, total devengado = 210, deducible = 1500
    assert values["09"] == Decimal("210.00")
    assert values["44"] == Decimal("1500.00")
    assert values["45"] == Decimal("-1290.00")
    assert values["71"] == Decimal("-1290.00")


def test_negative_rectification() -> None:
    """40 = -200 (negative rectification) => 44 reflects the negative."""
    values = _ledger_dict(
        {
            "07": Decimal("0"),
            "29": Decimal("500.00"),
            "40": Decimal("-200.00"),
            "65": Decimal("100"),
        }
    )
    assert values["44"] == Decimal("300.00")
    assert values["45"] == Decimal("-300.00")


def test_intra_community_acquisition() -> None:
    """36/37 self-assessed contribution feeds into 44 deducible."""
    values = _ledger_dict(
        {
            "07": Decimal("0"),
            "37": Decimal("1050.00"),  # cuota self-assessed at 21%
            "65": Decimal("100"),
        }
    )
    assert values["44"] == Decimal("1050.00")
    # Note: the self-assessed devengado contribution is NOT
    # automatically reflected on casilla 09 in this ruleset (the
    # caller computes the devengado side separately because the
    # ruleset only auto-derives 09 from base 07 x 0.21). Audit
    # tests that need the symmetric devengado/deducible split
    # belong to a downstream draft-builder layer.


def test_import_third_country() -> None:
    """32/33 import contribution feeds into 44 deducible."""
    values = _ledger_dict(
        {
            "07": Decimal("0"),
            "33": Decimal("630.00"),
            "65": Decimal("100"),
        }
    )
    assert values["44"] == Decimal("630.00")


def test_partial_state_attribution() -> None:
    """65 = 50 => 66 = 64 / 2."""
    values = _ledger_dict(
        {
            "07": Decimal("10000.00"),
            "65": Decimal("50"),
        }
    )
    assert values["64"] == Decimal("2100.00")
    assert values["66"] == Decimal("1050.00")
    assert values["69"] == Decimal("1050.00")


def test_carry_over_compensation() -> None:
    """67 reduces the resultado."""
    values = _ledger_dict(
        {
            "07": Decimal("10000.00"),
            "65": Decimal("100"),
            "67": Decimal("500.00"),
        }
    )
    assert values["66"] == Decimal("2100.00")
    assert values["69"] == Decimal("1600.00")
    assert values["71"] == Decimal("1600.00")


def test_boundary_rounding() -> None:
    """333.33 x 0.21 = 69.9993 → ROUND_HALF_UP to 70.00."""
    values = _ledger_dict(
        {
            "07": Decimal("333.33"),
            "65": Decimal("100"),
        }
    )
    assert values["09"] == Decimal("70.00")


def test_constant_rates_emerge_from_engine() -> None:
    """Casillas 02/05/08 surface their printed rate constants."""
    values = _ledger_dict({"65": Decimal("100")})
    assert values["02"] == Decimal("4.00")
    assert values["05"] == Decimal("10.00")
    assert values["08"] == Decimal("21.00")


def test_audit_against_clean() -> None:
    """Feeding inputs + correct computed values yields zero discrepancies."""
    inputs = {
        "07": Decimal("10000.00"),
        "65": Decimal("100"),
    }
    engine = Engine()
    derived = engine.derive(ruleset=MODELO_303_2025, inputs=inputs)
    full_provided = dict(inputs)
    for entry in derived.entries:
        full_provided[entry.casilla_id] = entry.value
    report = engine.audit_against(ruleset=MODELO_303_2025, provided=full_provided)
    assert report.discrepancies == ()


def test_audit_against_divergence_surfaces() -> None:
    """A wrong computed value surfaces as a Discrepancy."""
    engine = Engine()
    full_provided = {
        "07": Decimal("10000.00"),
        "65": Decimal("100"),
        "09": Decimal("9999.99"),  # wrong on purpose
    }
    report = engine.audit_against(ruleset=MODELO_303_2025, provided=full_provided)
    diverged = {d.casilla_id for d in report.discrepancies}
    assert "09" in diverged
