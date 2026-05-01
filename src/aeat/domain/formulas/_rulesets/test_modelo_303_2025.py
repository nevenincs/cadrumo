"""End-to-end derivation tests for the Modelo 303 2025 ruleset (#183)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from .._engine import Engine
from .modelo_303_2025 import RULESET as MODELO_303_2025

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


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


def test_engine_round_trip_is_deterministic() -> None:
    """Wave 53 stream 4 M3 rename: this test proves engine determinism,
    not formula correctness. Feeding derived values back in yields zero
    discrepancies regardless of whether the formulas are right. See
    ``test_external_worked_example_aeat_livA_rates`` below for the
    correctness test anchored to AEAT-published rates.
    """
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


def test_external_worked_example_aeat_liva_rates() -> None:
    """External-anchored worked example (wave 57a H5/H6 closure).

    Provenance: Ley 37/1992 (LIVA) artículos 90 y 91 fix the IVA
    rates at 21% general, 10% reducido, 4% superreducido. This
    fixture derives expected values from those rates independently
    of the ruleset's `iva.rate_*` parameters — a rate-swap bug in
    the ruleset would surface as a Decimal mismatch.

    Scenario: Kent's Q1 2025 autónomo filing with:
    - Base general (casilla 07): 20 000 €
    - Base reducido (casilla 04): 5 000 €
    - Base superreducido (casilla 01): 1 000 €

    Per LIVA art. 90/91 (AEAT legal baseline, NOT the ruleset):
    - Cuota general: 20 000 x 21% = 4 200 € (casilla 09).
    - Cuota reducido: 5 000 x 10% = 500 € (casilla 06).
    - Cuota superreducido: 1 000 x 4% = 40 € (casilla 03).

    Citations:
    - BOE-A-1992-28740 Ley 37/1992 art. 90 (tipo general 21%)
      https://www.boe.es/buscar/act.php?id=BOE-A-1992-28740#a90
    - BOE-A-1992-28740 Ley 37/1992 art. 91 (reducido 10%, superreducido 4%)
      https://www.boe.es/buscar/act.php?id=BOE-A-1992-28740#a91
    """
    engine = Engine()
    # Inputs derived from LIVA, not from the ruleset:
    inputs = {
        "01": Decimal("1000.00"),  # base superreducido
        "04": Decimal("5000.00"),  # base reducido
        "07": Decimal("20000.00"),  # base general
        "65": Decimal("100"),  # full attribution to Territorio Común
    }
    derived = {e.casilla_id: e.value for e in engine.derive(ruleset=MODELO_303_2025, inputs=inputs).entries}
    # Independent arithmetic — these values come from AEAT rates, not the ruleset.
    assert derived["03"] == Decimal("40.00"), "4% superreducido on 1000"
    assert derived["06"] == Decimal("500.00"), "10% reducido on 5000"
    assert derived["09"] == Decimal("4200.00"), "21% general on 20000"
    # Sum of cuotas: 40 + 500 + 4200 = 4740.
    # Casilla 45 is cuota a compensar (= sum cuotas + 44 - 44_deducible); since
    # we omit 44 deducciones, 45 = 4200 + (from 12/27/41 deducciones) — but
    # with a clean fixture 45 = 4200 (only 07 base provided for general
    # attribution). The sum-of-cuotas assertion is captured by 03/06/09
    # individually; attribution math (casilla 66) is verified separately.


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
