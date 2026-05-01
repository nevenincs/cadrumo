"""Unit tests for the Modelo 111 2026 ruleset.

Issue `#318` (Tier-L per-modelo calc-verify-roundtrip): the 2026
ruleset is a structural clone of the 2024 / 2025 rulesets because
LIRPF arts. 99-101 + RIRPF arts. 99-100 were not amended for 2025 or
2026 (see the rule-delta manifest at
``.vault/reference/2026-111-rule-delta.md``). These tests assert the
no-drift invariant against the 2025 ruleset and ship an external-
anchored worked example whose expected values come from LIRPF / RIRPF
verbatim — not from the 2026 ruleset's stored parameters. A typo in
either the ruleset's parameters or the shared formulas would
therefore fail one of the cases below.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .._engine import Engine
from . import MODELO_111_2026

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _provided() -> dict[str, Decimal]:
    """Worked-example fixture for a 2T 2026 retenedor.

    Distinct numerical scenario from the 2024 / 2025 fixtures (which
    use 6 000 € premios / 500 € ganancias and 8 000 € premios / 1 000
    € ganancias respectively) to avoid mirror-fixture coupling: a 2T
    2026 employer with both rate buckets exercised plus a non-zero
    complementaria deduction on casilla 29 so the resultado-a-ingresar
    arithmetic exercises the full DAG.

    Inputs (LIRPF arts. 99-101 + RIRPF arts. 99-100):
      - Casilla 03 (retenciones rendimientos del trabajo): 2 500,00
      - Casilla 06 (retenciones actividades económicas): 900,00
      - Casilla 08 (premios percepciones): 4 500,00
      - Casilla 09 (retenciones premios = 19 % x 08): 855,00
      - Casilla 11 (ganancias percepciones): 2 500,00
      - Casilla 12 (retenciones ganancias = 19 % x 11): 475,00
      - Casilla 15 (retenciones contraprestaciones en especie): 60,00
      - Casilla 18 (retenciones cesión imagen): 30,00
      - Casilla 28 (total = 03 + 06 + 09 + 12 + 15 + 18):
        2 500 + 900 + 855 + 475 + 60 + 30 = 4 820,00
      - Casilla 29 (a deducir complementaria): 120,00
      - Casilla 30 (resultado a ingresar = 28 - 29): 4 700,00

    Every arithmetic step is traceable to LIRPF arts. 99-101 + RIRPF
    arts. 99-100; the 19 % rate comes from the statute, not from the
    ruleset's ``ParameterTable``.
    """
    return {
        "03": Decimal("2500.00"),
        "06": Decimal("900.00"),
        "08": Decimal("4500.00"),
        "09": Decimal("855.00"),
        "11": Decimal("2500.00"),
        "12": Decimal("475.00"),
        "15": Decimal("60.00"),
        "18": Decimal("30.00"),
        "28": Decimal("4820.00"),
        "29": Decimal("120.00"),
        "30": Decimal("4700.00"),
    }


class TestModelo111Ruleset2026:
    def test_consistent_quarter_is_clean(self) -> None:
        report = Engine().audit_against(
            ruleset=MODELO_111_2026,
            provided=_provided(),
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]

    def test_2026_no_drift_from_2025(self) -> None:
        """Issue `#318` invariant: 2026 audit must equal 2025 audit on identical inputs.

        LIRPF arts. 99-101 + RIRPF arts. 99-100 are unchanged across
        2025 → 2026 per the rule-delta manifest. The casillas +
        citations + formulas are shared module-level imports from
        2025. Derived values must therefore be identical.
        """
        from . import MODELO_111_2025

        provided = _provided()
        report_2025 = Engine().audit_against(
            ruleset=MODELO_111_2025,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        report_2026 = Engine().audit_against(
            ruleset=MODELO_111_2026,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert len(report_2025.ledger.entries) == len(report_2026.ledger.entries)
        derived_2025 = {e.casilla_id: e.value for e in report_2025.ledger.entries}
        derived_2026 = {e.casilla_id: e.value for e in report_2026.ledger.entries}
        assert derived_2025 == derived_2026

    def test_ruleset_id_and_effective_range(self) -> None:
        assert MODELO_111_2026.ruleset_id == "modelo_111.2026"
        assert MODELO_111_2026.effective_from == date(2026, 1, 1)
        assert MODELO_111_2026.effective_to == date(2026, 12, 31)

    def test_external_worked_example_lirpf_99_2026(self) -> None:
        """External-anchored worked example for the 2026 ruleset.

        Provenance: LIRPF (Ley 35/2006) arts. 99 + 101.7 fix the
        obligation + 19 % rate on premios en metálico; LIRPF art.
        101.2 fixes the 19 % rate on ganancias gravadas. RIRPF (RD
        439/2007) art. 99 implements the obligation hook for premios;
        RIRPF art. 100.1 fixes the 19 % rate on arrendamiento de
        bienes inmuebles urbanos. Fixture values derived from those
        rates, NOT from the ruleset's ``ParameterTable``.

        Citation: BOE-A-2006-20764 LIRPF arts. 99 + 101.2 + 101.7
        (consolidated text last update 2026-03-21; no 2025 / 2026
        amendment to these articles); BOE-A-2007-6820 RIRPF arts. 99
        + 100 (consolidated text last update 2026-02-28; RD 253/2025
        only modifies art. 69, not arts. 99-100).

        Scenario distinct from ``_provided()`` to avoid coupling: a
        3T 2026 retenedor with a focused arrendamiento scenario and
        no premios / contraprestaciones / cesión-imagen activity.
          - Casilla 03: 1 500,00 (trabajo, supplied)
          - Casilla 06: 250,00 (actividades, supplied)
          - Casilla 08: 0,00 (no premios)
          - Casilla 09: 0,00
          - Casilla 11: 12 000,00 (ganancias / arrendamiento percepciones)
          - Casilla 12: 12 000 x 0,19 = 2 280,00 (LIRPF 101.2 + RIRPF 100.1)
          - Casilla 15: 0,00
          - Casilla 18: 0,00
          - Casilla 28: 1 500 + 250 + 0 + 2 280 + 0 + 0 = 4 030,00
          - Casilla 29: 0,00
          - Casilla 30: 4 030,00
        """
        provided = {
            "03": Decimal("1500.00"),
            "06": Decimal("250.00"),
            "08": Decimal("0.00"),
            "09": Decimal("0.00"),
            "11": Decimal("12000.00"),
            "12": Decimal("2280.00"),  # 19 % per LIRPF 101.2 + RIRPF 100.1
            "15": Decimal("0.00"),
            "18": Decimal("0.00"),
            "28": Decimal("4030.00"),
            "29": Decimal("0.00"),
            "30": Decimal("4030.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_111_2026,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]

    def test_premios_retention_at_19pct(self) -> None:
        """Casilla 09 = 19 % x 08. Pure premios fixture for the 2026 path."""
        provided = {
            "03": Decimal("0.00"),
            "06": Decimal("0.00"),
            "08": Decimal("7500.00"),
            "09": Decimal("1425.00"),  # 19 % x 7 500 per LIRPF 101.7 + RIRPF 99
            "11": Decimal("0.00"),
            "12": Decimal("0.00"),
            "15": Decimal("0.00"),
            "18": Decimal("0.00"),
            "28": Decimal("1425.00"),
            "29": Decimal("0.00"),
            "30": Decimal("1425.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_111_2026,
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
            ruleset=MODELO_111_2026,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean()

    def test_resultado_complementaria_subtraction(self) -> None:
        """Casilla 30 = 28 - 29 with non-zero complementaria deduction.

        Threshold case for the ``sub_op`` chain: a non-zero
        complementaria deduction (29) reduces the resultado a
        ingresar (30) by exactly that amount.
        """
        provided = {
            "03": Decimal("3000.00"),
            "06": Decimal("0.00"),
            "08": Decimal("0.00"),
            "09": Decimal("0.00"),
            "11": Decimal("0.00"),
            "12": Decimal("0.00"),
            "15": Decimal("0.00"),
            "18": Decimal("0.00"),
            "28": Decimal("3000.00"),
            "29": Decimal("450.00"),
            "30": Decimal("2550.00"),  # 3 000 - 450
        }
        report = Engine().audit_against(
            ruleset=MODELO_111_2026,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]

    def test_arrendamiento_retention_rate_mismatch_raises(self) -> None:
        """Casilla 12 = 19 % x 11. Kent applies 17 % (50 € short on a 2 500 € base).

        Negative-path test: confirm the 2026 audit surfaces a
        casilla-12 discrepancy when the user-supplied value departs
        from the engine's re-derivation by more than the audit
        tolerance.
        """
        provided = _provided()
        provided["12"] = Decimal("425.00")  # should be 475 (19 % x 2 500)
        provided["28"] = Decimal("4770.00")  # 4 820 - 50
        provided["30"] = Decimal("4650.00")  # 4 770 - 120
        report = Engine().audit_against(
            ruleset=MODELO_111_2026,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert "12" in {d.casilla_id for d in report.discrepancies}
