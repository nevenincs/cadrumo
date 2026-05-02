"""Unit tests for the Modelo 115 2026 ruleset.

The 2026 ruleset is a structural clone of the 2024 / 2025 rulesets because
RIRPF art. 100 was not amended for 2025 or 2026. These tests assert the
no-drift invariant against the 2025 ruleset and ship an externally-
anchored worked example whose expected values come from RIRPF art. 100
verbatim — not from the 2026 ruleset's stored parameters. A typo in either
the ruleset's ``irpf.arrendamientos_rate`` parameter or the formula chain
would therefore fail one of the cases below.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .._engine import Engine
from . import MODELO_115_2026

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _provided() -> dict[str, Decimal]:
    """Worked-example fixture for a Q3 2026 lessee with three landlords.

    The numerical scenario is intentionally distinct from the 2025
    fixtures (which use 12 000 € / 15 000 €) to avoid mirror-fixture
    coupling: a Q3 lessee paying rent to three landlords with both a
    small in-kind component (casilla 04) and a complementaria
    adjustment (casilla 05).

    Inputs (RIRPF art. 100 ¶ 1 — 19 % rate):
      - Casilla 01 (nº arrendadores): 3
      - Casilla 02 (base de retención): 24 000,00 EUR
      - Casilla 03 (retenciones, 19 % x 02): 24 000 x 0,19 = 4 560,00
      - Casilla 04 (ingresos a cuenta retribución en especie): 250,00
      - Casilla 05 (a deducir: complementaria): 100,00
      - Casilla 06 (resultado a ingresar): 4 560 + 250 - 100 = 4 710,00

    Every arithmetic step is traceable to RIRPF art. 100; the rate
    comes from the statute, not from the ruleset's
    ``ParameterTable``.
    """
    return {
        "01": Decimal("3"),
        "02": Decimal("24000.00"),
        "03": Decimal("4560.00"),
        "04": Decimal("250.00"),
        "05": Decimal("100.00"),
        "06": Decimal("4710.00"),
    }


class TestModelo115Ruleset2026:
    """Formula-engine assertions for the 2026 Modelo 115 ruleset."""

    def test_consistent_quarter_is_clean(self) -> None:
        report = Engine().audit_against(
            ruleset=MODELO_115_2026,
            provided=_provided(),
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]

    def test_2026_no_drift_from_2025(self) -> None:
        """The 2026 audit must equal the 2025 audit on identical inputs.

        RIRPF art. 100 is unchanged across 2025 → 2026 per the
        rule-delta manifest. The 2026 ruleset re-imports
        ``_CASILLAS``, ``_FORMULAS``, and ``_CITATIONS`` from the
        2025 module and binds the same numerical
        ``ParameterTable`` to the 2026 effective range. Derived
        values must therefore be identical.
        """
        from . import MODELO_115_2025

        provided = _provided()
        report_2025 = Engine().audit_against(
            ruleset=MODELO_115_2025,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        report_2026 = Engine().audit_against(
            ruleset=MODELO_115_2026,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert len(report_2025.ledger.entries) == len(report_2026.ledger.entries)
        derived_2025 = {e.casilla_id: e.value for e in report_2025.ledger.entries}
        derived_2026 = {e.casilla_id: e.value for e in report_2026.ledger.entries}
        assert derived_2025 == derived_2026

    def test_ruleset_id_and_effective_range(self) -> None:
        assert MODELO_115_2026.ruleset_id == "modelo_115.2026"
        assert MODELO_115_2026.effective_from == date(2026, 1, 1)
        assert MODELO_115_2026.effective_to == date(2026, 12, 31)

    def test_external_worked_example_rirpf_art_100_2026(self) -> None:
        """Externally-anchored worked example for the 2026 ruleset.

        Provenance: RD 439/2007 (RIRPF) art. 100, ¶ 1 fixes the
        19 % retention rate on rendimientos del arrendamiento o
        subarrendamiento de bienes inmuebles urbanos (verbatim
        statute: "el porcentaje del 19 por ciento sobre todos los
        conceptos que se satisfagan al arrendador, excluido el
        Impuesto sobre el Valor Añadido"). Fixture values are derived
        from that rate, NOT from the ruleset's ``ParameterTable``.

        Citation: BOE-A-2007-6820 RD 439/2007 art. 100 (no 2025 / 2026
        amendment to art. 100).

        Scenario distinct from :func:`_provided` to avoid coupling:
        a 4T 2026 lessee with a single landlord, no in-kind
        retribution, no complementaria adjustment.
          - Casilla 01: 1
          - Casilla 02: 9 500,00
          - Casilla 03: 9 500 x 0,19 = 1 805,00 (RIRPF 100 ¶ 1)
          - Casilla 04: 0,00
          - Casilla 05: 0,00
          - Casilla 06: 1 805 + 0 - 0 = 1 805,00
        """
        provided = {
            "01": Decimal("1"),
            "02": Decimal("9500.00"),
            "03": Decimal("1805.00"),  # 19 % per RIRPF 100 ¶ 1
            "04": Decimal("0.00"),
            "05": Decimal("0.00"),
            "06": Decimal("1805.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_115_2026,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]

    def test_zero_boundary_is_clean(self) -> None:
        """Zero-boundary case: no rent paid, no retention.

        Confirms that a quarter with zero base de retención
        produces zero retención and zero resultado a ingresar
        without surfacing a spurious discrepancy. The retención-
        base / resultado pair is the entire computed surface for
        Modelo 115; the zero boundary therefore covers the full
        formula DAG with the smallest non-trivial input.
        """
        provided = {
            "01": Decimal("0"),
            "02": Decimal("0.00"),
            "03": Decimal("0.00"),
            "04": Decimal("0.00"),
            "05": Decimal("0.00"),
            "06": Decimal("0.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_115_2026,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean()

    def test_retention_rate_mismatch_raises(self) -> None:
        """Casilla 03 = 19 % x 02; user applies 18 % (under by 240 €).

        Negative-path test: confirms the 2026 audit surfaces a
        casilla-03 discrepancy when the user-supplied value
        departs from the engine's re-derivation by more than the
        audit tolerance.
        """
        provided = _provided()
        provided["03"] = Decimal("4320.00")  # should be 4 560,00 (19 % x 24 000)
        provided["06"] = Decimal("4470.00")  # downstream propagation
        report = Engine().audit_against(
            ruleset=MODELO_115_2026,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert "03" in {d.casilla_id for d in report.discrepancies}

    def test_ceuta_melilla_fixture_validates_against_base_rate(self) -> None:
        """Caller-gated Ceuta / Melilla 60 % overlay does not change the base rate.

        RIRPF art. 100 ¶ 2 prescribes a 60 % reduction on the
        retention rate when the inmueble urbano is in Ceuta or
        Melilla. The base ruleset preserves the 19 % rate — the
        overlay is caller-gated (the ruleset does not own the
        territoriality flag). This test confirms that an audit on
        a non-Ceuta / Melilla quarter returns clean against the base
        19 % rate.
        """
        # 02 = 5 000,00 → 03 = 5 000 x 0,19 = 950,00 (statute base rate).
        provided = {
            "01": Decimal("1"),
            "02": Decimal("5000.00"),
            "03": Decimal("950.00"),
            "04": Decimal("0.00"),
            "05": Decimal("0.00"),
            "06": Decimal("950.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_115_2026,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]


# Parametrised per-base-amount cases for casilla 03 + casilla 06 exercised
# through the 2026 path. The 19 % retention rate (RIRPF art. 100 ¶ 1) is
# stable across 2024 → 2025 → 2026 per the rule-delta manifest; these
# cases pin the cent-exact derivations against externally-anchored
# expected values.
@pytest.mark.parametrize(
    ("base", "ingresos_especie", "complementaria", "expected_03", "expected_06"),
    [
        (Decimal("0.00"), Decimal("0.00"), Decimal("0.00"), Decimal("0.00"), Decimal("0.00")),
        (Decimal("100.00"), Decimal("0.00"), Decimal("0.00"), Decimal("19.00"), Decimal("19.00")),
        (Decimal("1000.00"), Decimal("0.00"), Decimal("0.00"), Decimal("190.00"), Decimal("190.00")),
        (Decimal("12000.00"), Decimal("0.00"), Decimal("0.00"), Decimal("2280.00"), Decimal("2280.00")),
        (Decimal("12000.00"), Decimal("100.00"), Decimal("50.00"), Decimal("2280.00"), Decimal("2330.00")),
        (Decimal("48000.00"), Decimal("0.00"), Decimal("0.00"), Decimal("9120.00"), Decimal("9120.00")),
    ],
)
def test_casilla_derivations_at_various_bases_2026(
    base: Decimal,
    ingresos_especie: Decimal,
    complementaria: Decimal,
    expected_03: Decimal,
    expected_06: Decimal,
) -> None:
    """Cent-exact derivations of casillas 03 and 06 across base amounts.

    Each row anchors the expected values to the statute (RIRPF
    art. 100 ¶ 1 — 19 %) and the resultado-a-ingresar formula
    (06 = 03 + 04 - 05). The audit must run clean for every row;
    a typo in the ruleset's ``irpf.arrendamientos_rate`` parameter
    would surface a casilla-03 discrepancy here.
    """
    provided = {
        "01": Decimal("1"),
        "02": base,
        "03": expected_03,
        "04": ingresos_especie,
        "05": complementaria,
        "06": expected_06,
    }
    report = Engine().audit_against(
        ruleset=MODELO_115_2026,
        provided=provided,
        tolerance=Decimal("0.01"),
    )
    assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]
