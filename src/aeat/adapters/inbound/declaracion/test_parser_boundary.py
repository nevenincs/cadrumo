"""Tests for the declaración parser boundary."""

from __future__ import annotations
from aeat.core.resources import resources

from decimal import Decimal
from pathlib import Path

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from aeat.tests import FIXTURES_DIR

from . import DeclaracionParseError, parse_declaracion

pytestmark = [
    pytest.mark.unit,
    pytest.mark.domain_inbound,
    pytest.mark.fixture_tier_l3,
]

_REAL_DECLARATION_COPY = FIXTURES_DIR / "justificantes" / "130" / "2024-1T.pdf"


def test_parser_extracts_registry_profile_targets_from_pdf(tmp_path: Path) -> None:
    snapshot = _modelo_130_snapshot()
    profile = snapshot.extraction_profiles["modelo-130-declaracion-pdf"]
    values = {
        casilla_id: Decimal(index).quantize(Decimal("0.01"))
        for index, casilla_id in enumerate(profile.target_casillas, start=1)
    }
    pdf_path = tmp_path / "modelo-130.pdf"
    _write_declaration_pdf(pdf_path, values=values)

    filing = parse_declaracion(pdf_path, modelo_override="130", año_override=2024)

    assert filing.modelo == "130"
    assert filing.period == "1T"
    assert filing.tax_id == "00000000T"
    assert {value.casilla_id: value.printed_value for value in filing.values} == values
    # The parser stamps the resolving registry snapshot's four-axis
    # coordinate onto the observation so downstream consumers can
    # detect AEAT template drift on subsequent registry releases
    # The ref is populated from the snapshot the parser actually
    # resolved against.
    assert filing.registry_snapshot_ref is not None
    assert filing.registry_snapshot_ref.modelo == "130"
    assert filing.registry_snapshot_ref.modelo_year == 2024
    assert filing.registry_snapshot_ref.period == "1T"


def test_parser_extracts_modelo_111_registry_profile_targets_from_pdf(tmp_path: Path) -> None:
    snapshot = _modelo_snapshot("111", filing_year=2025, period="1T")
    profile = snapshot.extraction_profiles["modelo-111-declaracion-pdf"]
    values = {
        casilla_id: Decimal(index).quantize(Decimal("0.01"))
        for index, casilla_id in enumerate(profile.target_casillas, start=1)
    }
    pdf_path = tmp_path / "modelo-111.pdf"
    _write_declaration_pdf(pdf_path, modelo="111", ejercicio="2025", values=values)

    filing = parse_declaracion(pdf_path, modelo_override="111", año_override=2025)

    assert filing.modelo == "111"
    assert filing.period == "1T"
    assert filing.tax_id == "00000000T"
    assert {value.casilla_id: value.printed_value for value in filing.values} == values


def test_parser_extracts_modelo_123_current_registry_profile_targets_from_pdf(tmp_path: Path) -> None:
    snapshot = _modelo_snapshot("123", filing_year=2026, period="1T")
    profile = snapshot.extraction_profiles["modelo-123-declaracion-pdf"]
    values = {
        casilla_id: Decimal(index).quantize(Decimal("0.01"))
        for index, casilla_id in enumerate(profile.target_casillas, start=1)
    }
    pdf_path = tmp_path / "modelo-123-2026.pdf"
    _write_declaration_pdf(pdf_path, modelo="123", ejercicio="2026", values=values)

    filing = parse_declaracion(pdf_path, modelo_override="123", año_override=2026)

    assert filing.modelo == "123"
    assert filing.period == "1T"
    assert filing.tax_id == "00000000T"
    assert {value.casilla_id: value.printed_value for value in filing.values} == values


def test_parser_extracts_modelo_123_historical_registry_profile_targets_from_pdf(tmp_path: Path) -> None:
    snapshot = _modelo_snapshot("123", filing_year=2023, period="4T")
    profile = snapshot.extraction_profiles["modelo-123-2019-declaracion-pdf"]
    values = {
        casilla_id: Decimal(index).quantize(Decimal("0.01"))
        for index, casilla_id in enumerate(profile.target_casillas, start=1)
    }
    pdf_path = tmp_path / "modelo-123-2023.pdf"
    _write_declaration_pdf(pdf_path, modelo="123", ejercicio="2023", period="4T", values=values)

    filing = parse_declaracion(pdf_path, modelo_override="123", año_override=2023)

    assert filing.modelo == "123"
    assert filing.period == "4T"
    assert filing.tax_id == "00000000T"
    assert {value.casilla_id: value.printed_value for value in filing.values} == values


def test_parser_fails_when_registry_profile_targets_are_missing(tmp_path: Path) -> None:
    snapshot = _modelo_130_snapshot()
    profile = snapshot.extraction_profiles["modelo-130-declaracion-pdf"]
    values = {
        casilla_id: Decimal(index).quantize(Decimal("0.01"))
        for index, casilla_id in enumerate(profile.target_casillas, start=1)
        if casilla_id != "19"
    }
    pdf_path = tmp_path / "modelo-130-missing.pdf"
    _write_declaration_pdf(pdf_path, values=values)

    with pytest.raises(DeclaracionParseError, match=r"missing=19"):
        parse_declaracion(pdf_path, modelo_override="130", año_override=2024)


def test_parser_requires_a_known_registry_model_after_template_resolution(tmp_path: Path) -> None:
    pdf_path = tmp_path / "modelo-999.pdf"
    _write_declaration_pdf(pdf_path, modelo="999", ejercicio="2025", values={"01": Decimal("1.00")})

    with pytest.raises(DeclaracionParseError, match="is not present in the calculation registry"):
        parse_declaracion(
            pdf_path,
            modelo_override="999",
            año_override=2025,
            period_override="1T",
        )


def test_real_redacted_declaration_copy_fails_on_registry_coverage_gap() -> None:
    with pytest.raises(DeclaracionParseError, match="missing="):
        parse_declaracion(
            _REAL_DECLARATION_COPY,
            modelo_override="130",
            año_override=2024,
            period_override="1T",
        )


def _modelo_130_snapshot():
    return _modelo_snapshot("130", filing_year=2024, period="1T")


def _modelo_snapshot(modelo_id: str, *, filing_year: int, period: str):
    return resources().modelos.authority.snapshot(modelo_id, filing_year=filing_year, period=period)


def _write_declaration_pdf(
    path: Path,
    *,
    values: dict[str, Decimal],
    modelo: str = "130",
    ejercicio: str = "2024",
    period: str = "1T",
) -> None:
    pdf = canvas.Canvas(str(path), pagesize=A4)
    width, height = A4
    y = height - 48
    pdf.drawString(50, y, "AGENCIA TRIBUTARIA")
    y -= 18
    pdf.drawString(50, y, f"Declaracion - Modelo {modelo}")
    y -= 18
    pdf.drawString(50, y, f"Ejercicio: {ejercicio}   Periodo: {period}")
    y -= 28
    for casilla_id, amount in values.items():
        pdf.drawString(50, y, f"{casilla_id}  Casilla {casilla_id}    {_spanish_amount(amount)}")
        y -= 22
    pdf.drawString(50, 54, "NIF: 00000000T")
    pdf.drawRightString(width - 50, 54, "CSV: TESTCSV0000000000")
    pdf.save()


def _spanish_amount(value: Decimal) -> str:
    formatted = f"{value:,.2f}"
    return formatted.replace(",", "_").replace(".", ",").replace("_", ".")
