"""Modelo 130 parser boundary corpus sweeps."""

from __future__ import annotations

import pytest

from .._parser import _extract_tax_id
from .._parsers import extract_pages_text
from ._parser_boundary_m130_support import (
    _M130_CORPUS_GROUND_TRUTH,
    _M130_CORPUS_IDS,
    _M130_CORPUS_PARAMS,
)
from ._parser_boundary_support import FIXTURES_DIR, _expected_period, parse_declaracion

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


@pytest.mark.parametrize("pdf_stem,year,period", _M130_CORPUS_PARAMS, ids=_M130_CORPUS_IDS)
def test_parser_extracts_modelo_130_tax_id_from_corpus(pdf_stem: str, year: int, period: str) -> None:
    """Tax-id extraction must succeed for all M130 corpus PDFs."""
    pdf_path = FIXTURES_DIR / "justificantes" / "130" / f"{pdf_stem}.pdf"
    pages = extract_pages_text(pdf_path)
    text = "\n".join(pages)

    tax_id = _extract_tax_id(text)

    assert tax_id == "Y0000001S", (
        f"{pdf_stem}: expected tax_id='Y0000001S', got {tax_id!r}; "
        "check _TAX_ID_RE and _DECLARANT_ROW_RE in _parser.py"
    )


@pytest.mark.parametrize("pdf_stem,year,period", _M130_CORPUS_PARAMS, ids=_M130_CORPUS_IDS)
def test_parser_extracts_modelo_130_casillas_from_corpus(pdf_stem: str, year: int, period: str) -> None:
    """Round-trip all M130 corpus PDFs through the production bbox_anchored profile."""
    expected = _M130_CORPUS_GROUND_TRUTH[pdf_stem]
    pdf_path = FIXTURES_DIR / "justificantes" / "130" / f"{pdf_stem}.pdf"

    filing = parse_declaracion(
        pdf_path,
        modelo_override="130",
        año_override=year,
        period_override=period,
    )

    assert filing.modelo == "130", f"{pdf_stem}: expected modelo='130', got {filing.modelo!r}"
    assert filing.period == _expected_period(year, period), (
        f"{pdf_stem}: expected period={period!r}, got {filing.period!r}"
    )
    assert filing.tax_id == "Y0000001S", f"{pdf_stem}: expected tax_id='Y0000001S', got {filing.tax_id!r}"
    assert filing.registry_snapshot_ref is not None
    assert filing.registry_snapshot_ref.modelo == "130"
    assert filing.registry_snapshot_ref.modelo_year == year

    extracted = {value.casilla_id: value.printed_value for value in filing.values}
    assert extracted == expected, (
        f"{pdf_stem}: extracted casillas do not match ground truth.\n  expected: {expected}\n  got:      {extracted}"
    )
