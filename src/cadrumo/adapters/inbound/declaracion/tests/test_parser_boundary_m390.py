"""Modelo 390 parser boundary corpus tests."""

from __future__ import annotations

import pytest

from ._parser_boundary_support import (
    FIXTURES_DIR,
    CasillaId,
    Decimal,
    _expected_casilla_values,
    _expected_period,
    parse_declaracion,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_M390_CORPUS_PARAMS: tuple[tuple[str, int], ...] = (
    ("2022-0A", 2022),
    ("2023-0A", 2023),
)
_M390_EXPECTED: dict[str, dict[CasillaId, Decimal]] = {
    "2022-0A": _expected_casilla_values(
        {
            "iva.anual.repercutido.general": Decimal("10500.00"),
            "iva.anual.repercutido.reducido": Decimal("0.00"),
            "iva.anual.repercutido.super-reducido": Decimal("0.00"),
            "iva.anual.aic.bienes.tipo-21.cuota": Decimal("0.00"),
            "iva.anual.soportado.interiores": Decimal("8400.00"),
            "iva.anual.cuota-devengada-total": Decimal("10500.00"),
            "iva.anual.cuota-deducible-total": Decimal("8400.00"),
            "iva.anual.resultado-regimen-general": Decimal("2100.00"),
        }
    ),
    "2023-0A": _expected_casilla_values(
        {
            "iva.anual.repercutido.general": Decimal("12600.00"),
            "iva.anual.repercutido.reducido": Decimal("0.00"),
            "iva.anual.repercutido.super-reducido": Decimal("0.00"),
            "iva.anual.aic.bienes.tipo-21.cuota": Decimal("0.00"),
            "iva.anual.soportado.interiores": Decimal("9800.00"),
            "iva.anual.cuota-devengada-total": Decimal("12600.00"),
            "iva.anual.cuota-deducible-total": Decimal("9800.00"),
            "iva.anual.resultado-regimen-general": Decimal("2800.00"),
        }
    ),
}


@pytest.mark.parametrize("pdf_stem,year", _M390_CORPUS_PARAMS)
def test_parser_extracts_modelo_390_profile_targets_from_corpus(pdf_stem: str, year: int) -> None:
    """Round-trip synthetic M390 corpus fixtures through the parser."""
    expected = _M390_EXPECTED[pdf_stem]
    pdf_path = FIXTURES_DIR / "justificantes" / "390" / f"{pdf_stem}.pdf"

    filing = parse_declaracion(
        pdf_path,
        modelo_override="390",
        año_override=year,
        period_override="0A",
    )

    assert filing.modelo == "390"
    assert filing.period == _expected_period(year, "0A")
    assert filing.tax_id == "Y0000001S"
    assert filing.registry_snapshot_ref is not None
    assert filing.registry_snapshot_ref.modelo == "390"
    assert filing.registry_snapshot_ref.modelo_year == year
    assert filing.registry_snapshot_ref.period == "0A"
    assert {value.casilla_id: value.printed_value for value in filing.values} == expected
