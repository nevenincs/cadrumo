"""Cover Modelo 100 Anexo B1 (rendimientos del trabajo) for the 2025 ejercicio.

Worked examples are externally anchored to LIRPF arts. 17-20 (post
Real Decreto-Ley 4/2024 with effects 1/1/2024). Every expected value
is derived directly from the statutory text rather than the ruleset's
own formulas, so a mis-implementation of the piecewise reducción
would fail the suite.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ..._engine import Engine
from .. import MODELO_100_2025

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _provided(rendimiento: Decimal, *, reduccion_art_20: Decimal) -> dict[str, Decimal]:
    """Build a fixture where ingresos == rendimiento and gastos == 0.

    Decouples the rendimiento-neto-previo computation (casilla 0020)
    from the inputs so reducción art. 20 (casilla 0021) and the final
    rendimiento neto reducido (casilla 0022) can be tested
    independently of the input arithmetic.
    """
    return {
        "0001": rendimiento,
        "0008": Decimal("0.00"),
        "0009": Decimal("0.00"),
        "0010": Decimal("0.00"),
        "0019": Decimal("0.00"),
        "0020": rendimiento,
        "0021": reduccion_art_20,
        "0022": max(Decimal("0.00"), rendimiento - reduccion_art_20),
    }


class TestModelo100AnexoB1:
    """Audit Anexo B1 against the 2025 ruleset using LIRPF-derived anchors."""

    def test_ruleset_id_and_default_variant(self) -> None:
        """Full-form ruleset uses the default variant slot."""
        assert MODELO_100_2025.ruleset_id == "modelo_100.2025"
        assert MODELO_100_2025.variant == "default"

    def test_consistent_filing_is_clean(self) -> None:
        """Worked example: ingresos 15.000 - SS 1.000 - otros 500 → 13.500.
        Rendimiento ≤ 14.852 → reducción 7.302; final 13.500 - 7.302 = 6.198.
        """
        provided = {
            "0001": Decimal("15000.00"),
            "0008": Decimal("1000.00"),
            "0009": Decimal("500.00"),
            "0010": Decimal("0.00"),
            "0019": Decimal("0.00"),
            "0020": Decimal("13500.00"),
            "0021": Decimal("7302.00"),
            "0022": Decimal("6198.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_100_2025,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]

    @pytest.mark.parametrize(
        ("rendimiento", "expected_reduccion", "anchor"),
        [
            # LIRPF art. 20 piecewise (RD-Ley 4/2024 vigent 1/1/2024,
            # unchanged 2025): four anchor points + below/above caps.
            # Post M-1 cap fix: reduccion = min(rendimiento, max(piece_a, piece_b))
            # so at rendimiento=0 the cap reduces 7302 -> 0; at rendimiento=5000
            # the cap reduces 7302 -> 5000; at rendimiento=10000 the cap is
            # inactive (10000 > 7302) so the full 7302 applies.
            (Decimal("0.00"), Decimal("0.00"), "zero rendimiento (capped to 0)"),
            (Decimal("5000.00"), Decimal("5000.00"), "below 7302 cap (capped to rendimiento)"),
            (Decimal("10000.00"), Decimal("7302.00"), "above 7302 cap, below first threshold"),
            (Decimal("14852.00"), Decimal("7302.00"), "boundary 1 (piece_a max)"),
            # piece_a active 14.852 → 17.673,52 with slope 1,75:
            (Decimal("16000.00"), Decimal("5293.00"), "middle of piece_a"),
            (Decimal("17673.52"), Decimal("2364.34"), "boundary 2 (piece_a meets piece_b)"),
            # piece_b active 17.673,52 → 19.747,50 with slope 1,14:
            (Decimal("18000.00"), Decimal("1992.15"), "middle of piece_b"),
            (Decimal("19747.50"), Decimal("0.00"), "boundary 3 (piece_b zero)"),
            (Decimal("25000.00"), Decimal("0.00"), "above all boundaries"),
        ],
    )
    def test_reduccion_art_20_piecewise(
        self,
        rendimiento: Decimal,
        expected_reduccion: Decimal,
        anchor: str,
    ) -> None:
        """LIRPF art. 20 reducción computed correctly at every piecewise anchor.

        Anchors correspond to: zero / below-piece-A / piece-A boundary / mid
        piece-A / piece-A→piece-B handoff / mid piece-B / piece-B zero
        boundary / above-cap. All values derived from the statutory text
        ``7302 - 1.75 * max(0, rendimiento - 14852)`` for piece_a and
        ``2364.34 - 1.14 * max(0, rendimiento - 17673.52)`` for piece_b,
        with ``max_op`` selecting the active piece.
        """
        del anchor
        report = Engine().audit_against(
            ruleset=MODELO_100_2025,
            provided=_provided(rendimiento, reduccion_art_20=expected_reduccion),
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]

    def test_zero_boundary_is_clean(self) -> None:
        """All inputs = 0 → reducción art. 20 capped at rendimiento previo (= 0).

        Post M-1 cap fix: reduccion art. 20 = min(0020, max(piece_a, piece_b)).
        At 0020=0 the cap reduces the 7302 piece_a value to 0; the
        rendimiento neto reducido (0022) is clamp_pos(0-0) = 0.
        """
        provided = {
            "0001": Decimal("0.00"),
            "0008": Decimal("0.00"),
            "0009": Decimal("0.00"),
            "0010": Decimal("0.00"),
            "0019": Decimal("0.00"),
            "0020": Decimal("0.00"),
            "0021": Decimal("0.00"),
            "0022": Decimal("0.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_100_2025,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]

    def test_rendimiento_neto_previo_clamps_negative(self) -> None:
        """When gastos exceed ingresos the rendimiento neto previo clamps to 0."""
        provided = {
            "0001": Decimal("5000.00"),
            "0008": Decimal("3000.00"),
            "0009": Decimal("3000.00"),
            "0010": Decimal("0.00"),
            "0019": Decimal("0.00"),
            "0020": Decimal("0.00"),  # clamp_pos(5000 - 3000 - 3000) = 0
            "0021": Decimal("0.00"),  # post M-1 cap: min(0020=0, max=7302) = 0
            "0022": Decimal("0.00"),  # clamp_pos(0 - 0) = 0
        }
        report = Engine().audit_against(
            ruleset=MODELO_100_2025,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]

    def test_drift_in_rendimiento_neto_previo_detected(self) -> None:
        """Mismatch on 0020 surfaces as a discrepancy."""
        provided = {
            "0001": Decimal("15000.00"),
            "0008": Decimal("1000.00"),
            "0009": Decimal("500.00"),
            "0010": Decimal("0.00"),
            "0019": Decimal("0.00"),
            "0020": Decimal("13000.00"),  # WRONG — should be 13500
            "0021": Decimal("7302.00"),
            "0022": Decimal("6198.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_100_2025,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert not report.is_clean()
        offenders = {d.casilla_id for d in report.discrepancies}
        assert "0020" in offenders

    def test_drift_in_reduccion_art_20_detected(self) -> None:
        """Mismatch on 0021 surfaces as a discrepancy."""
        provided = {
            "0001": Decimal("18000.00"),
            "0008": Decimal("0.00"),
            "0009": Decimal("0.00"),
            "0010": Decimal("0.00"),
            "0019": Decimal("0.00"),
            "0020": Decimal("18000.00"),
            "0021": Decimal("2200.00"),  # WRONG — should be 1992.15
            "0022": Decimal("16000.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_100_2025,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert not report.is_clean()
        offenders = {d.casilla_id for d in report.discrepancies}
        assert "0021" in offenders

    def test_b1_casillas_present(self) -> None:
        """B1 casillas must remain in the aggregated full-form ruleset."""
        computed = {c.casilla_id for c in MODELO_100_2025.casillas if c.computed}
        assert {"0020", "0021", "0022"}.issubset(computed)
        formula_ids = {fd.formula_id for fd in MODELO_100_2025.formulas}
        assert "modelo_100.2025.b1.rendimiento_neto_previo" in formula_ids
        assert "modelo_100.2025.b1.reduccion_art_20" in formula_ids
        assert "modelo_100.2025.b1.rendimiento_neto_reducido" in formula_ids

    def test_external_worked_example_lirpf_art_20_post_rd_ley_4_2024(self) -> None:
        """External anchor — LIRPF art. 20 post RD-Ley 4/2024.

        Provenance (BOE-A-2024-13066 RD-Ley 4/2024 + BOE-A-2006-20764
        consolidated LIRPF text): art. 20 fixes reducción
        rendimientos del trabajo at 7.302 € for rendimientos previos
        ≤ 14.852 €, decreasing linearly with slope 1,75 to 17.673,52 €
        (where reducción = 2.364,34 €) and then linearly with slope 1,14
        to 19.747,50 € (where reducción = 0). Above 19.747,50 €
        rendimientos do not benefit from the reducción.

        Scenario: Kent 2025 con Anexo B1 — ingresos íntegros del trabajo
        24.000 €, cotización SS 1.512 €, otros gastos 2.000 €, sin
        movilidad ni rendimientos irregulares.

        Statutory derivation:
          - Casilla 0020 (rendimiento neto previo) = 24.000 - 1.512 - 2.000
            = 20.488 €.
          - Casilla 0021 (reducción art. 20): rendimiento 20.488 > 19.747,50
            → reducción = 0 (above the piecewise function's zero point).
          - Casilla 0022 (rendimiento neto reducido) = 20.488 - 0 = 20.488 €.
        """
        provided = {
            "0001": Decimal("24000.00"),
            "0008": Decimal("1512.00"),
            "0009": Decimal("2000.00"),
            "0010": Decimal("0.00"),
            "0019": Decimal("0.00"),
            "0020": Decimal("20488.00"),
            "0021": Decimal("0.00"),
            "0022": Decimal("20488.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_100_2025,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]
