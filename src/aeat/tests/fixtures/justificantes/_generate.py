"""Synthetic justificante PDF generator for the #44 parser test suite.

This script produces deterministic synthetic *justificantes de presentacion*
for Modelo 130, Modelo 303, Modelo 100, and Modelo 840 under
``src/aeat/tests/fixtures/justificantes/``. The PDFs are hand-modelled on the public
AEAT receipt layout (header, modelo/periodo/ejercicio block, NIF, CSV, URL,
totals) but every identifier is fictitious — the fixtures contain no real
taxpayer data.

The M840 fixture reproduces the Apartado II label layout from the AEAT-published
printed form at:
  src/aeat/_data/corpus/aeat_official/forms/modelo_840/files/
    01-840-modelo-declaracion-iae-alta-variacion-baja-pdf.pdf
pdfplumber extracts the label lines as "14Ejercicio: <value>" and
"15Declaracion de: <value>" — the fixture uses the same casilla-number-prefixed
format so the named_label parser can locate and extract the values.

The PDFs are **committed** to the repo. This script exists as a reference so
they can be regenerated deterministically; it is not executed by the test
suite. Run manually with ``uv run python src/aeat/tests/fixtures/justificantes/_generate.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


@dataclass(frozen=True)
class _Fixture:
    filename: str
    modelo: str
    ejercicio: str
    periodo: str
    tax_id: str
    full_name: str
    csv: str
    presented_at: str
    presentation_id: str
    total_ingresar: str | None
    total_devolver: str | None


_FIXTURES: tuple[_Fixture, ...] = (
    _Fixture(
        filename="modelo_130_2026Q1.pdf",
        modelo="130",
        ejercicio="2026",
        periodo="1T",
        tax_id="00000000T",
        full_name="DEMO AUTONOMO UNO",
        csv="ABCD1234EFGH5678",
        presented_at="2026-04-10 11:23:45",
        presentation_id="13020260410ABCD1234EFGH5678",
        total_ingresar="1234.56",
        total_devolver=None,
    ),
    _Fixture(
        filename="modelo_303_2026Q1.pdf",
        modelo="303",
        ejercicio="2026",
        periodo="1T",
        tax_id="00000000T",
        full_name="DEMO AUTONOMO UNO",
        csv="ZZZZ9999YYYY8888",
        presented_at="2026-04-11 09:05:00",
        presentation_id="30320260411ZZZZ9999YYYY8888",
        total_ingresar=None,
        total_devolver="450.00",
    ),
    _Fixture(
        filename="modelo_100_2025A.pdf",
        modelo="100",
        ejercicio="2025",
        periodo="0A",
        tax_id="00000000T",
        full_name="DEMO AUTONOMO UNO",
        csv="MNOP4321QRST8765",
        presented_at="2026-06-20 17:45:12",
        presentation_id="10020260620MNOP4321QRST8765",
        total_ingresar="780.40",
        total_devolver=None,
    ),
)


_VERIFY_URL = (
    "https://sede.agenciatributaria.gob.es/Sede/ayuda/consultas-practicas-manuales/"
    "verificacion-integridad-documentos.html"
)


def _draw(c: canvas.Canvas, fixture: _Fixture) -> None:
    """Render a single synthetic justificante page onto ``c``."""
    _, height = A4
    y = height - 25 * mm
    c.setFont("Helvetica-Bold", 14)
    c.drawString(20 * mm, y, "AGENCIA TRIBUTARIA")
    y -= 8 * mm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(20 * mm, y, "Justificante de presentacion")
    y -= 12 * mm
    c.setFont("Helvetica", 10)
    c.drawString(20 * mm, y, f"Modelo: {fixture.modelo}")
    y -= 6 * mm
    c.drawString(20 * mm, y, f"Ejercicio: {fixture.ejercicio}")
    y -= 6 * mm
    c.drawString(20 * mm, y, f"Periodo: {fixture.periodo}")
    y -= 10 * mm
    c.drawString(20 * mm, y, f"NIF: {fixture.tax_id}")
    y -= 6 * mm
    c.drawString(20 * mm, y, f"Apellidos y nombre o razon social: {fixture.full_name}")
    y -= 10 * mm
    c.drawString(20 * mm, y, f"Numero de justificante: {fixture.presentation_id}")
    y -= 6 * mm
    c.drawString(20 * mm, y, f"Fecha y hora de presentacion: {fixture.presented_at}")
    y -= 10 * mm
    c.drawString(20 * mm, y, f"Codigo Seguro de Verificacion: {fixture.csv}")
    y -= 10 * mm
    if fixture.total_ingresar is not None:
        c.drawString(20 * mm, y, f"Total a ingresar: {fixture.total_ingresar} euros")
        y -= 6 * mm
    if fixture.total_devolver is not None:
        c.drawString(20 * mm, y, f"Total a devolver: {fixture.total_devolver} euros")
        y -= 6 * mm
    y -= 8 * mm
    c.drawString(20 * mm, y, "Puede verificar la autenticidad de este documento en:")
    y -= 6 * mm
    c.drawString(20 * mm, y, _VERIFY_URL)


@dataclass(frozen=True)
class _Modelo840Fixture:
    """Sanitized M840 declaracion fixture.

    Labels are taken verbatim from the AEAT-published printed form PDF at
    src/aeat/_data/corpus/aeat_official/forms/modelo_840/files/
      01-840-modelo-declaracion-iae-alta-variacion-baja-pdf.pdf
    pdfplumber yields "14Ejercicio:" and "15Declaracion de:" as the casilla-label
    prefixes. Values are placed on the same line so the named_label parser captures
    the trailing token.
    """

    filename: str
    ejercicio: str
    tipo_declaracion: str
    tax_id: str
    full_name: str


_MODELO_840_FIXTURES: tuple[_Modelo840Fixture, ...] = (
    _Modelo840Fixture(
        filename="840/2024-0A.pdf",
        ejercicio="2024",
        tipo_declaracion="Alta",
        tax_id="Y0000001S",
        full_name="DEMO AUTONOMO UNO",
    ),
)


def _draw_modelo_840(c: canvas.Canvas, fixture: _Modelo840Fixture) -> None:
    """Render a sanitized M840 declaracion page onto ``c``.

    The layout reproduces the Apartado II section from the AEAT-published printed
    form (boe-modelo-840-2003-form).  Labels are the exact casilla-number-prefixed
    strings that pdfplumber extracts from the official PDF:

      - "14Ejercicio:" followed by the fiscal year value on the same line
      - "15Declaracion de:" followed by the event-type code on the same line

    This format allows the named_label parser to locate and extract both casillas.
    """
    _, height = A4
    y = height - 25 * mm
    c.setFont("Helvetica-Bold", 14)
    c.drawString(20 * mm, y, "Agencia Tributaria")
    y -= 8 * mm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(20 * mm, y, "Impuesto sobre Actividades Economicas  Modelo 840")
    y -= 12 * mm
    c.setFont("Helvetica", 10)
    # Apartado I: datos identificativos
    # NIF is on its own line so _TAX_ID_RE (\bNIF:) can locate it without
    # the casilla-number prefix breaking the word boundary.
    c.drawString(20 * mm, y, f"NIF: {fixture.tax_id}")
    y -= 6 * mm
    c.drawString(20 * mm, y, f"Apellidos y nombre o Razon social: {fixture.full_name}")
    y -= 10 * mm
    # Apartado II: Declaracion — labels verbatim from AEAT printed form (corpus-grounded)
    c.drawString(20 * mm, y, f"14Ejercicio: {fixture.ejercicio}")
    y -= 6 * mm
    c.drawString(20 * mm, y, f"15Declaracion de: {fixture.tipo_declaracion}")
    y -= 10 * mm
    c.drawString(20 * mm, y, "Ejemplar para la Administracion")


def main() -> None:
    """Regenerate every fixture PDF in-place."""
    out_dir = Path(__file__).parent
    for fixture in _FIXTURES:
        target = out_dir / fixture.filename
        c = canvas.Canvas(str(target), pagesize=A4)
        # Deterministic metadata so file bytes are reproducible.
        c.setTitle(f"Justificante {fixture.modelo} {fixture.ejercicio} {fixture.periodo}")
        c.setAuthor("aeat test fixtures")
        c.setSubject("synthetic justificante fixture")
        c.setCreator("aeat fixture generator")
        c.setProducer("reportlab")
        _draw(c, fixture)
        c.showPage()
        c.save()
        print(f"wrote {target}")

    for fixture in _MODELO_840_FIXTURES:
        target = out_dir / fixture.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(target), pagesize=A4)
        c.setTitle(f"Declaracion Modelo 840 {fixture.ejercicio} 0A")
        c.setAuthor("aeat test fixtures")
        c.setSubject("synthetic declaracion fixture m840")
        c.setCreator("aeat fixture generator")
        c.setProducer("reportlab")
        _draw_modelo_840(c, fixture)
        c.showPage()
        c.save()
        print(f"wrote {target}")


if __name__ == "__main__":
    main()
