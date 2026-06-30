"""Modelo 130 parser boundary corpus tests."""

from __future__ import annotations

import pytest

from ._parser_boundary_casillas import (
    _M130_RENDIMIENTO_NETO_CASILLA,
    _M130_RESULTADO_CASILLA,
)
from ._parser_boundary_support import (
    _MODELO_130_EXPECTED_TARGETS,
    _REAL_DECLARATION_COPY,
    FIXTURES_DIR,
    CasillaId,
    Decimal,
    DeclaracionParseError,
    _expected_casilla_values,
    _expected_period,
    _modelo_130_snapshot,
    parse_declaracion,
    source_pdf_reference_path,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_M130_CORPUS_PARAMS: tuple[tuple[str, int, str], ...] = (
    ("2021-2T", 2021, "2T"),
    ("2021-3T", 2021, "3T"),
    ("2021-4T", 2021, "4T"),
    ("2022-1T", 2022, "1T"),
    ("2022-2T", 2022, "2T"),
    ("2022-3T", 2022, "3T"),
    ("2022-4T", 2022, "4T"),
    ("2023-1T", 2023, "1T"),
    ("2023-2T", 2023, "2T"),
    ("2023-3T", 2023, "3T"),
    ("2023-4T", 2023, "4T"),
    ("2024-1T", 2024, "1T"),
    ("2024-2T", 2024, "2T"),
    ("2024-3T", 2024, "3T"),
    ("2024-4T", 2024, "4T"),
)
_M130_CORPUS_IDS: tuple[str, ...] = tuple(stem for stem, _year, _period in _M130_CORPUS_PARAMS)
_M130_CORPUS_GROUND_TRUTH: dict[str, dict[CasillaId, Decimal]] = {
    "2021-2T": _expected_casilla_values({"03": Decimal("5000.00"), "19": Decimal("900.00")}),
    "2021-3T": _expected_casilla_values({"03": Decimal("7500.00"), "19": Decimal("1400.00")}),
    "2021-4T": _expected_casilla_values({"03": Decimal("10000.00"), "19": Decimal("1900.00")}),
    "2022-1T": _expected_casilla_values({"03": Decimal("5200.00"), "19": Decimal("940.00")}),
    "2022-2T": _expected_casilla_values({"03": Decimal("7800.00"), "19": Decimal("1460.00")}),
    "2022-3T": _expected_casilla_values({"03": Decimal("9100.00"), "19": Decimal("1720.00")}),
    "2022-4T": _expected_casilla_values({"03": Decimal("11000.00"), "19": Decimal("2100.00")}),
    "2023-1T": _expected_casilla_values({"03": Decimal("5400.00"), "19": Decimal("980.00")}),
    "2023-2T": _expected_casilla_values({"03": Decimal("8100.00"), "19": Decimal("1520.00")}),
    "2023-3T": _expected_casilla_values({"03": Decimal("10500.00"), "19": Decimal("2000.00")}),
    "2023-4T": _expected_casilla_values({"03": Decimal("13000.00"), "19": Decimal("2500.00")}),
    "2024-1T": _expected_casilla_values({"03": Decimal("5600.00"), "19": Decimal("1020.00")}),
    "2024-2T": _expected_casilla_values({"03": Decimal("8400.00"), "19": Decimal("1580.00")}),
    "2024-3T": _expected_casilla_values({"03": Decimal("11200.00"), "19": Decimal("2140.00")}),
    "2024-4T": _expected_casilla_values({"03": Decimal("14000.00"), "19": Decimal("2700.00")}),
}


def test_parser_extracts_modelo_130_registry_profile_targets_from_pdf() -> None:
    """Assert the M130 declaracion_pdf profile declares exactly the expected 19 targets."""
    snapshot = _modelo_130_snapshot()
    profile = snapshot.extraction_profiles["modelo-130-declaracion-pdf"]
    assert tuple(target.casilla_id for target in profile.target_casillas) == _MODELO_130_EXPECTED_TARGETS
    for target in profile.target_casillas:
        assert target.match_strategy == "bbox_anchored", (
            f"casilla {target.casilla_id}: expected match_strategy='bbox_anchored', got {target.match_strategy!r}"
        )
        assert target.bbox_anchor is not None, (
            f"casilla {target.casilla_id}: bbox_anchor must be set for bbox_anchored targets"
        )


def test_parser_extracts_modelo_130_legal_entity_nif_from_pdf() -> None:
    """Verify NIF extraction from a real M130 corpus PDF for a CIF-format declarant."""
    pdf_path = FIXTURES_DIR / "justificantes" / "130" / "2022-2T.pdf"
    filing = parse_declaracion(pdf_path, modelo_override="130", año_override=2022, period_override="2T")
    assert filing.tax_id == "Y0000001S"
    assert filing.source_pdf_path == source_pdf_reference_path(filing.source_pdf_sha256)
    assert pdf_path.name not in str(filing.source_pdf_path)


def test_parser_fails_when_modelo_130_registry_profile_targets_are_missing() -> None:
    """Parsing fails when the M130 profile coverage falls below the registry minimum."""
    snap = _modelo_130_snapshot()
    prod_profile = snap.extraction_profiles["modelo-130-declaracion-pdf"]
    strict_profile = prod_profile.model_copy(update={"min_coverage": Decimal("1")})
    profiles = dict(snap.extraction_profiles)
    profiles[prod_profile.id] = strict_profile
    strict_snap = snap.model_copy(update={"extraction_profiles": profiles})

    pdf_path = FIXTURES_DIR / "justificantes" / "130" / "2022-1T.pdf"

    with pytest.raises(DeclaracionParseError) as excinfo:
        parse_declaracion(
            pdf_path,
            modelo_override="130",
            año_override=2022,
            period_override="1T",
            registry_snapshot=strict_snap,
        )
    assert excinfo.value.translated_message == "adapters.inbound.declaracion.errors.extraction_failed"
    assert excinfo.value.context is not None
    details = excinfo.value.context.get("details", "")
    assert isinstance(details, str) and "coverage" in details


def test_real_redacted_modelo_130_declaration_copy_extracts_partial_casillas() -> None:
    """The synthetic M130 2024-1T corpus PDF extracts casillas via bbox_anchored."""
    filing = parse_declaracion(
        _REAL_DECLARATION_COPY,
        modelo_override="130",
        año_override=2024,
        period_override="1T",
    )
    extracted = {value.casilla_id: value.printed_value for value in filing.values}
    assert set(extracted.keys()) == {_M130_RENDIMIENTO_NETO_CASILLA, _M130_RESULTADO_CASILLA}, (
        f"2024-1T: expected casillas {{03, 19}}, got {set(extracted.keys())!r}"
    )
    assert isinstance(extracted[_M130_RESULTADO_CASILLA], Decimal)
    assert isinstance(extracted[_M130_RENDIMIENTO_NETO_CASILLA], Decimal)


@pytest.mark.parametrize("pdf_stem,year,period", _M130_CORPUS_PARAMS, ids=_M130_CORPUS_IDS)
def test_parser_extracts_modelo_130_tax_id_from_corpus(pdf_stem: str, year: int, period: str) -> None:
    """Tax-id extraction must succeed for all M130 corpus PDFs."""
    from .._parser import _extract_tax_id
    from .._parsers import extract_pages_text

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
