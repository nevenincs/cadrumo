"""Unit tests for the Modelo 123 2025 ruleset."""

from __future__ import annotations

from decimal import Decimal

import pytest

from .._engine import Engine
from . import MODELO_123_2025

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]


def _provided(**overrides: str) -> dict[str, Decimal]:
    """Consistent 123 fixture: 1+4=5 perceptores, 1500+8000=9500 base, 285+1520=1805, 1805-0=1805."""
    base = {
        "01": "1",
        "02": "4",
        "03": "5",
        "04": "1500.00",
        "05": "8000.00",
        "06": "9500.00",
        "07": "285.00",
        "08": "1520.00",
        "09": "1805.00",
        "10": "0.00",
        "11": "1805.00",
    }
    base.update(overrides)
    return {k: Decimal(v) for k, v in base.items()}


class TestModelo123Ruleset:
    def test_consistent_quarter_is_clean(self) -> None:
        report = Engine().audit_against(
            ruleset=MODELO_123_2025,
            provided=_provided(),
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean()

    def test_total_perceptores_mismatch(self) -> None:
        report = Engine().audit_against(
            ruleset=MODELO_123_2025,
            provided=_provided(**{"03": "6"}),
            tolerance=Decimal("0.01"),
        )
        assert not report.is_clean()
        assert "03" in {d.casilla_id for d in report.discrepancies}

    def test_total_base_mismatch(self) -> None:
        report = Engine().audit_against(
            ruleset=MODELO_123_2025,
            provided=_provided(**{"06": "9000.00"}),
            tolerance=Decimal("0.01"),
        )
        assert not report.is_clean()
        assert "06" in {d.casilla_id for d in report.discrepancies}

    def test_complementaria_offset_applied(self) -> None:
        # 09 = 2000 (07+08=800+1200), 10 = 500, expected 11 = 1500.
        report = Engine().audit_against(
            ruleset=MODELO_123_2025,
            provided=_provided(
                **{
                    "07": "800.00",
                    "08": "1200.00",
                    "09": "2000.00",
                    "10": "500.00",
                    "11": "1500.00",
                }
            ),
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean()

    def test_ruleset_has_four_formulas(self) -> None:
        # 03, 06, 09, 11 are computed; 01/02/04/05/07/08/10 are user input.
        computed = {c.casilla_id for c in MODELO_123_2025.casillas if c.computed}
        assert computed == {"03", "06", "09", "11"}

    def test_external_worked_example_lirpf_art_25(self) -> None:
        """External-anchored worked example (wave 59c H3 closure).

        Provenance: Ley 35/2006 (LIRPF) art. 25 defines rendimientos
        del capital mobiliario (dividendos, intereses). Modelo 123 is
        a pure aggregation — 03=01+02, 06=04+05, 09=07+08, 11=09-10.
        No rate is applied here; external anchor is the structural
        invariant from AEAT Instrucciones Modelo 123.

        Scenario: Kent as retenedor with 2 dividend perceptores +
        3 interest perceptores:
        - 01 perc. dividendos = 2. 02 perc. otras = 3. 03 total = 5.
        - 04 base div. = 5 000. 05 base otras = 12 000. 06 total = 17 000.
        - 07 ret. div. = 950 (5 000 x 19%). 08 ret. otras = 2 280
          (12 000 x 19%). 09 total = 3 230.
        - 10 = 0. 11 = 3 230.

        Citation: BOE-A-2006-20764 art. 25 (LIRPF).
        """
        provided = _provided(
            **{
                "01": "2",
                "02": "3",
                "03": "5",
                "04": "5000.00",
                "05": "12000.00",
                "06": "17000.00",
                "07": "950.00",
                "08": "2280.00",
                "09": "3230.00",
                "10": "0.00",
                "11": "3230.00",
            }
        )
        report = Engine().audit_against(ruleset=MODELO_123_2025, provided=provided, tolerance=Decimal("0.01"))
        assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]
