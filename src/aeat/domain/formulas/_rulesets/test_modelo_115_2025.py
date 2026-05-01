"""Unit tests for the Modelo 115 2025 ruleset."""

from __future__ import annotations

from decimal import Decimal

import pytest

from .._engine import Engine
from . import MODELO_115_2025

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


class TestModelo115Ruleset:
    def test_matches_published_values_is_clean(self) -> None:
        provided = {
            "01": Decimal("2"),
            "02": Decimal("12000.00"),
            "03": Decimal("2280.00"),
            "04": Decimal("0.00"),
            "05": Decimal("0.00"),
            "06": Decimal("2280.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_115_2025,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean()

    def test_retention_percent_mismatch_reported(self) -> None:
        # Kent typos 2280 → 2300 (off by ~20€ vs. 19% of 12000).
        provided = {
            "01": Decimal("2"),
            "02": Decimal("12000.00"),
            "03": Decimal("2300.00"),
            "04": Decimal("0.00"),
            "05": Decimal("0.00"),
            "06": Decimal("2300.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_115_2025,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert not report.is_clean()
        offenders = {d.casilla_id for d in report.discrepancies}
        assert "03" in offenders

    def test_resultado_a_ingresar_formula(self) -> None:
        # 06 should be 03 + 04 - 05 = 2280 + 100 - 50 = 2330.
        provided = {
            "02": Decimal("12000.00"),
            "03": Decimal("2280.00"),
            "04": Decimal("100.00"),
            "05": Decimal("50.00"),
            "06": Decimal("2330.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_115_2025,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean()

    def test_includes_reglamento_and_ley_citations(self) -> None:
        # RIRPF art. 100 has NO sub-letter structure
        # in the BOE consolidated text (BOE-A-2007-6820). The 19% rate on
        # arrendamientos urbanos lives in art. 100.1; art. 100.2 carries
        # the Ceuta/Melilla 60% reduction. The prior that
        # the rate lived in "art. 100.3.a" was factually wrong — corrected
        # across ruleset + tests in /68.
        articles = {c.article for c in MODELO_115_2025.legal_citations}
        assert "100.1" in articles  # Reglamento: fija el 19%
        assert "101.8" in articles  # LIRPF: delega el tipo al reglamento

    def test_external_worked_example_rirpf_100_1(self) -> None:
        """External-anchored worked example (closure;
        citation corrected ).

        Provenance: RD 439/2007 (RIRPF) art. 100.1 fixes the 19%
        retención rate on rendimientos del arrendamiento o
        subarrendamiento de bienes inmuebles urbanos (quote: "el
        porcentaje del 19 por ciento sobre todos los conceptos que
        se satisfagan al arrendador, excluido el Impuesto sobre el
        Valor Añadido"). LIRPF art. 101.8 hooks the obligation. This
        fixture derives the expected retención + resultado values
        from the statutory 19% rate independently of the ruleset's
        `irpf.arrendamientos_rate` parameter. BOE-A-2007-6820
        consolidated retrieval 2026-04-22.

        Prior-wave miscite (tracked): art. 100.3.a —
        invalid; RIRPF art. 100 has no sub-letter structure.
        Corrected in .

        Scenario: Q3 2025 Kent leasing a commercial premise:
        - 01 perceptores = 1 (single landlord).
        - 02 base = 15 000.
        - 03 retención = 15 000 x 19% = 2 850 per RIRPF 100.1.
        - 04 ingresos especie = 0.
        - 05 complementaria = 0.
        - 06 resultado = 03 + 04 - 05 = 2 850.
        """
        provided = {
            "01": Decimal("1"),
            "02": Decimal("15000.00"),
            "03": Decimal("2850.00"),  # 19% per RIRPF 100.1, NOT from ruleset
            "04": Decimal("0.00"),
            "05": Decimal("0.00"),
            "06": Decimal("2850.00"),
        }
        report = Engine().audit_against(ruleset=MODELO_115_2025, provided=provided, tolerance=Decimal("0.01"))
        assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]
