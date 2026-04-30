"""Unit tests for Modelo 100 Anexo D — actividades económicas (2026).

Covers the three régimenes (E.D. normal / E.D. simplificada / módulos)
against the 2026 ruleset. External-anchored to LIRPF arts. 27-32 +
LIS arts. 12-14 + 17 + RIRPF arts. 28 + 30 + 32.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ..._engine import Engine
from .. import MODELO_100_2026

pytestmark = [pytest.mark.unit, pytest.mark.domain_submission]


def _baseline_zero_other_anexos() -> dict[str, Decimal]:
    """Zero values for B1 / B2 / C plus all D casillas not under test.

    Casilla 0021 (LIRPF art. 20 reducción del trabajo) defaults to
    7.302 € (the by-design non-zero cap on zero rendimiento) since
    the engine derives it as a constant when 0001-0019 are all zero.
    """
    return {
        # Anexo B1.
        "0001": Decimal("0.00"),
        "0008": Decimal("0.00"),
        "0009": Decimal("0.00"),
        "0010": Decimal("0.00"),
        "0019": Decimal("0.00"),
        "0020": Decimal("0.00"),
        "0021": Decimal("0.00"),
        "0022": Decimal("0.00"),
        # Anexo B2.
        "0028": Decimal("0.00"),
        "0029": Decimal("0.00"),
        "0030": Decimal("0.00"),
        "0031": Decimal("0.00"),
        "0032": Decimal("0.00"),
        "0035": Decimal("0.00"),
        "0048": Decimal("0.00"),
        "0049": Decimal("0.00"),
        # Anexo C.
        "0061": Decimal("0.00"),
        "0066": Decimal("0.00"),
        "0072": Decimal("0.00"),
        "0078": Decimal("0.00"),
        "0085": Decimal("0.00"),
        "0106": Decimal("0.00"),
        "0107": Decimal("0.00"),
        # Anexo D normal.
        "0140": Decimal("0.00"),
        "0150": Decimal("0.00"),
        "0155": Decimal("0.00"),
        "0165": Decimal("0.00"),
        "0170": Decimal("0.00"),
        "0173": Decimal("0.00"),
        "0180": Decimal("0.00"),
        "0190": Decimal("0.00"),
        "0195": Decimal("0.00"),
        "0200": Decimal("0.00"),
        "0205": Decimal("0.00"),
        # Anexo D simplificada.
        "0210": Decimal("0.00"),
        "0215": Decimal("0.00"),
        "0220": Decimal("0.00"),
        "0225": Decimal("0.00"),
        "0230": Decimal("0.00"),
        "0235": Decimal("0.00"),
        "0240": Decimal("0.00"),
        # Anexo D módulos.
        "0250": Decimal("0.00"),
        "0255": Decimal("0.00"),
        "0260": Decimal("0.00"),
    }


class TestModelo100AnexoDNormal:
    def test_consistent_p_and_l_is_clean(self) -> None:
        """Worked example E.D. normal: ingresos 80.000 - compras 20.000 -
        personal 25.000 - servicios 8.000 - amortización 3.000 -
        provisiones 500 - variación + 2.000 (existencias subieron) ->
        gastos computables = 56.500; rendimiento neto previo = 23.500;
        sin reducción art. 32 -> rendimiento neto reducido = 23.500.
        """
        provided = _baseline_zero_other_anexos() | {
            "0140": Decimal("80000.00"),
            "0150": Decimal("20000.00"),
            "0155": Decimal("2000.00"),  # existencias finales > iniciales = +
            "0165": Decimal("25000.00"),
            "0170": Decimal("8000.00"),
            "0173": Decimal("3000.00"),
            "0180": Decimal("500.00"),
            "0190": Decimal("54500.00"),  # 20000+25000+8000+3000+500 - 2000 = 54500
            "0195": Decimal("25500.00"),  # 80000 - 54500
            "0200": Decimal("0.00"),
            "0205": Decimal("25500.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_100_2026,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]

    def test_irregular_reduction_art_32_30pct(self) -> None:
        """LIRPF art. 32 30 % over rendimientos irregulares (caller supplies
        amount as 0200). Rendimiento neto previo 10.000; reducción
        3.000 -> rendimiento neto reducido 7.000.
        """
        provided = _baseline_zero_other_anexos() | {
            "0140": Decimal("10000.00"),
            "0150": Decimal("0.00"),
            "0155": Decimal("0.00"),
            "0165": Decimal("0.00"),
            "0170": Decimal("0.00"),
            "0173": Decimal("0.00"),
            "0180": Decimal("0.00"),
            "0190": Decimal("0.00"),
            "0195": Decimal("10000.00"),
            "0200": Decimal("3000.00"),
            "0205": Decimal("7000.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_100_2026,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean()

    def test_negative_p_l_clamps_to_zero(self) -> None:
        """Gastos > ingresos -> rendimiento neto previo clamps to 0."""
        provided = _baseline_zero_other_anexos() | {
            "0140": Decimal("5000.00"),
            "0150": Decimal("3000.00"),
            "0165": Decimal("4000.00"),
            "0190": Decimal("7000.00"),
            "0195": Decimal("0.00"),
            "0200": Decimal("0.00"),
            "0205": Decimal("0.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_100_2026,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean()


class TestModelo100AnexoDSimplificada:
    @pytest.mark.parametrize(
        ("ingresos", "gastos", "expected_pre_cap", "expected_dificil", "expected_neto"),
        [
            # Below cap (5 % under 2.000 €):
            (Decimal("30000.00"), Decimal("10000.00"), Decimal("20000.00"), Decimal("1000.00"), Decimal("19000.00")),
            # At cap boundary (5 % = 2.000 € exactly): rendimiento_pre_cap = 40.000
            (Decimal("50000.00"), Decimal("10000.00"), Decimal("40000.00"), Decimal("2000.00"), Decimal("38000.00")),
            # Above cap (5 % > 2.000 €): cap applies
            (Decimal("100000.00"), Decimal("20000.00"), Decimal("80000.00"), Decimal("2000.00"), Decimal("78000.00")),
            # Zero rendimiento -> zero gastos difícil
            (Decimal("5000.00"), Decimal("5000.00"), Decimal("0.00"), Decimal("0.00"), Decimal("0.00")),
            # Negative pre-cap clamps to 0 -> zero gastos difícil
            (Decimal("3000.00"), Decimal("4000.00"), Decimal("0.00"), Decimal("0.00"), Decimal("0.00")),
        ],
    )
    def test_5pct_dificil_justificacion_cap_at_2000(
        self,
        ingresos: Decimal,
        gastos: Decimal,
        expected_pre_cap: Decimal,
        expected_dificil: Decimal,
        expected_neto: Decimal,
    ) -> None:
        """RIRPF art. 30: gastos difícil justificación = min(5 % * pre-cap, 2.000).
        Verified across boundary cases.
        """
        provided = _baseline_zero_other_anexos() | {
            "0210": ingresos,
            "0215": gastos,
            "0220": expected_pre_cap,
            "0225": expected_dificil,
            "0230": expected_neto,
            "0235": Decimal("0.00"),
            "0240": expected_neto,
        }
        report = Engine().audit_against(
            ruleset=MODELO_100_2026,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]

    def test_drift_in_gastos_dificil_detected(self) -> None:
        """Mismatch on 0225 (caller exceeds the 2.000 cap) surfaces."""
        provided = _baseline_zero_other_anexos() | {
            "0210": Decimal("100000.00"),
            "0215": Decimal("20000.00"),
            "0220": Decimal("80000.00"),
            "0225": Decimal("4000.00"),  # WRONG -- exceeds 2.000 cap
            "0230": Decimal("76000.00"),
            "0235": Decimal("0.00"),
            "0240": Decimal("76000.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_100_2026,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert not report.is_clean()
        offenders = {d.casilla_id for d in report.discrepancies}
        assert "0225" in offenders


class TestModelo100AnexoDModulos:
    def test_consistent_modulos_is_clean(self) -> None:
        """Caller supplies rendimiento neto previo módulos (0250) from the
        Orden HAC tabla per actividad. The ruleset only verifies the
        reducción chain.
        """
        provided = _baseline_zero_other_anexos() | {
            "0250": Decimal("18500.00"),
            "0255": Decimal("925.00"),  # 5 % reducción incentivos al empleo
            "0260": Decimal("17575.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_100_2026,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean()

    def test_modulos_negative_clamps(self) -> None:
        """Reducción exceeds rendimiento -> clamps to 0."""
        provided = _baseline_zero_other_anexos() | {
            "0250": Decimal("500.00"),
            "0255": Decimal("800.00"),
            "0260": Decimal("0.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_100_2026,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean()
