"""Modelo 111 parser boundary corpus tests."""

from __future__ import annotations

import pytest

from ._parser_boundary_support import (
    _MODELO_111_EXPECTED_TARGETS,
    FIXTURES_DIR,
    CasillaId,
    Decimal,
    _casilla_id,
    _expected_period,
    _modelo_snapshot,
    parse_declaracion,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_M111_CASILLA_07: CasillaId = _casilla_id("07")
_M111_CASILLA_08: CasillaId = _casilla_id("08")
_M111_CASILLA_09: CasillaId = _casilla_id("09")
_M111_CASILLA_28: CasillaId = _casilla_id("28")
_M111_CASILLA_30: CasillaId = _casilla_id("30")
_M111_CORPUS_PARAMS: tuple[tuple[str, int, str], ...] = (
    ("2024-1T", 2024, "1T"),
    ("2024-2T", 2024, "2T"),
    ("2024-3T", 2024, "3T"),
    ("2024-4T", 2024, "4T"),
)
_M111_CORPUS_IDS: tuple[str, ...] = tuple(stem for stem, _year, _period in _M111_CORPUS_PARAMS)


def test_parser_extracts_modelo_111_registry_profile_targets_from_pdf() -> None:
    """Assert the M111 declaracion_pdf profile declares exactly the expected 29 targets."""
    snapshot = _modelo_snapshot("111", filing_year=2025, period="1T")
    profile = snapshot.extraction_profiles["modelo-111-declaracion-pdf"]
    assert tuple(target.casilla_id for target in profile.target_casillas) == _MODELO_111_EXPECTED_TARGETS
    for target in profile.target_casillas:
        assert target.match_strategy == "bbox_anchored", (
            f"casilla {target.casilla_id}: expected match_strategy='bbox_anchored', got {target.match_strategy!r}"
        )
        assert target.bbox_anchor is not None, (
            f"casilla {target.casilla_id}: bbox_anchor must be set for bbox_anchored targets"
        )


@pytest.mark.parametrize("pdf_stem,year,period", _M111_CORPUS_PARAMS, ids=_M111_CORPUS_IDS)
def test_parser_extracts_modelo_111_tax_id_from_corpus(pdf_stem: str, year: int, period: str) -> None:
    """Tax-id extraction must succeed for all M111 corpus PDFs."""
    from .._parser import _extract_tax_id
    from .._parsers import extract_pages_text

    pdf_path = FIXTURES_DIR / "justificantes" / "111" / f"{pdf_stem}.pdf"
    pages = extract_pages_text(pdf_path)
    text = "\n".join(pages)

    tax_id = _extract_tax_id(text)

    assert tax_id == "Y0000001S", f"{pdf_stem}: expected tax_id='Y0000001S', got {tax_id!r}"


@pytest.mark.parametrize("pdf_stem,year,period", _M111_CORPUS_PARAMS, ids=_M111_CORPUS_IDS)
def test_parser_extracts_modelo_111_casillas_from_corpus(pdf_stem: str, year: int, period: str) -> None:
    """Round-trip all M111 corpus PDFs through the production bbox_anchored profile."""
    pdf_path = FIXTURES_DIR / "justificantes" / "111" / f"{pdf_stem}.pdf"

    filing = parse_declaracion(
        pdf_path,
        modelo_override="111",
        año_override=year,
        period_override=period,
    )

    assert filing.modelo == "111"
    assert filing.period == _expected_period(year, period)
    assert filing.tax_id == "Y0000001S", f"{pdf_stem}: expected tax_id='Y0000001S', got {filing.tax_id!r}"
    assert filing.registry_snapshot_ref is not None
    assert filing.registry_snapshot_ref.modelo == "111"
    assert filing.registry_snapshot_ref.modelo_year == year

    values = {value.casilla_id: value.printed_value for value in filing.values}
    assert _M111_CASILLA_30 in values, (
        f"{pdf_stem}: expected casilla {_M111_CASILLA_30!r} in extracted values, got {set(values.keys())!r}"
    )
    assert values[_M111_CASILLA_30] == Decimal("1000.00"), (
        f"{pdf_stem}: casilla {_M111_CASILLA_30!r} expected Decimal('1000.00'), "
        f"got {values[_M111_CASILLA_30]!r}"
    )

    if pdf_stem == "2024-4T":
        assert set(values.keys()) == {_M111_CASILLA_30}, (
            f"{pdf_stem}: negative filing should yield only casilla '30', got {set(values.keys())!r}"
        )
        return

    expected_positive_values = {
        _M111_CASILLA_07: Decimal("1"),
        _M111_CASILLA_08: Decimal("1000.00"),
        _M111_CASILLA_09: Decimal("1000.00"),
        _M111_CASILLA_28: Decimal("1000.00"),
    }
    assert set(expected_positive_values) <= set(values), (
        f"{pdf_stem}: expected casillas 07/08/09/28/30, got {set(values.keys())!r}"
    )
    for casilla_id, expected_value in expected_positive_values.items():
        assert values[casilla_id] == expected_value, (
            f"{pdf_stem}: casilla {casilla_id!r} expected {expected_value!r}, got {values[casilla_id]!r}"
        )
