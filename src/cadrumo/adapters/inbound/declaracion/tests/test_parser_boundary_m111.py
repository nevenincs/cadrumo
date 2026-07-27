"""Modelo 111 parser boundary corpus tests."""

from __future__ import annotations

import pytest

from ._parser_boundary_m111_support import (
    _M111_CASILLA_30,
    _M111_CORPUS_IDS,
    _M111_CORPUS_PARAMS,
    _M111_EXPECTED_VALUES_BY_STEM,
)
from ._parser_boundary_support import (
    _MODELO_111_EXPECTED_TARGETS,
    FIXTURES_DIR,
    Decimal,
    _expected_period,
    _modelo_snapshot,
    parse_declaracion,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


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

    # Exact map, not a subset: the extracted set IS the claim. A ratio or a
    # subset check survives a bbox anchor that stopped resolving one column
    # while another started, and the three-column layout is exactly where that
    # can happen. Each quarter's amounts are distinct from every other
    # quarter's, so a cross-fixture misread names itself too.
    expected = _M111_EXPECTED_VALUES_BY_STEM[pdf_stem]
    assert values == expected, (
        f"{pdf_stem}: extracted casillas drifted from what the render prints.\n"
        f"  unexpectedly absent: {sorted(set(expected) - set(values))}\n"
        f"  unexpectedly present: {sorted(set(values) - set(expected))}\n"
        f"  differing: {sorted(k for k in set(expected) & set(values) if values[k] != expected[k])}"
    )
    for value in values.values():
        assert isinstance(value, Decimal), f"{pdf_stem}: expected a Decimal instance, got {value!r}"
