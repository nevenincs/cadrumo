"""Unit tests for the Modelo 131 2026 ruleset."""

from __future__ import annotations

from decimal import Decimal

import pytest

from .._engine import Engine
from . import MODELO_131_2026

pytestmark = [pytest.mark.unit, pytest.mark.domain_submission]


_CASES: tuple[object, ...] = (
    pytest.param(
        {
            "01": Decimal("0.00"),
            "02": Decimal("0.00"),
            "03": Decimal("0.00"),
            "04": Decimal("0.00"),
            "05": Decimal("0.00"),
            "06": Decimal("0.00"),
            "07": Decimal("0.00"),
            "08": Decimal("0.00"),
            "09": Decimal("0.00"),
            "10": Decimal("0.00"),
            "11": Decimal("0.00"),
            "12": Decimal("0.00"),
            "13": Decimal("0.00"),
            "14": Decimal("0.00"),
            "15": Decimal("0.00"),
        },
        id="zero-boundary-rirpf-110",
    ),
    pytest.param(
        {
            "01": Decimal("1500.00"),
            "02": Decimal("150.00"),
            "03": Decimal("25000.00"),
            "04": Decimal("500.00"),
            "05": Decimal("10000.00"),
            "06": Decimal("200.00"),
            "07": Decimal("850.00"),
            "08": Decimal("20.00"),
            "09": Decimal("0.00"),
            "10": Decimal("830.00"),
            "11": Decimal("0.00"),
            "12": Decimal("0.00"),
            "13": Decimal("830.00"),
            "14": Decimal("0.00"),
            "15": Decimal("830.00"),
        },
        id="typical-quarter-rirpf-110",
    ),
    pytest.param(
        {
            "01": Decimal("0.00"),
            "02": Decimal("2000.00"),
            "03": Decimal("50000.00"),
            "04": Decimal("1000.00"),
            "05": Decimal("20000.00"),
            "06": Decimal("400.00"),
            "07": Decimal("3400.00"),
            "08": Decimal("500.00"),
            "09": Decimal("200.00"),
            "10": Decimal("2700.00"),
            "11": Decimal("300.00"),
            "12": Decimal("150.00"),
            "13": Decimal("2250.00"),
            "14": Decimal("600.00"),
            "15": Decimal("1650.00"),
        },
        id="coefficient-edge-rirpf-110",
    ),
)


@pytest.mark.parametrize("provided", _CASES)
def test_external_worked_examples_are_cent_exact(provided: dict[str, Decimal]) -> None:
    """RIRPF art. 110 and Orden HAC/1425/2025 arithmetic is cent-exact."""
    inputs = {c.casilla_id: provided[c.casilla_id] for c in MODELO_131_2026.casillas if not c.computed}
    derived = {
        entry.casilla_id: entry.value for entry in Engine().derive(ruleset=MODELO_131_2026, inputs=inputs).entries
    }
    for casilla in MODELO_131_2026.casillas:
        if casilla.computed:
            assert derived[casilla.casilla_id] == provided[casilla.casilla_id]
    report = Engine().audit_against(
        ruleset=MODELO_131_2026,
        provided=provided,
        tolerance=Decimal("0.01"),
    )
    assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]


def test_ruleset_shape_and_2026_citation() -> None:
    """Modelo 131 2026 registers the six computed liquidación rows."""
    computed = {c.casilla_id for c in MODELO_131_2026.casillas if c.computed}
    assert computed == {"04", "06", "07", "10", "13", "15"}
    assert {f.casilla_id for f in MODELO_131_2026.formulas} == computed
    assert any(c.article == "HAC/1425/2025" for c in MODELO_131_2026.legal_citations)
    for casilla in MODELO_131_2026.casillas:
        if casilla.computed:
            assert any(c.article == "HAC/1425/2025" for c in casilla.legal_basis)
