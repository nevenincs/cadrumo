"""Shared support for split adapter tests."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from .....core import CasillaId, Period, validated_casilla_id
from .....core.errors import CadrumoError
from .....core.money import round_to_cents
from .....domain.calculations.registry.authority import bundled_authority
from .....domain.justificante import PdfModeloImportError
from .....tests import FIXTURES_DIR
from ...pdf import source_pdf_reference_path
from .. import parse_declaracion
from .._parser import _extract_pages_words
from ..errors import DeclaracionParseError, TemplateNotDetectedError

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
    "_MODELO_130_SYNTHETIC_FIXTURE",
    "_MODELO_131_SYNTHETIC_FIXTURE",
    "_MODELO_180_SYNTHETIC_FIXTURE",
    "_MODELO_184_SYNTHETIC_FIXTURE",
    "_MODELO_190_SYNTHETIC_FIXTURE",
    "_MODELO_193_SYNTHETIC_FIXTURE",
    "_MODELO_202_SYNTHETIC_FIXTURE",
    "_MODELO_232_2016_SYNTHETIC_FIXTURE",
    "_MODELO_232_2018_SYNTHETIC_FIXTURE",
    "_MODELO_303_SYNTHETIC_FIXTURE",
    "_MODELO_347_SYNTHETIC_FIXTURE",
    "_MODELO_349_SYNTHETIC_FIXTURE",
    "_MODELO_369_SYNTHETIC_FIXTURE",
    "_MODELO_720_SYNTHETIC_FIXTURE",
    "_MODELO_840_SYNTHETIC_FIXTURE",
    "CadrumoError",
    "CasillaId",
    "Decimal",
    "DeclaracionParseError",
    "Path",
    "PdfModeloImportError",
    "TemplateNotDetectedError",
    "_expected_casilla_values",
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

# Named for what it is. This fixture was previously called
# _REAL_DECLARATION_COPY, but its sidecar declares
# ``provenance = "synthetic_generated"`` -- as does every one of the 15 M130
# justificante fixtures. There is no real-corpus M130 render in the repository
# for the name to have referred to, and the consuming test's own docstring
# already said "synthetic" while its name still said "real".
_MODELO_130_SYNTHETIC_FIXTURE = FIXTURES_DIR / "justificantes" / "130" / "2024-1T.pdf"

_MODELO_349_SYNTHETIC_FIXTURE = FIXTURES_DIR / "justificantes" / "349" / "2024-1T.pdf"

# Named for what it is. This fixture was previously called
# _REAL_MODELO_303_DECLARATION_COPY, but its sidecar declares
# ``provenance = "synthetic_generated"``: it is produced by this project's own
# fixture generator, not by AEAT. The old name asserted an external grounding
# the file does not carry, which is the same class of error as a profile
# claiming to read boxes the form does not print. There is consequently no
# real-render M303 parser test in the suite; that gap is real and is recorded
# rather than papered over by the name.
_MODELO_303_SYNTHETIC_FIXTURE = FIXTURES_DIR / "justificantes" / "303" / "2024-1T.pdf"

# Named for what it is. This was previously _REAL_MODELO_190_DECLARATION_COPY,
# and the name was true: a real filed resumen anual, sanitised. It is now a
# generated specimen, because the real one carried identity the sanitiser never
# replaced and could not stay in the repository. The replacement reproduces the
# printed layout the tests read -- the three numbered summary lines, the
# perceptor identity row, the clave/subclave line, the wrapped amount row -- and
# nothing beyond it. Modelo 190 consequently has NO externally-authored render
# in the tree any more; what a real one would still have caught is AEAT
# behaviour nobody has thought to look for, and that gap is real rather than
# closed by this file.
_MODELO_190_SYNTHETIC_FIXTURE = FIXTURES_DIR / "justificantes" / "190" / "2024-0A.pdf"

_MODELO_840_SYNTHETIC_FIXTURE = FIXTURES_DIR / "justificantes" / "840" / "2024-0A.pdf"

_MODELO_036_SYNTHETIC_FIXTURE = FIXTURES_DIR / "justificantes" / "036" / "2025-0A.pdf"

_MODELO_180_SYNTHETIC_FIXTURE = FIXTURES_DIR / "justificantes" / "180" / "2024-0A.pdf"

_MODELO_202_SYNTHETIC_FIXTURE = FIXTURES_DIR / "justificantes" / "202" / "2025-1P.pdf"

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


def _expected_casilla_values(values: Mapping[object, Decimal]) -> dict[CasillaId, Decimal]:
    return {
        validated_casilla_id(casilla_id, surface="declaracion_parser_boundary.casilla"): amount
        for casilla_id, amount in values.items()
    }


_MODELO_130_EXPECTED_TARGETS: tuple[CasillaId, ...] = tuple(
    validated_casilla_id(_v, surface="declaracion_parser_boundary.casilla")
    for _v in (*(f"{index:02d}" for index in range(1, 20)),)
)

_MODELO_111_EXPECTED_TARGETS: tuple[CasillaId, ...] = tuple(
    validated_casilla_id(_v, surface="declaracion_parser_boundary.casilla")
    for _v in (
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
        "30",
    )
)

_MODELO_123_CURRENT_EXPECTED_TARGETS: tuple[CasillaId, ...] = tuple(
    validated_casilla_id(_v, surface="declaracion_parser_boundary.casilla")
    for _v in (*(f"{index:02d}" for index in range(1, 15)),)
)

_MODELO_123_HISTORICAL_EXPECTED_TARGETS: tuple[CasillaId, ...] = tuple(
    validated_casilla_id(_v, surface="declaracion_parser_boundary.casilla")
    for _v in (*(f"{index:02d}" for index in range(1, 9)),)
)


def _modelo_130_snapshot():
    return _modelo_snapshot("130", filing_year=2024, period="1T")


def _modelo_snapshot(modelo_id: str, *, filing_year: int, period: str):
    return bundled_authority().snapshot(modelo_id, filing_year=filing_year, period=period)


def _expected_period(filing_year: int, period: str) -> Period:
    return Period.from_year_and_code(filing_year, period)


def _write_declaration_pdf(
    path: Path,
    *,
    values: dict[CasillaId, Decimal],
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
    """Render ``value`` the way an AEAT declaración prints a money-2 amount.

    ``format`` rounds half-even, so it is not allowed to do the rounding:
    a cent-tie such as ``1.005`` would print ``1,00`` where AEAT requires
    ``1,01``. :func:`round_to_cents` applies the canonical half-up rule
    first, leaving ``format`` an exact two-decimal value to lay out.
    """
    formatted = f"{round_to_cents(value):,.2f}"
    return formatted.replace(",", "_").replace(".", ",").replace("_", ".")
