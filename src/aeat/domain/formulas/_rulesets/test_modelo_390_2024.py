"""Unit tests for the Modelo 390 2024 IVA annual-resumen ruleset.

The 2024 ruleset is the year-master that owns ``_CASILLAS`` and
``_CITATIONS``; the 2025 and 2026 siblings re-import them. The
algebraic chain is identical across the three years because LIVA
arts. 90 / 91 / 92 / 102 / 107 / 164 and RIVA art. 71.7 were not
amended for 2024-2026. Expected values below are derived from those
articles and the AEAT Modelo 390 Instrucciones, not from the
ruleset's parameter table.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .._engine import Engine
from . import MODELO_390_2024

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _provided() -> dict[str, Decimal]:
    """Externally anchored 2024 fixture for régimen general."""
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


class TestModelo390Ruleset2024:
    def test_ruleset_id_and_effective_range(self) -> None:
        assert MODELO_390_2024.ruleset_id == "modelo_390.2024"
        assert MODELO_390_2024.effective_from == date(2024, 1, 1)
        assert MODELO_390_2024.effective_to == date(2024, 12, 31)

    def test_consistent_filing_is_clean(self) -> None:
        report = Engine().audit_against(
            ruleset=MODELO_390_2024,
            provided=_provided(),
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]

    def test_zero_filing_is_clean(self) -> None:
        """Zero-boundary: every input zero ⇒ every computed casilla 0.00."""
        report = Engine().audit_against(
            ruleset=MODELO_390_2024,
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
        """External-anchored worked example for 2024 régimen general.

        Provenance. AEAT Instrucciones del modelo 390 (ejercicio 2024)
        prescribe: 104 = 100 + 101, 105 = 96 - 104, 190 = 105 + 108 +
        109, 191 = 190 - 662, 192 = clamp_pos(191), 193 = clamp_pos(0
        - 191).

        Scenario. 2024 annual resumen with bases 95 = 60 000, cuotas
        repercutidas 96 = 12 600 (= 60 000 * 21 % per LIVA art. 90),
        IVA soportado deducible interior 100 = 5 000, importaciones
        101 = 750, no simplificado / otros, sin regularización.

        Independent arithmetic from AEAT Instrucciones:
        - 104 = 5 000 + 750 = 5 750
        - 105 = 12 600 - 5 750 = 6 850
        - 190 = 6 850 + 0 + 0 = 6 850
        - 191 = 6 850 - 0 = 6 850
        - 192 = clamp_pos(6 850) = 6 850
        - 193 = clamp_pos(0 - 6 850) = 0

        Citations: BOE-A-1992-28740 LIVA arts. 90 / 91 / 92 / 164;
        BOE-A-1992-28925 RIVA art. 71.7; BOE-A-2009-18472 Orden
        EHA/3111/2009 (modelo 390).
        """
        provided = {
            "95": Decimal("60000.00"),
            "96": Decimal("12600.00"),
            "100": Decimal("5000.00"),
            "101": Decimal("750.00"),
            "104": Decimal("5750.00"),
            "105": Decimal("6850.00"),
            "108": Decimal("0.00"),
            "109": Decimal("0.00"),
            "190": Decimal("6850.00"),
            "191": Decimal("6850.00"),
            "192": Decimal("6850.00"),
            "193": Decimal("0.00"),
            "662": Decimal("0.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_390_2024,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]

    def test_regularizacion_bienes_inversion_reduces_cuota(self) -> None:
        """LIVA art. 107: positive 662 reduces 191 toward zero."""
        provided = _provided()
        provided["662"] = Decimal("2000.00")
        provided["191"] = Decimal("5500.00")  # 7500 - 2000
        provided["192"] = Decimal("5500.00")
        provided["193"] = Decimal("0.00")
        report = Engine().audit_against(
            ruleset=MODELO_390_2024,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean()

    def test_a_devolver_when_191_is_negative(self) -> None:
        """Large 662 flips 191 negative ⇒ 192 = 0, 193 = -191."""
        provided = _provided()
        provided["662"] = Decimal("8500.00")
        provided["191"] = Decimal("-1000.00")  # 7500 - 8500
        provided["192"] = Decimal("0.00")
        provided["193"] = Decimal("1000.00")
        report = Engine().audit_against(
            ruleset=MODELO_390_2024,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean()

    def test_threshold_zero_crossing_of_191(self) -> None:
        """Boundary case: 662 == 190 ⇒ 191 == 0, both 192 and 193 are 0."""
        provided = _provided()
        provided["662"] = Decimal("7500.00")
        provided["191"] = Decimal("0.00")
        provided["192"] = Decimal("0.00")
        provided["193"] = Decimal("0.00")
        report = Engine().audit_against(
            ruleset=MODELO_390_2024,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean()

    def test_2024_no_drift_from_2025(self) -> None:
        """2024 and 2025 audit identically against the same provided values.

        Confirms the year-master pattern works: same casillas, same
        algebraic chain, only the formula identifiers and effective
        dates differ.
        """
        from . import MODELO_390_2025

        provided = _provided()
        report_2024 = Engine().audit_against(
            ruleset=MODELO_390_2024,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        report_2025 = Engine().audit_against(
            ruleset=MODELO_390_2025,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report_2024.is_clean()
        assert report_2025.is_clean()
        assert {e.casilla_id: e.value for e in report_2024.ledger.entries} == {
            e.casilla_id: e.value for e in report_2025.ledger.entries
        }

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
            ruleset=MODELO_390_2024,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert casilla_id in {d.casilla_id for d in report.discrepancies}
