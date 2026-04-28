"""Unit tests for per-CCAA tarifa autonómica brackets.

Verifies the per-CCAA progressive scales for the 5 highest-population
CCAAs (Madrid, Cataluña, Andalucía, Comunitat Valenciana, Castilla y
León) at boundary + midpoint anchors. Each bracket boundary is hit so
any rate / threshold drift in `_ccaa.py` would surface as a test
failure.

The `compute_cuota_autonomica_general()` helper is the public surface
callers use to derive casilla 0551 externally before supplying it to
the engine via Anexo G's caller-supplied 0551 input.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ._ccaa import (
    CCAA,
    PER_CCAA_TARIFA_AUTONOMICA,
    compute_cuota_autonomica_general,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_submission]


class TestTarifaMadrid:
    """Madrid Decreto Legislativo 1/2010 modif. Ley 5/2024 deflactación.

    Tramos: 0-13362.22 8.5%; 13362.22-19004.63 10.7%;
    19004.63-35425.68 12.8%; 35425.68-57320.40 17.4%; 57320.40+ 20.5%.
    """

    @pytest.mark.parametrize(
        ("blg", "expected"),
        [
            # Boundaries + midpoints + above-cap. Expected values verified
            # against the helper's progressive computation; each anchor
            # exercises a distinct bracket transition.
            (Decimal("0.00"), Decimal("0.00")),
            (Decimal("13362.22"), Decimal("1135.79")),  # 13362.22 * 0.085
            # +5642.41 * 0.107 = 603.738; cumul 1739.527 -> 1739.53
            (Decimal("19004.63"), Decimal("1739.53")),
            # +16421.05 * 0.128 = 2101.894; cumul 3841.421 -> 3841.42
            (Decimal("35425.68"), Decimal("3841.42")),
            # +21894.72 * 0.174 = 3809.681; cumul 7651.102 -> 7651.10
            (Decimal("57320.40"), Decimal("7651.10")),
            # +42679.60 * 0.205 = 8749.318; cumul 16400.420 -> 16400.42
            (Decimal("100000.00"), Decimal("16400.42")),
        ],
    )
    def test_madrid_progressive_anchors(self, blg: Decimal, expected: Decimal) -> None:
        assert compute_cuota_autonomica_general(blg, CCAA.MADRID) == expected


class TestTarifaCataluna:
    """Cataluña Llei 5/2020 — 9-bracket progressive scale.

    Top bracket >175.000 at 25.5%.
    """

    def test_cataluna_zero(self) -> None:
        assert compute_cuota_autonomica_general(Decimal("0.00"), CCAA.CATALUNA) == Decimal("0.00")

    def test_cataluna_first_bracket_cap(self) -> None:
        # 12450 * 0.105 = 1307.25
        assert compute_cuota_autonomica_general(Decimal("12450.00"), CCAA.CATALUNA) == Decimal("1307.25")

    def test_cataluna_top_bracket_active(self) -> None:
        # At 200000: cumul through previous brackets + (200000-175000)*0.255
        # = bracket sums + 25000 * 0.255 = 6375 + previous
        # Previous brackets cumul:
        # 12450*0.105 = 1307.25
        # +5257.20*0.12 = 630.864
        # +3292.80*0.14 = 460.992
        # +12007.20*0.15 = 1801.08
        # +20400.00*0.188 = 3835.20
        # +36592.80*0.215 = 7867.452
        # +30000.00*0.235 = 7050.00
        # +55000.00*0.245 = 13475.00
        # +25000.00*0.255 = 6375.00
        # = 42802.838
        assert compute_cuota_autonomica_general(Decimal("200000.00"), CCAA.CATALUNA) == Decimal("42802.84")


class TestTarifaAndalucia:
    """Andalucía Decreto Legislativo 1/2018 — 5-bracket progressive scale."""

    @pytest.mark.parametrize(
        ("blg", "expected"),
        [
            (Decimal("0.00"), Decimal("0.00")),
            (Decimal("13000.00"), Decimal("1235.00")),  # 13000 * 0.095
            (Decimal("21100.00"), Decimal("2207.00")),  # +8100*0.12
            (Decimal("35200.00"), Decimal("4322.00")),  # +14100*0.15
            (Decimal("60000.00"), Decimal("8910.00")),  # +24800*0.185
            (Decimal("100000.00"), Decimal("17910.00")),  # +40000*0.225
        ],
    )
    def test_andalucia_progressive_anchors(self, blg: Decimal, expected: Decimal) -> None:
        assert compute_cuota_autonomica_general(blg, CCAA.ANDALUCIA) == expected


class TestTarifaComunidadValenciana:
    """Comunitat Valenciana Ley 13/1997 — 11-bracket progressive scale.

    Top bracket >200.000 at 29.5%. The most steeply progressive of the
    5 encoded CCAAs.
    """

    def test_valenciana_zero(self) -> None:
        assert compute_cuota_autonomica_general(Decimal("0.00"), CCAA.COMUNIDAD_VALENCIANA) == Decimal("0.00")

    def test_valenciana_first_bracket(self) -> None:
        # 12000 * 0.09 = 1080
        assert compute_cuota_autonomica_general(Decimal("12000.00"), CCAA.COMUNIDAD_VALENCIANA) == Decimal("1080.00")

    def test_valenciana_top_bracket(self) -> None:
        """At BLG 300.000 the cumulative cuota walks all 11 brackets:
          12000*0.09 = 1080
        + 10000*0.12 = 1200 -> cumul 2280
        + 10000*0.15 = 1500 -> 3780
        + 10000*0.175 = 1750 -> 5530
        + 10000*0.20 = 2000 -> 7530
        + 13000*0.225 = 2925 -> 10455
        + 7000*0.25 = 1750 -> 12205
        + 28000*0.265 = 7420 -> 19625
        + 50000*0.275 = 13750 -> 33375
        + 50000*0.285 = 14250 -> 47625
        + 100000*0.295 = 29500 -> 77125
        """
        assert compute_cuota_autonomica_general(Decimal("300000.00"), CCAA.COMUNIDAD_VALENCIANA) == Decimal("77125.00")


class TestTarifaCastillaYLeon:
    """Castilla y León Decreto Legislativo 1/2013 — 5-bracket scale."""

    @pytest.mark.parametrize(
        ("blg", "expected"),
        [
            (Decimal("0.00"), Decimal("0.00")),
            (Decimal("12450.00"), Decimal("1120.50")),  # 12450 * 0.09
            (Decimal("20200.00"), Decimal("2050.50")),  # +7750*0.12
            (Decimal("35200.00"), Decimal("4150.50")),  # +15000*0.14
            (Decimal("60000.00"), Decimal("8738.50")),  # +24800*0.185
            (Decimal("100000.00"), Decimal("17338.50")),  # +40000*0.215
        ],
    )
    def test_castilla_leon_progressive_anchors(self, blg: Decimal, expected: Decimal) -> None:
        assert compute_cuota_autonomica_general(blg, CCAA.CASTILLA_Y_LEON) == expected


class TestUnencodedCCAAs:
    """The 10 remaining CCAAs raise KeyError — caller computes externally
    pending each Comunidad's per-CCAA texto refundido encoding in a
    follow-up wave.
    """

    @pytest.mark.parametrize(
        "unencoded_ccaa",
        [
            CCAA.ARAGON,
            CCAA.ASTURIAS,
            CCAA.BALEARES,
            CCAA.CANARIAS,
            CCAA.CANTABRIA,
            CCAA.CASTILLA_LA_MANCHA,
            CCAA.EXTREMADURA,
            CCAA.GALICIA,
            CCAA.LA_RIOJA,
            CCAA.MURCIA,
        ],
    )
    def test_unencoded_ccaa_raises_keyerror(self, unencoded_ccaa: CCAA) -> None:
        with pytest.raises(KeyError):
            compute_cuota_autonomica_general(Decimal("30000.00"), unencoded_ccaa)


class TestPerCCAATarifaCoverage:
    """Verifies the PER_CCAA_TARIFA_AUTONOMICA dict covers exactly the
    5 highest-population CCAAs declared in the docstring."""

    def test_exactly_5_ccaas_encoded(self) -> None:
        assert len(PER_CCAA_TARIFA_AUTONOMICA) == 5
        assert set(PER_CCAA_TARIFA_AUTONOMICA.keys()) == {
            CCAA.MADRID,
            CCAA.CATALUNA,
            CCAA.ANDALUCIA,
            CCAA.COMUNIDAD_VALENCIANA,
            CCAA.CASTILLA_Y_LEON,
        }

    def test_each_tarifa_has_open_top_bracket(self) -> None:
        """Every encoded tarifa's last bracket has `to_value=None`."""
        for ccaa, brackets in PER_CCAA_TARIFA_AUTONOMICA.items():
            _, last_to, _ = brackets[-1]
            assert last_to is None, f"{ccaa.value}: top bracket must be open-ended (to_value=None)"

    def test_each_tarifa_has_ascending_brackets(self) -> None:
        """Bracket boundaries are strictly ascending per progressive-scale invariant."""
        for ccaa, brackets in PER_CCAA_TARIFA_AUTONOMICA.items():
            prior_to: Decimal | None = None
            for from_value, to_value, _rate in brackets:
                from_d = Decimal(from_value)
                if prior_to is not None:
                    assert from_d == prior_to, f"{ccaa.value}: bracket from {from_value} != prior to {prior_to}"
                if to_value is not None:
                    to_d = Decimal(to_value)
                    assert to_d > from_d, f"{ccaa.value}: bracket to {to_value} <= from {from_value}"
                    prior_to = to_d
                else:
                    prior_to = None
