"""Unit tests for the Modelo 390 2026 IVA annual-resumen ruleset.

The 2026 ruleset is a structural clone of the 2024 / 2025 rulesets
because the BOE-grounded algebraic chain is unchanged: LIVA arts.
90 / 91 / 92 / 102 / 107 / 164 and RIVA art. 71.7 were not amended
for 2026, and the 2026 small-enterprise franquicia regime
(Directiva (UE) 2020/285) is an opt-in regime outside the régimen-
general scope of this ruleset. Expected values below are derived
from those articles and the AEAT Modelo 390 Instrucciones, not from
the ruleset's parameter table.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .._engine import Engine
from . import MODELO_390_2024, MODELO_390_2025, MODELO_390_2026

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]


def _provided() -> dict[str, Decimal]:
    """Externally anchored 2026 fixture for régimen general."""
    return {
        "01": Decimal("12500.00"),
        "04": Decimal("2625.00"),
        "95": Decimal("50000.00"),
        "96": Decimal("10000.00"),
        "100": Decimal("2000.00"),
        "101": Decimal("500.00"),
        "104": Decimal("2500.00"),
        "105": Decimal("7500.00"),
        "108": Decimal("0.00"),
        "109": Decimal("0.00"),
        "190": Decimal("7500.00"),
        "191": Decimal("7500.00"),
        "192": Decimal("7500.00"),
        "193": Decimal("0.00"),
        "662": Decimal("0.00"),
    }


class TestModelo390Ruleset2026:
    def test_ruleset_id_and_effective_range(self) -> None:
        assert MODELO_390_2026.ruleset_id == "modelo_390.2026"
        assert MODELO_390_2026.effective_from == date(2026, 1, 1)
        assert MODELO_390_2026.effective_to == date(2026, 12, 31)

    def test_consistent_filing_is_clean(self) -> None:
        report = Engine().audit_against(
            ruleset=MODELO_390_2026,
            provided=_provided(),
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]

    def test_zero_filing_is_clean(self) -> None:
        report = Engine().audit_against(
            ruleset=MODELO_390_2026,
            provided={
                cid: Decimal("0.00")
                for cid in (
                    "01",
                    "04",
                    "95",
                    "96",
                    "100",
                    "101",
                    "104",
                    "105",
                    "108",
                    "109",
                    "190",
                    "191",
                    "192",
                    "193",
                    "662",
                )
            },
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean()

    def test_external_worked_example_aeat_modelo_390_instrucciones(self) -> None:
        """External-anchored worked example for 2026.

        Provenance. AEAT Instrucciones del modelo 390 (ejercicio 2026)
        prescribe the same algebraic chain as 2024 / 2025: 104 = 100
        + 101, 105 = 96 - 104, 190 = 105 + 108 + 109, 191 = 190 - 662,
        192 = clamp_pos(191), 193 = clamp_pos(0 - 191). LIVA art. 90
        keeps the 21 % general rate; LIVA art. 91 keeps the 10 % and
        4 % reduced / super-reduced rates.

        Scenario. 2026 annual resumen with bases 95 = 100 000, cuotas
        repercutidas 96 = 21 000 (= 100 000 * 21 % per LIVA art. 90),
        IVA soportado deducible interior 100 = 9 000, importaciones
        101 = 1 000, simplificado 108 = 0, otros 109 = 0,
        regularización 662 = 500 (positive — reduce cuota).

        Independent arithmetic from AEAT Instrucciones:
        - 104 = 9 000 + 1 000 = 10 000
        - 105 = 21 000 - 10 000 = 11 000
        - 190 = 11 000 + 0 + 0 = 11 000
        - 191 = 11 000 - 500 = 10 500
        - 192 = clamp_pos(10 500) = 10 500
        - 193 = clamp_pos(0 - 10 500) = 0

        Citations: BOE-A-1992-28740 LIVA arts. 90 / 91 / 92 / 107 /
        164; BOE-A-1992-28925 RIVA art. 71.7; BOE-A-2009-18472 Orden
        EHA/3111/2009 (modelo 390); DOUE-L-2020-80356 Directiva (UE)
        2020/285 — small-enterprise franquicia, opt-in regime out of
        base ruleset scope.
        """
        provided = {
            "95": Decimal("100000.00"),
            "96": Decimal("21000.00"),
            "100": Decimal("9000.00"),
            "101": Decimal("1000.00"),
            "104": Decimal("10000.00"),
            "105": Decimal("11000.00"),
            "108": Decimal("0.00"),
            "109": Decimal("0.00"),
            "190": Decimal("11000.00"),
            "191": Decimal("10500.00"),
            "192": Decimal("10500.00"),
            "193": Decimal("0.00"),
            "662": Decimal("500.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_390_2026,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]

    def test_2026_no_drift_from_2024_and_2025(self) -> None:
        """2024, 2025, and 2026 audit identically against the same provided values."""
        provided = _provided()
        reports = {
            ruleset.ruleset_id: Engine().audit_against(
                ruleset=ruleset,
                provided=provided,
                tolerance=Decimal("0.01"),
            )
            for ruleset in (MODELO_390_2024, MODELO_390_2025, MODELO_390_2026)
        }
        for ruleset_id, report in reports.items():
            assert report.is_clean(), (ruleset_id, [d.casilla_id for d in report.discrepancies])
        ledgers = {
            ruleset_id: {e.casilla_id: e.value for e in report.ledger.entries} for ruleset_id, report in reports.items()
        }
        assert ledgers["modelo_390.2024"] == ledgers["modelo_390.2025"]
        assert ledgers["modelo_390.2025"] == ledgers["modelo_390.2026"]

    def test_threshold_zero_crossing_of_191(self) -> None:
        """662 == 190 ⇒ 191 == 0, both 192 and 193 are 0."""
        provided = _provided()
        provided["662"] = Decimal("7500.00")
        provided["191"] = Decimal("0.00")
        provided["192"] = Decimal("0.00")
        provided["193"] = Decimal("0.00")
        report = Engine().audit_against(
            ruleset=MODELO_390_2026,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean()

    def test_a_devolver_flips_when_191_is_negative(self) -> None:
        provided = _provided()
        provided["662"] = Decimal("9000.00")
        provided["191"] = Decimal("-1500.00")
        provided["192"] = Decimal("0.00")
        provided["193"] = Decimal("1500.00")
        report = Engine().audit_against(
            ruleset=MODELO_390_2026,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean()

    @pytest.mark.parametrize(
        ("casilla_id", "wrong_value"),
        [
            ("104", Decimal("100.00")),
            ("105", Decimal("0.00")),
            ("190", Decimal("100.00")),
            ("191", Decimal("100.00")),
            ("192", Decimal("100.00")),
            ("193", Decimal("100.00")),
        ],
    )
    def test_audit_surfaces_drifted_casilla(
        self,
        casilla_id: str,
        wrong_value: Decimal,
    ) -> None:
        provided = _provided()
        provided[casilla_id] = wrong_value
        report = Engine().audit_against(
            ruleset=MODELO_390_2026,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert casilla_id in {d.casilla_id for d in report.discrepancies}
