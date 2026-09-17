"""Shared support for split adapter tests."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
from pathlib import Path

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from .....core.authority_grade import RegistryAuthorityGrade
from .....core.casilla_id import CasillaId, validated_casilla_id
from .....core.money.rounding import round_to_cents
from .....core.period import Period
from .....domain.calculations.registry.schema import ModeloRevision
from .....domain.calculations.registry.schema_extraction import ExtractionProfileDefinition
from .....domain.calculations.registry.tests.published_authority import (
    published_authored_revision,
    published_snapshot,
    published_supported_filing_years,
)
from .....tests.inventory import FIXTURES_DIR
from ..parser import _select_extraction_profile

pytestmark = [
    pytest.mark.unit,
    pytest.mark.hex_inbound_adapter,
]

__all__ = [
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
    "_expected_casilla_values",
    "_expected_period",
    "_filing_year_is_supported",
    "_modelo_130_snapshot",
    "_modelo_snapshot",
    "_render_extraction_profile",
    "_split_by_supported_filing_year",
    "_write_declaration_pdf",
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
    return published_snapshot(modelo_id, filing_year=filing_year, period=period)


def _split_by_supported_filing_year[CaseT: tuple[object, ...]](
    cases: Sequence[CaseT],
    *,
    year_index: int,
) -> tuple[tuple[CaseT, ...], tuple[CaseT, ...]]:
    """Partition corpus cases into admitted and refused filing years.

    The published support envelope is the only authority on which years a
    declaration may be parsed for; a corpus render below its floor must be
    refused rather than silently resolved.
    """
    admitted = tuple(case for case in cases if _filing_year_is_supported(int(case[year_index])))
    refused = tuple(case for case in cases if case not in admitted)
    return admitted, refused


def _filing_year_is_supported(filing_year: int) -> bool:
    support = published_supported_filing_years()
    return support is None or support.admits_filing_year(filing_year)


def _render_extraction_profile(
    modelo_id: str,
    *,
    filing_year: int,
    period: str,
    grade: RegistryAuthorityGrade = RegistryAuthorityGrade.FILING,
) -> tuple[ExtractionProfileDefinition, ModeloRevision]:
    """Return the declaration profile and revision that govern one render's layout.

    An admitted filing year goes through the production selector. A render
    below the support envelope cannot be filing-selected, so its layout is read
    from the authored revision covering its year; the parser boundary refusing
    that render is asserted separately.
    """
    if _filing_year_is_supported(filing_year):
        snapshot = published_snapshot(modelo_id, filing_year=filing_year, period=period, grade=grade)
        return _select_extraction_profile(snapshot, extraction_profile_id=None), snapshot.revision
    revision = published_authored_revision(modelo_id, year=filing_year)
    profiles = [
        profile
        for profile in revision.extraction_profiles
        if profile.surface == "declaracion_pdf" and "declaration_pdf" in profile.accepted_artefact_kinds
    ]
    assert len(profiles) == 1, f"M{modelo_id} {filing_year}: expected one declaration profile, got {profiles}"
    return profiles[0], revision


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
