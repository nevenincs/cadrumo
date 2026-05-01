"""Cumulation tests for Modelo 390 (annual IVA resumen).

Modelo 390 is structurally an annual aggregator of the four quarterly
Modelo 303 filings. The ADR
``2026-04-27-modelo-390-calc-verify-adr.md`` chooses Approach C: the
cumulated casillas (``95``, ``96``, ``100``, ``101``, ``108``,
``109``, ``662``) stay user-supplied, and the M390 ruleset only
encodes the algebraic relationships among them.

These tests assert cumulation correctness at the *test* level: a
parametrised case configures four quarterly Modelo 303 inputs, runs
the M303 engine for each quarter, sums the per-quarter results into
the corresponding annual M390 casillas, and verifies that the M390
ruleset audits cleanly against those sums.

Cumulation rule encoded by these tests (per AEAT Modelo 390
Instrucciones):

- M390 casilla ``95`` (total bases imponibles) = sum of M303 bases
  per rate bucket: ``Σ_q (01 + 04 + 07)``.
- M390 casilla ``96`` (total cuotas repercutidas) = ``Σ_q (03 + 06 +
  09)``.
- M390 casilla ``100`` (total IVA soportado interior) = ``Σ_q 29``
  (deducible operaciones interiores corrientes).
- M390 casilla ``101`` (total IVA soportado importaciones) = ``Σ_q
  33`` (deducible importaciones corrientes).
- M390 casilla ``108`` (régimen simplificado) = 0 in this scope
  (régimen general only).
- M390 casilla ``109`` (otros regímenes) = 0 in this scope.
- M390 casilla ``662`` (regularización bienes inversión) = annual
  user-supplied figure; not a sum of quarterly casillas.

The M390 ruleset then derives ``104`` / ``105`` / ``190`` / ``191`` /
``192`` / ``193`` cleanly when the user-supplied annual aggregates
match the quarterly cumulation.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

import pytest

from .._engine import Engine
from .._ruleset import Ruleset
from . import (
    MODELO_303_2024,
    MODELO_303_2025,
    MODELO_303_2026,
    MODELO_390_2024,
    MODELO_390_2025,
    MODELO_390_2026,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _quarterly_inputs(*, base_general: Decimal, base_reducido: Decimal, base_super: Decimal) -> dict[str, Decimal]:
    """Return Modelo 303 inputs for a régimen-general quarter.

    Bases are taxpayer-supplied; the ruleset derives every cuota at
    the LIVA art. 90 / 91 rates plus the result chain. Casilla ``65``
    defaults to 100 (full attribution to Territorio Común).
    """
    return {
        "01": base_super,
        "04": base_reducido,
        "07": base_general,
        "65": Decimal("100"),
    }


def _derive_quarter(ruleset: Ruleset, inputs: Mapping[str, Decimal]) -> dict[str, Decimal]:
    """Run the M303 engine for one quarter and return the value map."""
    ledger = Engine().derive(ruleset=ruleset, inputs=dict(inputs))
    derived: dict[str, Decimal] = dict(inputs)
    for entry in ledger.entries:
        derived[entry.casilla_id] = entry.value
    return derived


def _cumulate_to_annual(
    quarters: list[dict[str, Decimal]],
    *,
    bienes_inversion_adjust: Decimal = Decimal("0"),
) -> dict[str, Decimal]:
    """Sum four M303 quarterly value maps into the M390 annual surface.

    Every M303 quarterly result map is normalised to the M390 annual
    casilla layout per the cumulation rule documented at the top of
    this module.
    """

    def _csum(casilla_id: str) -> Decimal:
        return sum((q.get(casilla_id, Decimal("0")) for q in quarters), start=Decimal("0"))

    bases_imponibles = _csum("01") + _csum("04") + _csum("07")
    cuotas_repercutidas = _csum("03") + _csum("06") + _csum("09")
    iva_interior = _csum("29")
    iva_importaciones = _csum("33")

    cuota_104 = iva_interior + iva_importaciones
    resultado_105 = cuotas_repercutidas - cuota_104
    suma_190 = resultado_105
    cuota_191 = suma_190 - bienes_inversion_adjust
    a_ingresar_192 = cuota_191 if cuota_191 > Decimal("0") else Decimal("0")
    a_devolver_193 = -cuota_191 if cuota_191 < Decimal("0") else Decimal("0")

    return {
        "01": Decimal("0.00"),  # statistical Q1 mirror; not part of cumulation
        "04": Decimal("0.00"),
        "95": bases_imponibles,
        "96": cuotas_repercutidas,
        "100": iva_interior,
        "101": iva_importaciones,
        "104": cuota_104,
        "105": resultado_105,
        "108": Decimal("0.00"),
        "109": Decimal("0.00"),
        "190": suma_190,
        "191": cuota_191,
        "192": a_ingresar_192,
        "193": a_devolver_193,
        "662": bienes_inversion_adjust,
    }


@pytest.mark.parametrize(
    "year_pair",
    [
        (MODELO_303_2024, MODELO_390_2024),
        (MODELO_303_2025, MODELO_390_2025),
        (MODELO_303_2026, MODELO_390_2026),
    ],
    ids=lambda pair: pair[1].ruleset_id,
)
class TestModelo390CumulationFromModelo303:
    """Annual M390 casillas equal Σ quarterly M303 casillas; M390 audits cleanly."""

    def test_uniform_quarters_cumulate_cleanly(self, year_pair: tuple[Ruleset, Ruleset]) -> None:
        """Four identical quarters at LIVA art. 90 / 91 rates round-trip."""
        m303, m390 = year_pair
        quarter_inputs = _quarterly_inputs(
            base_general=Decimal("10000.00"),
            base_reducido=Decimal("2000.00"),
            base_super=Decimal("500.00"),
        )
        quarters = [_derive_quarter(m303, quarter_inputs) for _ in range(4)]

        annual = _cumulate_to_annual(quarters)
        # Cumulation invariant: 96 = sum(03 + 06 + 09) per quarter * 4 quarters
        # = 4 * (500*0.04 + 2000*0.10 + 10000*0.21) = 4 * (20 + 200 + 2100)
        # = 4 * 2320 = 9 280 EUR.
        assert annual["96"] == Decimal("9280.00")
        # 95 = sum bases = 4 * (500 + 2000 + 10000) = 4 * 12500 = 50 000 EUR.
        assert annual["95"] == Decimal("50000.00")

        report = Engine().audit_against(
            ruleset=m390,
            provided=annual,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]

    def test_mixed_quarters_with_imports_cumulate_cleanly(
        self,
        year_pair: tuple[Ruleset, Ruleset],
    ) -> None:
        """Per-quarter variance + import VAT round-trips into M390."""
        m303, m390 = year_pair
        quarters = [
            _derive_quarter(
                m303,
                {
                    **_quarterly_inputs(
                        base_general=Decimal("8000.00"),
                        base_reducido=Decimal("1000.00"),
                        base_super=Decimal("0.00"),
                    ),
                    "29": Decimal("250.00"),
                    "33": Decimal("100.00"),
                },
            ),
            _derive_quarter(
                m303,
                {
                    **_quarterly_inputs(
                        base_general=Decimal("12000.00"),
                        base_reducido=Decimal("3000.00"),
                        base_super=Decimal("250.00"),
                    ),
                    "29": Decimal("400.00"),
                },
            ),
            _derive_quarter(
                m303,
                {
                    **_quarterly_inputs(
                        base_general=Decimal("9500.00"),
                        base_reducido=Decimal("2500.00"),
                        base_super=Decimal("0.00"),
                    ),
                    "29": Decimal("300.00"),
                    "33": Decimal("50.00"),
                },
            ),
            _derive_quarter(
                m303,
                {
                    **_quarterly_inputs(
                        base_general=Decimal("11000.00"),
                        base_reducido=Decimal("0.00"),
                        base_super=Decimal("0.00"),
                    ),
                    "29": Decimal("200.00"),
                },
            ),
        ]

        annual = _cumulate_to_annual(quarters)
        report = Engine().audit_against(
            ruleset=m390,
            provided=annual,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]

    def test_cumulation_with_regularizacion_flips_191(
        self,
        year_pair: tuple[Ruleset, Ruleset],
    ) -> None:
        """Annual 662 adjustment large enough to flip 191 from positive to negative.

        Cumulation-edge case: four quarters that net to a small
        positive régimen-general result, then a bienes-inversión
        regularización absorbs the cuota and turns 191 negative,
        triggering 193 (a devolver).
        """
        m303, m390 = year_pair
        quarter_inputs = _quarterly_inputs(
            base_general=Decimal("1000.00"),
            base_reducido=Decimal("0.00"),
            base_super=Decimal("0.00"),
        )
        quarters = [_derive_quarter(m303, quarter_inputs) for _ in range(4)]
        # 96 cumulated = 4 * 210 = 840. With 0 deducible, 191 = 840.
        # 662 = 1000 flips 191 to -160 ⇒ 192 = 0, 193 = 160.
        annual = _cumulate_to_annual(quarters, bienes_inversion_adjust=Decimal("1000.00"))
        assert annual["191"] == Decimal("-160.00")
        assert annual["192"] == Decimal("0.00")
        assert annual["193"] == Decimal("160.00")

        report = Engine().audit_against(
            ruleset=m390,
            provided=annual,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]

    def test_drifted_annual_sum_surfaces_discrepancy(
        self,
        year_pair: tuple[Ruleset, Ruleset],
    ) -> None:
        """If Kent mistypes the annual aggregate, M390 surfaces a discrepancy."""
        m303, m390 = year_pair
        quarter_inputs = _quarterly_inputs(
            base_general=Decimal("10000.00"),
            base_reducido=Decimal("0.00"),
            base_super=Decimal("0.00"),
        )
        quarters = [_derive_quarter(m303, quarter_inputs) for _ in range(4)]
        annual = _cumulate_to_annual(quarters)
        # Tamper with 105 — it should be 8400, drift it to 0.
        annual["105"] = Decimal("0.00")
        report = Engine().audit_against(
            ruleset=m390,
            provided=annual,
            tolerance=Decimal("0.01"),
        )
        assert "105" in {d.casilla_id for d in report.discrepancies}
