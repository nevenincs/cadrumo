"""Unit tests for the Modelo 111 2024 ruleset.

The 2024 ruleset re-imports ``_CASILLAS``, ``_CITATIONS``, and ``_FORMULAS``
from the canonical 2025 module and declares only its own ``ParameterTable``
with the 2024 effective range. These tests assert the no-drift invariant
against the 2025 ruleset and ship an externally-anchored worked example
whose expected values come from the LIRPF / RIRPF statutes verbatim — not
from the 2024 ruleset's stored parameters. A typo in either the 2024
ruleset's parameters or the shared formulas would therefore fail one of
the cases below.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .._engine import Engine
from . import MODELO_111_2024

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _provided() -> dict[str, Decimal]:
    """Worked-example fixture for a 1T 2024 retenedor.

    The numerical scenario is intentionally distinct from the 2025 / 2026
    fixtures (which use 8 000 € premios / 1 000 € arrendamientos and
    4 500 € premios / 2 500 € arrendamientos respectively) to avoid
    mirror-fixture coupling: a 1T 2024 small business with a single
    perceptor across rendimientos del trabajo + actividades económicas +
    premios + contraprestaciones en especie.

    Inputs (LIRPF arts. 99-101 + RIRPF arts. 99-100):
      - Casilla 03 (retenciones rendimientos del trabajo, supplied):
        1 200,00
      - Casilla 06 (retenciones actividades económicas, supplied):
        450,00
      - Casilla 08 (premios percepciones): 6 000,00
      - Casilla 09 (retenciones premios = 19 % x 08): 1 140,00
      - Casilla 11 (ganancias percepciones): 500,00
      - Casilla 12 (retenciones ganancias = 19 % x 11): 95,00
      - Casilla 15 (retenciones contraprestaciones en especie,
        supplied): 80,00
      - Casilla 18 (retenciones cesión imagen, supplied): 0,00
      - Casilla 28 (total = 03 + 06 + 09 + 12 + 15 + 18):
        1 200 + 450 + 1 140 + 95 + 80 + 0 = 2 965,00
      - Casilla 29 (a deducir complementaria): 0,00
      - Casilla 30 (resultado a ingresar = 28 - 29): 2 965,00

    Every arithmetic step is traceable to LIRPF arts. 99-101 + RIRPF
    arts. 99-100; the 19 % rate comes from the statute, not from the
    ruleset's ``ParameterTable``.
    """
    return {
        "03": Decimal("1200.00"),
        "06": Decimal("450.00"),
        "08": Decimal("6000.00"),
        "09": Decimal("1140.00"),
        "11": Decimal("500.00"),
        "12": Decimal("95.00"),
        "15": Decimal("80.00"),
        "18": Decimal("0.00"),
        "28": Decimal("2965.00"),
        "29": Decimal("0.00"),
        "30": Decimal("2965.00"),
    }


class TestModelo111Ruleset2024:
    """Formula-engine assertions for the 2024 Modelo 111 ruleset."""

    def test_consistent_quarter_is_clean(self) -> None:
        report = Engine().audit_against(
            ruleset=MODELO_111_2024,
            provided=_provided(),
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]

    def test_2024_no_drift_from_2025(self) -> None:
        """The 2024 audit must equal the 2025 audit on identical inputs.

        LIRPF arts. 99-101 + RIRPF arts. 99-100 are unchanged across
        2024 → 2025 per the rule-delta manifest. The casillas +
        citations + formulas are shared module-level imports from 2025.
        Derived values must therefore be identical.
        """
        from . import MODELO_111_2025

        provided = _provided()
        report_2024 = Engine().audit_against(
            ruleset=MODELO_111_2024,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        report_2025 = Engine().audit_against(
            ruleset=MODELO_111_2025,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert len(report_2024.ledger.entries) == len(report_2025.ledger.entries)
        derived_2024 = {e.casilla_id: e.value for e in report_2024.ledger.entries}
        derived_2025 = {e.casilla_id: e.value for e in report_2025.ledger.entries}
        assert derived_2024 == derived_2025

    def test_ruleset_id_and_effective_range(self) -> None:
        assert MODELO_111_2024.ruleset_id == "modelo_111.2024"
        assert MODELO_111_2024.effective_from == date(2024, 1, 1)
        assert MODELO_111_2024.effective_to == date(2024, 12, 31)

    def test_external_worked_example_lirpf_99_2024(self) -> None:
        """Externally-anchored worked example for the 2024 ruleset.

        Provenance: LIRPF (Ley 35/2006) arts. 99 + 101.7 fix the
        obligation + 19 % rate on premios en metálico; LIRPF art.
        101.2 fixes the 19 % rate on ganancias gravadas. RIRPF (RD
        439/2007) art. 99 implements the obligation hook for premios;
        RIRPF art. 100.1 fixes the 19 % rate on arrendamiento de
        bienes inmuebles urbanos. Fixture values are derived from those
        rates, NOT from the ruleset's ``ParameterTable``.

        Citation: BOE-A-2006-20764 LIRPF arts. 99 + 101.2 + 101.7;
        BOE-A-2007-6820 RIRPF arts. 99 + 100.

        Scenario distinct from :func:`_provided` to avoid coupling: a
        4T 2024 small employer with a focused premios scenario and no
        ganancias / contraprestaciones / cesión-imagen activity.
          - Casilla 03: 800,00 (trabajo retenciones, supplied)
          - Casilla 06: 0,00 (actividades, supplied)
          - Casilla 08: 10 000,00 (premios percepciones)
          - Casilla 09: 10 000 x 0,19 = 1 900,00 (LIRPF 101.7 + RIRPF 99)
          - Casilla 11: 0,00 (ganancias)
          - Casilla 12: 0,00
          - Casilla 15: 0,00
          - Casilla 18: 0,00
          - Casilla 28: 800 + 0 + 1 900 + 0 + 0 + 0 = 2 700,00
          - Casilla 29: 0,00
          - Casilla 30: 2 700,00
        """
        provided = {
            "03": Decimal("800.00"),
            "06": Decimal("0.00"),
            "08": Decimal("10000.00"),
            "09": Decimal("1900.00"),  # 19 % per LIRPF 101.7 + RIRPF 99
            "11": Decimal("0.00"),
            "12": Decimal("0.00"),
            "15": Decimal("0.00"),
            "18": Decimal("0.00"),
            "28": Decimal("2700.00"),
            "29": Decimal("0.00"),
            "30": Decimal("2700.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_111_2024,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]

    def test_zero_boundary_is_clean(self) -> None:
        """Zero-boundary case: no retenciones in any apartado."""
        provided = {
            k: Decimal("0.00")
            for k in [
                "03",
                "06",
                "08",
                "09",
                "11",
                "12",
                "15",
                "18",
                "28",
                "29",
                "30",
            ]
        }
        report = Engine().audit_against(
            ruleset=MODELO_111_2024,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean()

    def test_premios_retention_rate_mismatch_raises(self) -> None:
        """Casilla 09 = 19 % x 08; user applies 18 % (60 € short on a 6 000 € base).

        Negative-path test: confirms the 2024 audit surfaces a
        casilla-09 discrepancy when the user-supplied value departs
        from the engine's re-derivation by more than the audit
        tolerance.
        """
        provided = _provided()
        provided["09"] = Decimal("1080.00")  # should be 1 140 (19 % x 6 000)
        # Recompute downstream so we isolate the casilla-09 discrepancy.
        provided["28"] = Decimal("2905.00")  # 1 200 + 450 + 1 080 + 95 + 80 + 0
        provided["30"] = Decimal("2905.00")
        report = Engine().audit_against(
            ruleset=MODELO_111_2024,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert "09" in {d.casilla_id for d in report.discrepancies}

    def test_arrendamiento_retention_at_19pct(self) -> None:
        """Casilla 12 = 19 % x 11 — pure ganancias / arrendamiento fixture.

        Drives only the casilla-12 path. Anchored on RIRPF art. 100.1 +
        LIRPF art. 101.2.
        """
        provided = {
            "03": Decimal("0.00"),
            "06": Decimal("0.00"),
            "08": Decimal("0.00"),
            "09": Decimal("0.00"),
            "11": Decimal("4000.00"),
            "12": Decimal("760.00"),  # 19 % x 4 000
            "15": Decimal("0.00"),
            "18": Decimal("0.00"),
            "28": Decimal("760.00"),
            "29": Decimal("0.00"),
            "30": Decimal("760.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_111_2024,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]
