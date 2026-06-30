"""Modelo 303 parser boundary tests for the 2023-2024 printed template."""

from __future__ import annotations

import pytest

from ._parser_boundary_part2_support import (
    _M303_CASILLA_27,
    _M303_CASILLA_29,
    _M303_CASILLA_37,
    _M303_CASILLA_45,
    _M303_CASILLA_64,
    _M303_CASILLA_66,
    _M303_CASILLA_71,
    _M303_COMPENSACION_ANTERIORES_CASILLA,
    _M303_COMPENSACION_APLICADA_CASILLA,
    _M303_COMPENSACION_POSTERIORES_CASILLA,
    _M303_RESULTADO_CASILLA,
    _M303_RESULTADO_REGIMEN_GENERAL_CASILLA,
)
from ._parser_boundary_support import (
    FIXTURES_DIR,
    CasillaId,
    Decimal,
    _casilla_id,
    _expected_casilla_values,
    _expected_period,
    parse_declaracion,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_M303_2023_2024_PARAMS: tuple[tuple[str, int, str], ...] = (
    ("2023-1T", 2023, "1T"),
    ("2023-2T", 2023, "2T"),
    ("2023-3T", 2023, "3T"),
    ("2023-4T", 2023, "4T"),
    ("2024-1T", 2024, "1T"),
    ("2024-2T", 2024, "2T"),
    ("2024-3T", 2024, "3T"),
    ("2024-4T", 2024, "4T"),
)
_M303_2023_2024_IDS: tuple[str, ...] = tuple(stem for stem, _year, _period in _M303_2023_2024_PARAMS)


@pytest.mark.parametrize("pdf_stem,year,period", _M303_2023_2024_PARAMS, ids=_M303_2023_2024_IDS)
def test_parser_extracts_modelo_303_profile_targets_from_corpus(pdf_stem: str, year: int, period: str) -> None:
    """Round-trip: parse all 8 corpus M303 PDFs and verify casilla coverage.

    Ground truth is derived from the synthetic fixture values in _generate.py.
    Each specimen uses formula-consistent values: c46 = c27 - c45, c69 = c46.
    Box 37 (intracomunitarias) is always 0.00; compensation boxes are all 0.00.
    """
    # Per-specimen expected values derived from _MODELO_303_CORPUS_FIXTURES in _generate.py
    _expected: dict[str, dict[CasillaId, Decimal]] = {
        "2023-1T": _expected_casilla_values(
            {
                "27": Decimal("12600.00"),
                "29": Decimal("8100.00"),
                "37": Decimal("0.00"),
                "45": Decimal("8100.00"),
                "c46": Decimal("4500.00"),
                "c69": Decimal("4500.00"),
            }
        ),
        "2023-2T": _expected_casilla_values(
            {
                "27": Decimal("13800.00"),
                "29": Decimal("8700.00"),
                "37": Decimal("0.00"),
                "45": Decimal("8700.00"),
                "c46": Decimal("5100.00"),
                "c69": Decimal("5100.00"),
            }
        ),
        "2023-3T": _expected_casilla_values(
            {
                "27": Decimal("15000.00"),
                "29": Decimal("9300.00"),
                "37": Decimal("0.00"),
                "45": Decimal("9300.00"),
                "c46": Decimal("5700.00"),
                "c69": Decimal("5700.00"),
            }
        ),
        "2023-4T": _expected_casilla_values(
            {
                "27": Decimal("16800.00"),
                "29": Decimal("10500.00"),
                "37": Decimal("0.00"),
                "45": Decimal("10500.00"),
                "c46": Decimal("6300.00"),
                "c69": Decimal("6300.00"),
            }
        ),
        "2024-1T": _expected_casilla_values(
            {
                "27": Decimal("13200.00"),
                "29": Decimal("8400.00"),
                "37": Decimal("0.00"),
                "45": Decimal("8400.00"),
                "c46": Decimal("4800.00"),
                "c69": Decimal("4800.00"),
            }
        ),
        "2024-2T": _expected_casilla_values(
            {
                "27": Decimal("14400.00"),
                "29": Decimal("9000.00"),
                "37": Decimal("0.00"),
                "45": Decimal("9000.00"),
                "c46": Decimal("5400.00"),
                "c69": Decimal("5400.00"),
            }
        ),
        "2024-3T": _expected_casilla_values(
            {
                "27": Decimal("16200.00"),
                "29": Decimal("10200.00"),
                "37": Decimal("0.00"),
                "45": Decimal("10200.00"),
                "c46": Decimal("6000.00"),
                "c69": Decimal("6000.00"),
            }
        ),
        "2024-4T": _expected_casilla_values(
            {
                "27": Decimal("18000.00"),
                "29": Decimal("11400.00"),
                "37": Decimal("0.00"),
                "45": Decimal("11400.00"),
                "c46": Decimal("6600.00"),
                "c69": Decimal("6600.00"),
            }
        ),
    }
    exp = _expected[pdf_stem]

    pdf_path = FIXTURES_DIR / "justificantes" / "303" / f"{pdf_stem}.pdf"

    filing = parse_declaracion(
        pdf_path,
        modelo_override="303",
        año_override=year,
        period_override=period,
    )

    assert filing.modelo == "303"
    assert filing.period == _expected_period(year, period)
    assert filing.tax_id == "Y0000001S"
    assert filing.registry_snapshot_ref is not None
    assert filing.registry_snapshot_ref.modelo == "303"

    values = {v.casilla_id: v.printed_value for v in filing.values}

    # All 18 profile casillas (6 primitives + 12 form-page totals) must be present.
    assert set(values.keys()) == {
        # Primitive cuota leaves for parser-to-engine total reconstruction.
        "iva.repercutido.general",
        "iva.repercutido.reducido",
        "iva.repercutido.super-reducido",
        "iva.autorepercutido.intracomunitaria",
        "iva.soportado.interiores",
        "iva.autoconsumo.promotor.base",
        # Form-page totals.
        "27",
        "29",
        "37",
        "45",
        "iva.resultado-regimen-general",
        "64",
        "66",
        "iva.compensacion-pendiente-periodos-anteriores",
        "iva.compensacion-aplicada-periodo",
        "iva.compensacion-pendiente-periodos-posteriores",
        "iva.resultado",
        "71",
    }

    # Stable casillas: formula-consistent values derived from _generate.py fixtures.
    expected_c46 = exp[_casilla_id("c46")]
    expected_c69 = exp[_casilla_id("c69")]
    stable_expected = {
        _M303_CASILLA_27: exp[_M303_CASILLA_27],
        _M303_CASILLA_29: exp[_M303_CASILLA_29],
        _M303_CASILLA_37: exp[_M303_CASILLA_37],
        _M303_CASILLA_45: exp[_M303_CASILLA_45],
        _M303_RESULTADO_REGIMEN_GENERAL_CASILLA: expected_c46,
        _M303_CASILLA_64: expected_c46,
        _M303_CASILLA_66: expected_c46,
        _M303_RESULTADO_CASILLA: expected_c69,
        _M303_CASILLA_71: expected_c69,
    }
    for casilla_id, expected_value in stable_expected.items():
        assert values[casilla_id] == expected_value, (
            f"{pdf_stem}: casilla {casilla_id!r} expected {expected_value!r}, got {values[casilla_id]!r}"
        )

    # Compensation boxes are all 0.00 in synthetic fixtures
    for casilla_id in (
        _M303_COMPENSACION_ANTERIORES_CASILLA,
        _M303_COMPENSACION_APLICADA_CASILLA,
        _M303_COMPENSACION_POSTERIORES_CASILLA,
    ):
        assert values[casilla_id] == Decimal("0.00"), (
            f"{pdf_stem}: compensation casilla {casilla_id!r} got {values[casilla_id]!r}"
        )
