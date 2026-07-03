"""Modelo 303 parser boundary corpus tests."""

from __future__ import annotations

import pytest

from ._parser_boundary_m303_support import _M303_CORPUS_STEMS, _M303_CURRENT_PROFILE_CASILLAS
from ._parser_boundary_support import (
    _REAL_MODELO_303_DECLARATION_COPY,
    FIXTURES_DIR,
    Decimal,
    _expected_casilla_values,
    _expected_period,
    parse_declaracion,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


def test_parser_extracts_modelo_303_targets_from_real_redacted_declaration_copy() -> None:
    filing = parse_declaracion(
        _REAL_MODELO_303_DECLARATION_COPY,
        modelo_override="303",
        año_override=2024,
        period_override="1T",
    )

    assert filing.modelo == "303"
    assert filing.period == _expected_period(2024, "1T")
    assert filing.tax_id == "Y0000001S"
    values = {value.casilla_id: value.printed_value for value in filing.values}
    assert set(values.keys()) == _M303_CURRENT_PROFILE_CASILLAS

    expected_values = _expected_casilla_values(
        {
            "27": Decimal("13200.00"),
            "29": Decimal("8400.00"),
            "37": Decimal("0.00"),
            "45": Decimal("8400.00"),
            "iva.resultado-regimen-general": Decimal("4800.00"),
            "64": Decimal("4800.00"),
            "66": Decimal("4800.00"),
            "iva.compensacion-pendiente-periodos-anteriores": Decimal("0.00"),
            "iva.resultado": Decimal("4800.00"),
            "71": Decimal("4800.00"),
        },
    )
    for casilla_id, expected_value in expected_values.items():
        assert values[casilla_id] == expected_value
    assert filing.registry_snapshot_ref is not None
    assert filing.registry_snapshot_ref.modelo == "303"
    assert filing.registry_snapshot_ref.modelo_year == 2024
    assert filing.registry_snapshot_ref.period == "1T"


@pytest.mark.parametrize("pdf_stem", _M303_CORPUS_STEMS)
def test_parser_extracts_tax_id_from_all_m303_corpus_pdfs(pdf_stem: str) -> None:
    """Tax-id extraction must succeed for all M303 corpus PDFs."""
    from .._parser import _extract_tax_id
    from .._parsers import extract_pages_text

    pdf_path = FIXTURES_DIR / "justificantes" / "303" / f"{pdf_stem}.pdf"
    pages = extract_pages_text(pdf_path)
    text = "\n".join(pages)

    tax_id = _extract_tax_id(text)

    assert tax_id == "Y0000001S", (
        f"{pdf_stem}: expected tax_id='Y0000001S', got {tax_id!r}; "
        "check _TAX_ID_RE and _TAX_ID_BEFORE_LABEL_RE in _parser.py"
    )
