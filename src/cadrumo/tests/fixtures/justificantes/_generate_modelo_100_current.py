"""Synthetic Modelo 100 current-year (2024/2025) declaracion fixture.

No real ejercicio-2024/2025 declaracion PDF specimen is bundled (the corpus
under ``tests/fixtures/justificantes/100/`` covers 2021-2023 only). This
generator renders a DR-faithful synthetic declaracion body: each casilla
line reproduces the AEAT-published Diseno de Registro field-dictionary label
text (deaccented for the ASCII-safe pdfplumber extraction path, consistent
with the M232/M349/M840/M036/M180/M369/M720 fixture conventions) verbatim
for the target casilla, sourced from:

    src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_100/files/
        08-100-diccionario-declaracion-individual-ejercicio-2024-...properties
        01-100-diccionario-declaracion-individual-ejercicio-2025-...properties

Non-tautology proof: label_pattern values on the registry
``declaracion_pdf`` extraction profile are grounded against these DR field
descriptions, not the registry casilla ``label`` fields; a pattern that
drifts from the DR vocabulary produces a zero-match parse failure on this
fixture.

See Also:
    :mod:`~adapters.inbound.declaracion.tests.test_parser_boundary_m100_current_year`
        Round-trip tests that consume the generated 2024/2025 fixture PDFs.
    :mod:`~adapters.inbound.declaracion.tests._parser_boundary_m100_current_support`
        Shared expected casilla set that mirrors this generator's rows.
    :func:`~domain.calculations.registry.validated_casilla_id`
        Core casilla-id validator used to keep render-row keys canonical.

Current-year declaration coverage makes casilla 0604 load-bearing.
"""

from __future__ import annotations

from dataclasses import dataclass

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from ....core.casilla_id import CasillaId, validated_casilla_id
from ._generate_base import _SEDE_ORIGIN


@dataclass(frozen=True)
class _Modelo100CurrentYearFixture:
    """Sanitized M100 current-year declaracion fixture -- named_label layout."""

    filename: str
    ejercicio: str
    tax_id: str
    full_name: str
    render_rows: tuple[tuple[CasillaId, str, str], ...]  # (casilla_id, dr_label_text, spanish_formatted_amount)


# DR-grounded label text per casilla, deaccented, shared by both covered years
# (the year-specific formula tail on 0218/0235/0595 does not affect the
# registry profile's tail-agnostic label_pattern anchors).
_M100_CURRENT_YEAR_RENDER_ROWS: tuple[tuple[CasillaId, str, str], ...] = (
    (
        validated_casilla_id("0171", surface="modelo_100_current_year_fixture casilla id"),
        "Ingresos de explotacion",
        "1.000,00",
    ),
    (
        validated_casilla_id("0180", surface="modelo_100_current_year_fixture casilla id"),
        "Total ingresos computables ( Suma [0171] a [0179] )",
        "1.000,00",
    ),
    (
        validated_casilla_id("0218", surface="modelo_100_current_year_fixture casilla id"),
        "Suma ( [0181] a [0195] + [0198] a [0200] )",
        "0,00",
    ),
    (
        validated_casilla_id("0223", surface="modelo_100_current_year_fixture casilla id"),
        "Total gastos deducibles ( [0218] + [0222] )",
        "0,00",
    ),
    (
        validated_casilla_id("0224", surface="modelo_100_current_year_fixture casilla id"),
        "Rendimiento neto ( [0180] - [0220] o [0180] - [0223] )",
        "1.000,00",
    ),
    (
        validated_casilla_id("0226", surface="modelo_100_current_year_fixture casilla id"),
        "Rendimiento neto reducido ( [0224] - [0225] - [0236] )",
        "1.000,00",
    ),
    (
        validated_casilla_id("0231", surface="modelo_100_current_year_fixture casilla id"),
        "Suma de rendimientos netos reducidos de las actividades economicas en estimacion directa",
        "1.000,00",
    ),
    (
        validated_casilla_id("0235", surface="modelo_100_current_year_fixture casilla id"),
        "Rendimiento neto reducido total de las actividades economicas en estimacion directa ( [0231] - [0232] )",
        "1.000,00",
    ),
    (
        validated_casilla_id("0432", surface="modelo_100_current_year_fixture casilla id"),
        "Saldo neto de los rendimientos a integrar en la base imponible general",
        "1.000,00",
    ),
    (
        validated_casilla_id("0500", surface="modelo_100_current_year_fixture casilla id"),
        "Base liquidable general",
        "1.000,00",
    ),
    (
        validated_casilla_id("0505", surface="modelo_100_current_year_fixture casilla id"),
        "Base liquidable general sometida a gravamen",
        "1.000,00",
    ),
    (
        validated_casilla_id("0510", surface="modelo_100_current_year_fixture casilla id"),
        "Base liquidable del ahorro",
        "0,00",
    ),
    (
        validated_casilla_id("0545", surface="modelo_100_current_year_fixture casilla id"),
        "Cuota integra estatal: Parte estatal",
        "100,00",
    ),
    (
        validated_casilla_id("0546", surface="modelo_100_current_year_fixture casilla id"),
        "Cuota integra autonomica: Parte autonomica",
        "100,00",
    ),
    (
        validated_casilla_id("0585", surface="modelo_100_current_year_fixture casilla id"),
        "Cuota liquida estatal incrementada ( [0585] = [0570] + [0568] ): Parte estatal",
        "100,00",
    ),
    (
        validated_casilla_id("0586", surface="modelo_100_current_year_fixture casilla id"),
        "Cuota liquida autonomica incrementada ( [0586] = [0571] + [0569] ): Parte autonomica",
        "100,00",
    ),
    (
        validated_casilla_id("0587", surface="modelo_100_current_year_fixture casilla id"),
        "Cuota liquida incrementada total ( [0585] + [0586] )",
        "200,00",
    ),
    (
        validated_casilla_id("0595", surface="modelo_100_current_year_fixture casilla id"),
        "Cuota resultante de la autoliquidacion ( [0587] - [0588] - [0589] )",
        "200,00",
    ),
    (
        validated_casilla_id("0604", surface="modelo_100_current_year_fixture casilla id"),
        "Pagos fraccionados ingresados (actividades economicas)",
        "50,00",
    ),
    (validated_casilla_id("0610", surface="modelo_100_current_year_fixture casilla id"), "Cuota diferencial", "150,00"),
    (
        validated_casilla_id("0670", surface="modelo_100_current_year_fixture casilla id"),
        "Resultado de la declaracion ( [0610] - [0611] + [0612] )",
        "150,00",
    ),
)

_MODELO_100_CURRENT_YEAR_FIXTURES: tuple[_Modelo100CurrentYearFixture, ...] = (
    _Modelo100CurrentYearFixture(
        filename="100/2024-0A.pdf",
        ejercicio="2024",
        tax_id="Y0000001S",
        full_name="APELLIDO APELLIDO NOMBRE",
        render_rows=_M100_CURRENT_YEAR_RENDER_ROWS,
    ),
    _Modelo100CurrentYearFixture(
        filename="100/2025-0A.pdf",
        ejercicio="2025",
        tax_id="Y0000001S",
        full_name="APELLIDO APELLIDO NOMBRE",
        render_rows=_M100_CURRENT_YEAR_RENDER_ROWS,
    ),
)


def _draw_modelo_100_current_year(c: canvas.Canvas, fixture: _Modelo100CurrentYearFixture) -> None:
    """Render a sanitized M100 current-year declaracion page onto ``c``.

    Each casilla row prints the DR-grounded label text followed by the
    Spanish-formatted amount at line end, matching the real declaracion
    body-text layout the ``named_label`` extraction targets anchor on.
    """
    _, height = A4
    y = height - 25 * mm
    c.setFont("Helvetica-Bold", 14)
    c.drawString(20 * mm, y, "Agencia Tributaria")
    y -= 8 * mm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(20 * mm, y, f"Declaracion IRPF  Modelo 100  Ejercicio {fixture.ejercicio}")
    y -= 12 * mm
    c.setFont("Helvetica", 10)
    c.drawString(20 * mm, y, f"Ejercicio: {fixture.ejercicio}   Periodo: 0A")
    y -= 8 * mm
    c.drawString(20 * mm, y, f"NIF: {fixture.tax_id}")
    y -= 6 * mm
    c.drawString(20 * mm, y, f"Apellidos y nombre: {fixture.full_name}")
    y -= 10 * mm
    for _casilla_id_value, label, amount in fixture.render_rows:
        c.drawString(20 * mm, y, f"{label}  {amount}")
        y -= 6 * mm
        if y < 30 * mm:
            c.showPage()
            c.setFont("Helvetica", 10)
            y = height - 25 * mm
    y -= 4 * mm
    c.drawString(20 * mm, y, "Ejemplar para el obligado tributario")
    y -= 8 * mm
    # Justificante receipt trailer -- required by the sidecar roundtrip test.
    csv_val = f"SANITIZED100{fixture.ejercicio}"
    c.drawString(20 * mm, y, f"Codigo Seguro de Verificacion: {csv_val}")
    y -= 6 * mm
    c.drawString(20 * mm, y, "Fecha y hora de presentacion: 2025-06-01 10:00:00")
    y -= 6 * mm
    c.drawString(20 * mm, y, "Fecha de alta de la actividad: 01-01-1900")
    y -= 6 * mm
    c.drawString(20 * mm, y, _SEDE_ORIGIN)


__all__ = [
    "_MODELO_100_CURRENT_YEAR_FIXTURES",
    "_Modelo100CurrentYearFixture",
    "_draw_modelo_100_current_year",
]
