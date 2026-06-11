"""Shared support for split adapter tests."""


from __future__ import annotations

import logging
from decimal import Decimal
from pathlib import Path

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from .....core import Period
from .....core.errors import AeatError
from .....core.resources import resources
from .....domain.justificante import PdfModeloImportError
from .....tests import FIXTURES_DIR
from ...pdf._utils import source_pdf_reference_path
from .. import parse_declaracion
from .._errors import DeclaracionParseError, TemplateNotDetectedError
from .._parser import _extract_pages_words

pytestmark = [
    pytest.mark.unit,
    pytest.mark.hex_inbound_adapter,
]

__all__ = [
    "A4",
    "FIXTURES_DIR",
    "_MODELO_036_SYNTHETIC_FIXTURE",
    "_MODELO_111_EXPECTED_TARGETS",
    "_MODELO_115_SYNTHETIC_FIXTURE",
    "_MODELO_123_2023_SYNTHETIC_FIXTURE",
    "_MODELO_123_2024_SYNTHETIC_FIXTURE",
    "_MODELO_123_CURRENT_EXPECTED_TARGETS",
    "_MODELO_123_HISTORICAL_EXPECTED_TARGETS",
    "_MODELO_130_EXPECTED_TARGETS",
    "_MODELO_131_SYNTHETIC_FIXTURE",
    "_MODELO_180_SYNTHETIC_FIXTURE",
    "_MODELO_184_SYNTHETIC_FIXTURE",
    "_MODELO_193_SYNTHETIC_FIXTURE",
    "_MODELO_232_2016_SYNTHETIC_FIXTURE",
    "_MODELO_232_2018_SYNTHETIC_FIXTURE",
    "_MODELO_347_SYNTHETIC_FIXTURE",
    "_MODELO_349_SYNTHETIC_FIXTURE",
    "_MODELO_369_SYNTHETIC_FIXTURE",
    "_MODELO_720_SYNTHETIC_FIXTURE",
    "_MODELO_840_SYNTHETIC_FIXTURE",
    "_REAL_DECLARATION_COPY",
    "_REAL_MODELO_190_DECLARATION_COPY",
    "_REAL_MODELO_303_DECLARATION_COPY",
    "AeatError",
    "Decimal",
    "DeclaracionParseError",
    "Path",
    "PdfModeloImportError",
    "TemplateNotDetectedError",
    "_expected_period",
    "_extract_pages_words",
    "_modelo_130_snapshot",
    "_modelo_snapshot",
    "_write_declaration_pdf",
    "canvas",
    "logging",
    "parse_declaracion",
    "source_pdf_reference_path",
]

_REAL_DECLARATION_COPY = FIXTURES_DIR / "justificantes" / "130" / "2024-1T.pdf"

_MODELO_349_SYNTHETIC_FIXTURE = FIXTURES_DIR / "justificantes" / "349" / "2024-1T.pdf"

_REAL_MODELO_303_DECLARATION_COPY = FIXTURES_DIR / "justificantes" / "303" / "2024-1T.pdf"

_REAL_MODELO_190_DECLARATION_COPY = FIXTURES_DIR / "justificantes" / "190" / "2024-0A.pdf"

_MODELO_840_SYNTHETIC_FIXTURE = FIXTURES_DIR / "justificantes" / "840" / "2024-0A.pdf"

_MODELO_036_SYNTHETIC_FIXTURE = FIXTURES_DIR / "justificantes" / "036" / "2025-0A.pdf"

_MODELO_180_SYNTHETIC_FIXTURE = FIXTURES_DIR / "justificantes" / "180" / "2024-0A.pdf"

_MODELO_123_2024_SYNTHETIC_FIXTURE = FIXTURES_DIR / "justificantes" / "123" / "2024-1T.pdf"

_MODELO_123_2023_SYNTHETIC_FIXTURE = FIXTURES_DIR / "justificantes" / "123" / "2023-1T.pdf"

_MODELO_369_SYNTHETIC_FIXTURE = FIXTURES_DIR / "justificantes" / "369" / "2024-1T.pdf"

_MODELO_720_SYNTHETIC_FIXTURE = FIXTURES_DIR / "justificantes" / "720" / "2024-0A.pdf"

_MODELO_347_SYNTHETIC_FIXTURE = FIXTURES_DIR / "justificantes" / "347" / "2024-0A.pdf"

_MODELO_232_2016_SYNTHETIC_FIXTURE = FIXTURES_DIR / "justificantes" / "232" / "2016-0A.pdf"

_MODELO_232_2018_SYNTHETIC_FIXTURE = FIXTURES_DIR / "justificantes" / "232" / "2018-0A.pdf"

_MODELO_193_SYNTHETIC_FIXTURE = FIXTURES_DIR / "justificantes" / "193" / "2024-0A.pdf"

_MODELO_184_SYNTHETIC_FIXTURE = FIXTURES_DIR / "justificantes" / "184" / "2024-0A.pdf"

_MODELO_115_SYNTHETIC_FIXTURE = FIXTURES_DIR / "justificantes" / "115" / "2024-1T.pdf"

_MODELO_131_SYNTHETIC_FIXTURE = FIXTURES_DIR / "justificantes" / "131" / "2024-1T.pdf"

_MODELO_130_EXPECTED_TARGETS = tuple(f"{index:02d}" for index in range(1, 20))

_MODELO_111_EXPECTED_TARGETS = (
    "01",
    "04",
    "07",
    "10",
    "13",
    "16",
    "19",
    "22",
    "25",  # col A
    "02",
    "05",
    "08",
    "11",
    "14",
    "17",
    "20",
    "23",
    "26",  # col B
    "03",
    "06",
    "09",
    "12",
    "15",
    "18",
    "21",
    "24",
    "27",
    "28",
    "30",  # col C
)

_MODELO_123_CURRENT_EXPECTED_TARGETS = tuple(f"{index:02d}" for index in range(1, 15))

_MODELO_123_HISTORICAL_EXPECTED_TARGETS = tuple(f"{index:02d}-legacy" for index in range(1, 9))


def _modelo_130_snapshot():
    return _modelo_snapshot("130", filing_year=2024, period="1T")


def _modelo_snapshot(modelo_id: str, *, filing_year: int, period: str):
    return resources().modelos.authority.snapshot(modelo_id, filing_year=filing_year, period=period)


def _expected_period(filing_year: int, period: str) -> Period:
    return Period.from_year_and_code(filing_year, period)


def _write_declaration_pdf(
    path: Path,
    *,
    values: dict[str, Decimal],
    modelo: str = "130",
    ejercicio: str = "2024",
    period: str = "1T",
    tax_id: str = "00000000T",
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
    pdf.drawString(50, 54, f"NIF: {tax_id}")
    pdf.drawRightString(width - 50, 54, "CSV: TESTCSV0000000000")
    pdf.save()


def _spanish_amount(value: Decimal) -> str:
    formatted = f"{value:,.2f}"
    return formatted.replace(",", "_").replace(".", ",").replace("_", ".")
