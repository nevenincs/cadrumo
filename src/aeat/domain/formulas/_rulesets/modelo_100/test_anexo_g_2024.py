"""Unit tests for Modelo 100 Anexo G — cuotas + tarifas (2024).

External-anchored to LIRPF arts. 63 + 66 + 67 + 68.4 + 79.

Strategy: use `Engine.derive()` directly and inspect specific ledger
entries. Avoids the audit-comparison cascade that would surface
unrelated discrepancies when only the focal casillas matter.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ..._engine import Engine
from .. import MODELO_100_2024, MODELO_100_2025

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _zero_inputs(ruleset) -> dict[str, Decimal]:
    """Return zero values for every NON-COMPUTED casilla."""
    return {c.casilla_id: Decimal("0.00") for c in ruleset.casillas if not c.computed}


def _derived(ruleset, inputs: dict[str, Decimal]) -> dict[str, Decimal]:
    """Run the engine and return derived values keyed by casilla_id."""
    ledger = Engine().derive(ruleset=ruleset, inputs=inputs)
    return {entry.casilla_id: entry.value for entry in ledger.entries}


class TestProgressiveTarifaEstatalGeneral:
    """LIRPF art. 63 progressive scale: 0-12450 9.5%; 12450-20200 12%;
    20200-35200 15%; 35200-60000 18.5%; 60000-300000 22.5%; >300000 24.5%.
    Stable 2021-2026.
    """

    @pytest.mark.parametrize(
        ("blg", "expected_tarifa"),
        [
            (Decimal("0.00"), Decimal("0.00")),
            (Decimal("20200.00"), Decimal("2112.75")),
            (Decimal("30000.00"), Decimal("3582.75")),
            (Decimal("35200.00"), Decimal("4362.75")),
            (Decimal("60000.00"), Decimal("8950.75")),
            (Decimal("100000.00"), Decimal("17950.75")),
            (Decimal("300000.00"), Decimal("62950.75")),
            (Decimal("500000.00"), Decimal("111950.75")),
        ],
    )
    def test_tarifa_blg_progressive_anchors(
        self,
        blg: Decimal,
        expected_tarifa: Decimal,
    ) -> None:
        """Verify casilla 0540 (tarifa estatal sobre BLG) at 9 anchors
        spanning all 6 brackets of the LIRPF art. 63 progressive scale.
        """
        inputs = _zero_inputs(MODELO_100_2024)
        # Channel into BLG via B1 input 0001 (sueldos). At rendimiento >
        # 19747.50 EUR the art. 20 reducción = 0 so 0022 = 0001; BIG =
        # 0022; BLG = clamp_pos(BIG - 0 - 0) = 0022 = 0001.
        inputs["0001"] = blg
        derived = _derived(MODELO_100_2024, inputs)
        assert derived["0545"] == blg, f"BLG channel: {derived['0545']} != {blg}"
        assert derived["0540"] == expected_tarifa


class TestMinimoAbsorption:
    """LIRPF art. 56: minimo personal y familiar applied at scale =
    progressive_tarifa(BLG) - progressive_tarifa(min(0500, BLG)).
    """

    def test_minimo_absorbs_at_lowest_bracket(self) -> None:
        """BLG 30.000, minimo 5.550 -> tarifa(30000) - tarifa(5550) =
        3582.75 - 527.25 = 3055.50.
        Channel BLG via 0001=30000 (rendimiento > 19747.50 -> reducción 0).
        """
        inputs = _zero_inputs(MODELO_100_2024)
        inputs["0001"] = Decimal("30000.00")
        inputs["0505"] = Decimal("5550.00")
        derived = _derived(MODELO_100_2024, inputs)
        assert derived["0545"] == Decimal("30000.00")
        assert derived["0500"] == Decimal("5550.00")
        assert derived["0540"] == Decimal("3582.75")
        assert derived["0542"] == Decimal("527.25")
        assert derived["0550"] == Decimal("3055.50")


class TestProgressiveTarifaAhorro2024:
    """LIRPF art. 66 pre Ley 7/2024: state half rates 9.5/10.5/11.5/13.5/14 %."""

    @pytest.mark.parametrize(
        ("bia", "expected_tarifa_estatal"),
        [
            (Decimal("0.00"), Decimal("0.00")),
            (Decimal("6000.00"), Decimal("570.00")),
            (Decimal("50000.00"), Decimal("5190.00")),
            (Decimal("200000.00"), Decimal("22440.00")),
            (Decimal("300000.00"), Decimal("35940.00")),
            (Decimal("500000.00"), Decimal("63940.00")),  # pre Ley 7/2024 top 14%
        ],
    )
    def test_tarifa_ahorro_progressive_anchors(
        self,
        bia: Decimal,
        expected_tarifa_estatal: Decimal,
    ) -> None:
        """Verify 0560 against the 5-bracket pre-Ley-7/2024 ahorro scale."""
        inputs = _zero_inputs(MODELO_100_2024)
        # Channel into BIA via B2 input 0028 (dividendos). 0049 derives
        # = clamp_pos(0048 - 0) = clamp_pos(0028 - 0) = 0028 when only
        # 0028 is set; 0460 = 0049 + 0400 = 0028; 0555 = 0460 = 0028.
        inputs["0028"] = bia
        derived = _derived(MODELO_100_2024, inputs)
        assert derived["0049"] == bia
        assert derived["0460"] == bia
        assert derived["0555"] == bia
        assert derived["0560"] == expected_tarifa_estatal


class TestProgressiveTarifaAhorroDelta:
    """Pre-Ley 7/2024: top bracket >300000 is 14% state half (vs 15% post)."""

    def test_tarifa_ahorro_top_bracket_2024_pre_ley_7_2024(self) -> None:
        """At BIA 500.000: 2024 tarifa estatal = 35940 + 200000*0.14 = 63940."""
        inputs = _zero_inputs(MODELO_100_2024)
        inputs["0028"] = Decimal("500000.00")  # Channel into BIA via B2 dividendos.
        derived = _derived(MODELO_100_2024, inputs)
        assert derived["0560"] == Decimal("63940.00")

    def test_tarifa_ahorro_2025_vs_2024_top_bracket_delta(self) -> None:
        """At BIA 500.000: 2025 - 2024 = 65940 - 63940 = 2000 EUR (delta of
        200.000 EUR above 300.000 EUR x (15% - 14%) = 2.000 EUR).
        """
        inputs_2024 = _zero_inputs(MODELO_100_2024)
        inputs_2024["0028"] = Decimal("500000.00")
        inputs_2025 = _zero_inputs(MODELO_100_2025)
        inputs_2025["0028"] = Decimal("500000.00")
        derived_2024 = _derived(MODELO_100_2024, inputs_2024)
        derived_2025 = _derived(MODELO_100_2025, inputs_2025)
        assert derived_2025["0560"] - derived_2024["0560"] == Decimal("2000.00")


class TestCuotaChain:
    """Cuota chain: 0595 = 0550 + 0551 + 0560 + 0561; 0698 = clamp_pos(
    0595 - 0630 - 0612); 0720 = 0698 - 0699 - 0700.
    """

    def test_cuota_diferencial_after_retenciones(self) -> None:
        """BLG 30.000, minimo 5.550, autonomic 0551=2.000, retenciones 500,
        pagos 100. Verify the cuota chain end-to-end.
        """
        inputs = _zero_inputs(MODELO_100_2024)
        inputs["0001"] = Decimal("30000.00")
        inputs["0505"] = Decimal("5550.00")
        inputs["0551"] = Decimal("2000.00")
        inputs["0699"] = Decimal("500.00")
        inputs["0700"] = Decimal("100.00")
        derived = _derived(MODELO_100_2024, inputs)
        # 0550 = 3055.50; 0595 = 3055.50 + 2000 + 0 + 0 = 5055.50;
        # 0698 = clamp_pos(5055.50 - 0 - 0) = 5055.50;
        # 0720 = 5055.50 - 500 - 100 = 4455.50.
        assert derived["0550"] == Decimal("3055.50")
        assert derived["0595"] == Decimal("5055.50")
        assert derived["0698"] == Decimal("5055.50")
        assert derived["0720"] == Decimal("4455.50")


class TestCeutaMelilla:
    """LIRPF art. 68.4 post Ley 6/2018: 60% deduction over cuota
    proporcional a rentas obtenidas en Ceuta/Melilla.
    """

    def test_ceuta_melilla_60pct_reduces_cuota_liquida(self) -> None:
        """BLG 30.000, autonomic 0551=2.000, Ceuta/Melilla 0612=3.000.
        0698 = clamp_pos(0595 - 0 - 0612) = clamp_pos(5055.50 - 3000) = 2055.50.
        """
        inputs = _zero_inputs(MODELO_100_2024)
        inputs["0001"] = Decimal("30000.00")
        inputs["0505"] = Decimal("5550.00")
        inputs["0551"] = Decimal("2000.00")
        inputs["0612"] = Decimal("3000.00")
        derived = _derived(MODELO_100_2024, inputs)
        assert derived["0595"] == Decimal("5055.50")
        assert derived["0698"] == Decimal("2055.50")

    def test_ceuta_melilla_clamps_to_zero_when_exceeds_cuota(self) -> None:
        """If 0612 caller-supplied exceeds cuota íntegra (which would be a
        user error — LIRPF art. 68.4 caps the deduction at 60% of cuota
        íntegra), the clamp_pos protects against negative cuota líquida.
        BLG 25000 (low rendimiento, art. 20 reducción active brings BLG to
        ~25000-0 since 25000 > 19747.50 -> reducción 0). Cuota íntegra small;
        0612=100000 way exceeds; 0698 clamps to 0.
        """
        inputs = _zero_inputs(MODELO_100_2024)
        inputs["0001"] = Decimal("25000.00")  # > 19747.50 -> reducción 0
        inputs["0505"] = Decimal("5550.00")
        inputs["0612"] = Decimal("100000.00")
        derived = _derived(MODELO_100_2024, inputs)
        assert derived["0698"] == Decimal("0.00")
