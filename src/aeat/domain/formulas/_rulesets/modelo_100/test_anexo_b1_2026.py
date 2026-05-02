"""Cover Modelo 100 Anexo B1 (rendimientos del trabajo) for the 2026 ejercicio.

Ejercicio 2026 inherits the 2025 numerical surface for arts. 17-20
because no posterior law modification has been published in the
consolidated BOE text. The 2026 ruleset is a structural clone with
year-scoped formula IDs and 2026 effective dates, so this suite
verifies the same anchors against
:data:`aeat.domain.formulas._rulesets.modelo_100.MODELO_100_2026`.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ..._engine import Engine
from .. import MODELO_100_2026

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


class TestModelo100AnexoB1:
    """Audit Anexo B1 against the 2026 ruleset using LIRPF-derived anchors."""

    def test_ruleset_id_and_default_variant(self) -> None:
        """The 2026 full-form ruleset uses the default variant slot."""
        assert MODELO_100_2026.ruleset_id == "modelo_100.2026"
        assert MODELO_100_2026.variant == "default"

    def test_consistent_filing_is_clean(self) -> None:
        """Same scenario as 2025 — 2026 inherits per BOE consult 2026-02-28."""
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
            ruleset=MODELO_100_2026,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]

    def test_no_drift_from_2025(self) -> None:
        """Regression: 2026 ruleset produces identical audit to 2025 on the
        same fixture (when no BOE delta exists).
        """
        from .. import MODELO_100_2025

        provided = {
            "0001": Decimal("18000.00"),
            "0008": Decimal("0.00"),
            "0009": Decimal("0.00"),
            "0010": Decimal("0.00"),
            "0019": Decimal("0.00"),
            "0020": Decimal("18000.00"),
            "0021": Decimal("1992.15"),
            "0022": Decimal("16007.85"),
        }
        engine = Engine()
        report_2025 = engine.audit_against(ruleset=MODELO_100_2025, provided=provided, tolerance=Decimal("0.01"))
        report_2026 = engine.audit_against(ruleset=MODELO_100_2026, provided=provided, tolerance=Decimal("0.01"))
        assert report_2025.is_clean()
        assert report_2026.is_clean()

    def test_b1_casillas_present(self) -> None:
        """B1 casillas must remain in the aggregated full-form ruleset."""
        computed = {c.casilla_id for c in MODELO_100_2026.casillas if c.computed}
        assert {"0020", "0021", "0022"}.issubset(computed)
        formula_ids = {fd.formula_id for fd in MODELO_100_2026.formulas}
        assert "modelo_100.2026.b1.rendimiento_neto_previo" in formula_ids
        assert "modelo_100.2026.b1.reduccion_art_20" in formula_ids
        assert "modelo_100.2026.b1.rendimiento_neto_reducido" in formula_ids
