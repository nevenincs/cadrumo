"""Unit tests for the Modelo 123 2025 ruleset."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .._engine import Engine
from .._ruleset import Ruleset
from . import MODELO_123_2024, MODELO_123_2025, MODELO_123_2026

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


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
        """External-anchored worked example (closure).

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


@pytest.mark.parametrize(
    ("ruleset", "expected_id", "expected_from", "expected_to"),
    [
        (MODELO_123_2024, "modelo_123.2024", date(2024, 1, 1), date(2024, 12, 31)),
        (MODELO_123_2025, "modelo_123.2025", date(2025, 1, 1), date(2025, 12, 31)),
        (MODELO_123_2026, "modelo_123.2026", date(2026, 1, 1), date(2026, 12, 31)),
    ],
)
def test_modelo_123_per_annum_effective_ranges(
    ruleset: Ruleset,
    expected_id: str,
    expected_from: date,
    expected_to: date,
) -> None:
    assert ruleset.ruleset_id == expected_id
    assert ruleset.effective_from == expected_from
    assert ruleset.effective_to == expected_to


@pytest.mark.parametrize(
    ("ruleset", "case_id", "provided"),
    [
        pytest.param(
            MODELO_123_2024,
            "zero-boundary",
            {
                "01": Decimal("0"),
                "02": Decimal("0"),
                "03": Decimal("0"),
                "04": Decimal("0.00"),
                "05": Decimal("0.00"),
                "06": Decimal("0.00"),
                "07": Decimal("0.00"),
                "08": Decimal("0.00"),
                "09": Decimal("0.00"),
                "10": Decimal("0.00"),
                "11": Decimal("0.00"),
            },
            id="2024-zero-boundary",
        ),
        pytest.param(
            MODELO_123_2024,
            "typical-irpf-19-percent",
            {
                "01": Decimal("2"),
                "02": Decimal("3"),
                "03": Decimal("5"),
                "04": Decimal("5000.00"),
                "05": Decimal("12000.00"),
                "06": Decimal("17000.00"),
                "07": Decimal("950.00"),
                "08": Decimal("2280.00"),
                "09": Decimal("3230.00"),
                "10": Decimal("0.00"),
                "11": Decimal("3230.00"),
            },
            id="2024-typical",
        ),
        pytest.param(
            MODELO_123_2024,
            "complementaria-offset",
            {
                "01": Decimal("1"),
                "02": Decimal("1"),
                "03": Decimal("2"),
                "04": Decimal("10000.00"),
                "05": Decimal("2500.00"),
                "06": Decimal("12500.00"),
                "07": Decimal("1900.00"),
                "08": Decimal("475.00"),
                "09": Decimal("2375.00"),
                "10": Decimal("200.00"),
                "11": Decimal("2175.00"),
            },
            id="2024-complementaria",
        ),
        pytest.param(
            MODELO_123_2025,
            "zero-boundary",
            _provided(
                **{
                    "01": "0",
                    "02": "0",
                    "03": "0",
                    "04": "0.00",
                    "05": "0.00",
                    "06": "0.00",
                    "07": "0.00",
                    "08": "0.00",
                    "09": "0.00",
                    "10": "0.00",
                    "11": "0.00",
                }
            ),
            id="2025-zero-boundary",
        ),
        pytest.param(MODELO_123_2025, "typical-irpf-19-percent", _provided(), id="2025-typical"),
        pytest.param(
            MODELO_123_2025,
            "complementaria-offset",
            _provided(
                **{
                    "07": "800.00",
                    "08": "1200.00",
                    "09": "2000.00",
                    "10": "500.00",
                    "11": "1500.00",
                }
            ),
            id="2025-complementaria",
        ),
        pytest.param(
            MODELO_123_2026,
            "zero-boundary",
            {
                "01": Decimal("0"),
                "02": Decimal("0"),
                "03": Decimal("0"),
                "04": Decimal("0.00"),
                "05": Decimal("0.00"),
                "06": Decimal("0.00"),
                "07": Decimal("0.00"),
                "08": Decimal("0.00"),
                "09": Decimal("0.00"),
                "10": Decimal("0.00"),
                "11": Decimal("0.00"),
            },
            id="2026-zero-boundary",
        ),
        pytest.param(
            MODELO_123_2026,
            "typical-irpf-19-percent",
            {
                "01": Decimal("4"),
                "02": Decimal("2"),
                "03": Decimal("6"),
                "04": Decimal("18000.00"),
                "05": Decimal("7000.00"),
                "06": Decimal("25000.00"),
                "07": Decimal("3420.00"),
                "08": Decimal("1330.00"),
                "09": Decimal("4750.00"),
                "10": Decimal("0.00"),
                "11": Decimal("4750.00"),
            },
            id="2026-typical",
        ),
        pytest.param(
            MODELO_123_2026,
            "complementaria-offset",
            {
                "01": Decimal("1"),
                "02": Decimal("2"),
                "03": Decimal("3"),
                "04": Decimal("6400.00"),
                "05": Decimal("3600.00"),
                "06": Decimal("10000.00"),
                "07": Decimal("1216.00"),
                "08": Decimal("684.00"),
                "09": Decimal("1900.00"),
                "10": Decimal("75.00"),
                "11": Decimal("1825.00"),
            },
            id="2026-complementaria",
        ),
    ],
)
def test_modelo_123_worked_examples_by_year(
    ruleset: Ruleset,
    case_id: str,
    provided: dict[str, Decimal],
) -> None:
    """BOE-anchored aggregation examples across 2024, 2025, and 2026.

    The ordinary IRPF rate examples use LIRPF art. 101.4 and RIRPF
    art. 90 (19%) to populate user-supplied casillas 07 and 08. The
    ruleset verifies the AEAT Modelo 123 liquidación arithmetic:
    03=01+02, 06=04+05, 09=07+08, 11=09-10.
    """
    report = Engine().audit_against(ruleset=ruleset, provided=provided, tolerance=Decimal("0.01"))
    assert report.is_clean(), (
        case_id,
        [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies],
    )
