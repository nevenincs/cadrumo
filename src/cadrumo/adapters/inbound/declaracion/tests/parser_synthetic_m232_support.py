"""Shared Modelo 232 synthetic fixture expectations."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from .....core.casilla_id import CasillaId, validated_casilla_id
from .....domain.calculations.registry.tests.authored_editions import open_ended_revision, revision_covering
from .....domain.calculations.registry.tests.published_authority import published_supported_filing_years
from .....tests.aeat_literal_fixtures import SEDE_ROOT_URL_FIXTURE
from .parser_boundary_support import (
    MODELO_232_2016_SYNTHETIC_FIXTURE,
    MODELO_232_2018_SYNTHETIC_FIXTURE,
    specimen_period,
    split_by_supported_filing_year,
)

DECL_EJERCICIO_CASILLA: CasillaId = validated_casilla_id(
    "decl.ejercicio", surface="declaracion_parser_boundary.casilla"
)
DECL_TIPO_EJERCICIO_CASILLA: CasillaId = validated_casilla_id(
    "decl.tipo-ejercicio", surface="declaracion_parser_boundary.casilla"
)
DECL_CNAE_CASILLA: CasillaId = validated_casilla_id("decl.cnae", surface="declaracion_parser_boundary.casilla")
M232_PROFILE_CASILLAS: frozenset[CasillaId] = frozenset(
    {
        DECL_EJERCICIO_CASILLA,
        DECL_TIPO_EJERCICIO_CASILLA,
        DECL_CNAE_CASILLA,
    },
)


def _m232_fixture_case(fixture: Path) -> tuple[Path, int, str, str]:
    """Describe one bundled specimen by the exercise it is named for, its authored revision and its printed year."""
    exercise = specimen_period(fixture).filing_year
    return fixture, exercise, str(revision_covering("232", exercise).id), str(exercise)


_M232_FIXTURE_CASES: tuple[tuple[Path, int, str, str], ...] = (
    _m232_fixture_case(MODELO_232_2016_SYNTHETIC_FIXTURE),
    _m232_fixture_case(MODELO_232_2018_SYNTHETIC_FIXTURE),
)
M232_FIXTURE_PARAMS, M232_UNSUPPORTED_FIXTURE_PARAMS = split_by_supported_filing_year(_M232_FIXTURE_CASES, year_index=1)
M232_OPEN_ENDED_REVISION_ID = str(open_ended_revision("232").id)


def first_supported_filing_year() -> int:
    """The lowest filing year the published support envelope admits."""
    support = published_supported_filing_years()
    assert support is not None, "the published registry declares no filing-year support envelope"
    return support.floor


def write_modelo_232_declaration_pdf(path: Path, *, ejercicio: int) -> None:
    """Render the bundled synthetic Modelo 232 layout for one ejercicio de devengo.

    Reproduces the printed lines of the bundled synthetic fixtures so a year
    inside the support envelope can be parsed end to end; the bundled files
    print ejercicios below it.
    """
    lines = (
        "Agencia Tributaria",
        "Declaracion informativa operaciones vinculadas Modelo 232",
        "NIF: Y0001006P",
        "Razon social: DEMO EMPRESA SL",
        f"Ejercicio de devengo {ejercicio}",
        "Tipo de Ejercicio 1",
        "C.N.A.E. actividad principal 6201",
        "Ejemplar para el obligado tributario",
        f"Codigo Seguro de Verificacion: SANITIZED232{ejercicio}",
        "Fecha y hora de presentacion: 2024-01-01 10:00:00",
        "Fecha de alta de la actividad: 01-01-1900",
        SEDE_ROOT_URL_FIXTURE.rstrip("/"),
    )
    pdf = canvas.Canvas(str(path), pagesize=A4)
    _width, height = A4
    y = height - 48
    for line in lines:
        pdf.drawString(50, y, line)
        y -= 18
    pdf.save()
