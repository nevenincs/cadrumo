"""Unit tests for the Modelo 390 2025 IVA annual-resumen ruleset.

Exercises :data:`aeat.domain.formulas._rulesets.MODELO_390_2025` against
:class:`aeat.domain.formulas._engine.Engine`. Expected values are
derived from LIVA arts. 90 / 91 / 92 / 102 / 107 / 164 and the AEAT
Modelo 390 Instrucciones, never from the ruleset's parameter table.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from .._engine import Engine
from . import MODELO_390_2025

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _provided() -> dict[str, Decimal]:
    """Return a consistent 2025 régimen-general filing.

    Provenance: LIVA arts. 90 (21 % general) and 91 (10 % reduced and
    4 % super-reduced) ground the rate buckets that produce casilla 96
    upstream in the quarterly Modelo 303s. Modelo 390 totals those
    annual cuotas in casilla 96 and lets casilla 104 = 100 + 101 sum
    the IVA soportado deducible. The result chain then derives:
    105 = 96 - 104 (régimen general result), 190 = 105 + 108 + 109
    (suma resultado), 191 = 190 - 662 (cuota anual after bienes-
    inversión regularización), 192 = clamp_pos(191) (a ingresar),
    193 = clamp_pos(0 - 191) (a devolver, sign-flipped).

    Returns:
        A casilla-id keyed mapping suitable for
        :meth:`aeat.domain.formulas._engine.Engine.audit_against`.
    """
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


class TestModelo390Ruleset2025:
    """Behavioural tests for the 2025 Modelo 390 ruleset variant."""

    def test_consistent_filing_is_clean(self) -> None:
        report = Engine().audit_against(
            ruleset=MODELO_390_2025,
            provided=_provided(),
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]

    def test_iva_deducible_sum(self) -> None:
        """104 = 100 + 101 (LIVA art. 92 deducción framework)."""
        provided = _provided()
        provided["104"] = Decimal("2000.00")
        report = Engine().audit_against(
            ruleset=MODELO_390_2025,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert "104" in {d.casilla_id for d in report.discrepancies}

    def test_resultado_regimen_general(self) -> None:
        """105 = 96 - 104 (LIVA arts. 90 / 91 + art. 164 autoliquidación)."""
        provided = _provided()
        provided["105"] = Decimal("5000.00")
        report = Engine().audit_against(
            ruleset=MODELO_390_2025,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert "105" in {d.casilla_id for d in report.discrepancies}

    def test_suma_resultado_with_regimenes(self) -> None:
        """190 = 105 + 108 + 109."""
        provided = _provided()
        provided["108"] = Decimal("1000.00")
        provided["109"] = Decimal("200.00")
        provided["190"] = Decimal("8700.00")
        provided["191"] = Decimal("8700.00")
        provided["192"] = Decimal("8700.00")
        report = Engine().audit_against(
            ruleset=MODELO_390_2025,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]

    def test_regularizacion_bienes_inversion_reduces_cuota(self) -> None:
        """191 = 190 - 662 (LIVA art. 107 regularización)."""
        provided = _provided()
        provided["662"] = Decimal("1500.00")
        provided["191"] = Decimal("6000.00")  # 7500 - 1500
        provided["192"] = Decimal("6000.00")
        provided["193"] = Decimal("0.00")
        report = Engine().audit_against(
            ruleset=MODELO_390_2025,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]

    def test_a_devolver_flips_when_191_is_negative(self) -> None:
        """193 = clamp_pos(0 - 191) and 192 = 0 when 191 < 0."""
        provided = _provided()
        provided["662"] = Decimal("9000.00")  # large regularización flips sign
        provided["191"] = Decimal("-1500.00")  # 7500 - 9000
        provided["192"] = Decimal("0.00")
        provided["193"] = Decimal("1500.00")
        report = Engine().audit_against(
            ruleset=MODELO_390_2025,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]

    def test_zero_filing_is_clean(self) -> None:
        """Zero-boundary: every input zero ⇒ every computed casilla 0.00."""
        report = Engine().audit_against(
            ruleset=MODELO_390_2025,
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

    def test_ruleset_shape(self) -> None:
        computed = {c.casilla_id for c in MODELO_390_2025.casillas if c.computed}
        assert computed == {"104", "105", "190", "191", "192", "193"}
        assert len(MODELO_390_2025.formulas) == 6

    def test_external_worked_example_aeat_modelo_390_instrucciones(self) -> None:
        """External-anchored worked example.

        Provenance. AEAT Instrucciones del modelo 390 prescribe:
        casilla 104 = casilla 100 + casilla 101 (total IVA soportado
        deducible operaciones interiores), casilla 105 = casilla 96 -
        casilla 104 (resultado régimen general), casilla 190 = casilla
        105 + casilla 108 + casilla 109 (suma resultado), casilla 191 =
        casilla 190 ± casilla 662 (regularización por bienes de
        inversión, LIVA art. 107), casilla 192 = casilla 191 cuando es
        positivo, en otro caso 0 (total a ingresar), casilla 193 =
        |casilla 191| cuando es negativo, en otro caso 0 (total a
        devolver).

        Scenario. A 2025 annual resumen: bases imponibles 95 =
        80 000, cuotas repercutidas 96 = 16 800 (12 000 al 21 % + 4 800
        al 10 %), IVA soportado interior 100 = 8 500, IVA soportado
        importaciones 101 = 1 500, no simplificado / otros, sin
        regularización bienes inversión.

        Independent arithmetic from AEAT Instrucciones:
        - 104 = 100 + 101 = 8 500 + 1 500 = 10 000
        - 105 = 96 - 104 = 16 800 - 10 000 = 6 800
        - 190 = 105 + 108 + 109 = 6 800 + 0 + 0 = 6 800
        - 191 = 190 - 662 = 6 800 - 0 = 6 800
        - 192 = clamp_pos(191) = 6 800
        - 193 = clamp_pos(0 - 191) = clamp_pos(-6 800) = 0

        Citations:
        - LIVA arts. 90, 91 (BOE-A-1992-28740) — rate buckets that fed 96.
        - LIVA arts. 92, 102 (BOE-A-1992-28740) — deducciones framework.
        - LIVA art. 107 (BOE-A-1992-28740) — regularización bienes
          de inversión.
        - LIVA art. 164 (BOE-A-1992-28740) — autoliquidación.
        - RIVA art. 71.7 (BOE-A-1992-28925) — resumen-anual obligation.
        - Orden EHA/3111/2009 (BOE-A-2009-18472) — Modelo 390 form.
        """
        provided = {
            "95": Decimal("80000.00"),
            "96": Decimal("16800.00"),
            "100": Decimal("8500.00"),
            "101": Decimal("1500.00"),
            "104": Decimal("10000.00"),
            "105": Decimal("6800.00"),
            "108": Decimal("0.00"),
            "109": Decimal("0.00"),
            "190": Decimal("6800.00"),
            "191": Decimal("6800.00"),
            "192": Decimal("6800.00"),
            "193": Decimal("0.00"),
            "662": Decimal("0.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_390_2025,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]

    @pytest.mark.parametrize(
        ("casilla_id", "wrong_value"),
        [
            ("104", Decimal("999.99")),
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
        """Each computed casilla surfaces a discrepancy when drifted."""
        provided = _provided()
        provided[casilla_id] = wrong_value
        report = Engine().audit_against(
            ruleset=MODELO_390_2025,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert casilla_id in {d.casilla_id for d in report.discrepancies}
