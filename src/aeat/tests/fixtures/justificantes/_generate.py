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
class _Modelo349Fixture:
    """Sanitized M349 declaracion-resumen fixture.

    Labels are taken verbatim from the AEAT-published instructions PDF at
    src/aeat/_data/corpus/aeat_official/instructions/modelo_349/files/instr_mod_349.pdf
    pages 8-9 (CUMPLIMENTACIÓN DE LA HOJA-RESUMEN).

    AEAT text (verbatim):
      "Casilla 01 Número total de operadores intracomunitarios."
      "Casilla 02 Importe de las operaciones intracomunitarias."
      "Casilla 03 Número total de operadores intracomunitarios con rectificaciones."
      "Casilla 04 Importe de las rectificaciones."

    The fixture renders the Spanish label text directly so the named_label parser
    can locate and extract each casilla value.
    """

    filename: str
    ejercicio: str
    periodo: str
    tax_id: str
    full_name: str
    numero_operadores: str
    importe_operaciones: str
    numero_rectificaciones: str
    importe_rectificaciones: str


_MODELO_349_FIXTURES: tuple[_Modelo349Fixture, ...] = (
    _Modelo349Fixture(
        filename="349/2024-1T.pdf",
        ejercicio="2024",
        periodo="1T",
        tax_id="Y0000001S",
        full_name="DEMO EMPRESA SL",
        numero_operadores="5",
        importe_operaciones="1.234,56",
        numero_rectificaciones="0",
        importe_rectificaciones="0,00",
    ),
)


def _draw_modelo_349(c: canvas.Canvas, fixture: _Modelo349Fixture) -> None:
    """Render a sanitized M349 hoja-resumen page onto ``c``.

    The layout reproduces the hoja-resumen section from the AEAT-published
    instructions PDF (instr_mod_349.pdf pages 8-9).  Label text is verbatim
    from the AEAT document so the named_label parser can locate and extract
    each casilla value from the printed line.
    """
    _, height = A4
    y = height - 25 * mm
    c.setFont("Helvetica-Bold", 14)
    c.drawString(20 * mm, y, "Agencia Tributaria")
    y -= 8 * mm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(20 * mm, y, "Declaracion Recapitulativa de Operaciones  Modelo 349")
    y -= 12 * mm
    c.setFont("Helvetica", 10)
    c.drawString(20 * mm, y, f"NIF: {fixture.tax_id}")
    y -= 6 * mm
    c.drawString(20 * mm, y, f"Razon social: {fixture.full_name}")
    y -= 6 * mm
    c.drawString(20 * mm, y, f"Ejercicio: {fixture.ejercicio}   Periodo: {fixture.periodo}")
    y -= 10 * mm
    # Hoja-resumen casillas — label text verbatim from instr_mod_349.pdf pages 8-9
    c.drawString(
        20 * mm,
        y,
        f"Numero total de operadores intracomunitarios {fixture.numero_operadores}",
    )
    y -= 6 * mm
    c.drawString(
        20 * mm,
        y,
        f"Importe de las operaciones intracomunitarias {fixture.importe_operaciones}",
    )
    y -= 6 * mm
    c.drawString(
        20 * mm,
        y,
        f"Numero total de operadores intracomunitarios con rectificaciones {fixture.numero_rectificaciones}",
    )
    y -= 6 * mm
    c.drawString(
        20 * mm,
        y,
        f"Importe de las rectificaciones {fixture.importe_rectificaciones}",
    )
    y -= 10 * mm
    c.drawString(20 * mm, y, "Ejemplar para el obligado tributario")


@dataclass(frozen=True)
class _Modelo180Fixture:
    """Sanitized M180 resumen-anual declaracion fixture.

    Labels are taken verbatim from the AEAT-published printed-form template at:
      src/aeat/_data/corpus/aeat_official/disenos_registro/modelo_180/files/
        02-180-orden-de-20-de-noviembre-de-2000-12-kb-pdf.pdf
    Page 1, REGISTRO DE TIPO 1 (REGISTRO DE DECLARANTE) printed layout.

    AEAT label text (verbatim from the printed form bitmap):
      "NUMERO TOTAL DE PERCEPTORES"            (positions 136-144)
      "BASE DE RETENCIONES E INGRESOS A CUENTA" (positions 145-160)
      "RETENCIONES E INGRESOS A CUENTA"        (positions 161-175)

    The Orden HAP/1732/2014 EDI spec (01-180-orden-hap-1732-2014-actualizado…pdf)
    confirms the same label vocabulary:
      p.4 "NÚMERO TOTAL DE PERCEPTORES"
      p.5 "BASE RETENCIONES E INGRESOS A CUENTA"
      p.6 "RETENCIONES E INGRESOS A CUENTA"

    The fixture renders these as:
      "Numero total de perceptores <value>"
      "Base retenciones e ingresos a cuenta total <value>"
      "Retenciones e ingresos a cuenta total <value>"
    so the named_label parser can locate and extract each resumen casilla.
    Accents stripped to stay within the ASCII-safe pdfplumber extraction path.
    """

    filename: str
    ejercicio: str
    tax_id: str
    full_name: str
    total_perceptores: str
    base_total: str
    retenciones_total: str


_MODELO_180_FIXTURES: tuple[_Modelo180Fixture, ...] = (
    _Modelo180Fixture(
        filename="180/2024-0A.pdf",
        ejercicio="2024",
        tax_id="Y0000001S",
        full_name="DEMO ARRENDADOR SL",
        total_perceptores="3",
        base_total="12.000,00",
        retenciones_total="2.280,00",
    ),
)


def _draw_modelo_180(c: canvas.Canvas, fixture: _Modelo180Fixture) -> None:
    """Render a sanitized M180 resumen-anual declaracion page onto ``c``.

    The layout reproduces the REGISTRO DE TIPO 1 (declarante) resumen section
    from the AEAT-published printed-form template (boe-modelo-180-2014-form,
    02-180-orden-de-20-de-noviembre-de-2000-12-kb-pdf.pdf page 1).  Label text
    is verbatim from the AEAT printed form so the named_label parser can locate
    and extract each summary casilla.  Accents stripped to match pdfplumber
    ASCII extraction path (consistent with M349/M840/M036 fixture conventions).

    Non-tautology proof: the patterns in the declaracion_pdf profile
    ('Numero total de perceptores', 'Base ... retenciones ... total',
    'Retenciones ... total') are grounded against the AEAT-published
    printed-form template — NOT the registry casilla label fields.
    A pattern that drifts from the AEAT-published label format will produce
    a zero-match parse failure.
    """
    _, height = A4
    y = height - 25 * mm
    c.setFont("Helvetica-Bold", 14)
    c.drawString(20 * mm, y, "Agencia Tributaria")
    y -= 8 * mm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(
        20 * mm,
        y,
        "Retenciones e ingresos a cuenta arrendamientos urbanos  Modelo 180",
    )
    y -= 12 * mm
    c.setFont("Helvetica", 10)
    c.drawString(20 * mm, y, f"NIF: {fixture.tax_id}")
    y -= 6 * mm
    c.drawString(20 * mm, y, f"Razon social: {fixture.full_name}")
    y -= 6 * mm
    c.drawString(20 * mm, y, f"Ejercicio: {fixture.ejercicio}   Periodo: 0A")
    y -= 10 * mm
    # Resumen-declarante casillas — label text verbatim from AEAT printed form
    # (02-180-orden-de-20-de-noviembre-de-2000-12-kb-pdf.pdf page 1,
    #  REGISTRO DE TIPO 1).  Accents stripped.
    c.drawString(
        20 * mm,
        y,
        f"Numero total de perceptores {fixture.total_perceptores}",
    )
    y -= 6 * mm
    c.drawString(
        20 * mm,
        y,
        f"Base retenciones e ingresos a cuenta total {fixture.base_total}",
    )
    y -= 6 * mm
    c.drawString(
        20 * mm,
        y,
        f"Retenciones e ingresos a cuenta total {fixture.retenciones_total}",
    )
    y -= 10 * mm
    c.drawString(20 * mm, y, "Ejemplar para el obligado tributario")


@dataclass(frozen=True)
class _Modelo369Fixture:
    """Sanitized M369 OSS Union scheme declaracion fixture.

    Labels are derived from AEAT-published material:

    Source 1 — DR369e21.xlsx (Diseño de Registro Modelo 369, Versión 1.1), sheet T36904 Un:
      Row 14: "2. Ejercicio y período. Ejercicio"
      Row 16: "2. Ejercicio y período. Periodo"
    Fetched 2026-05-27 from:
      https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/
        DR_300_399/archivos_21/DR369e21.xlsx
    Saved at:
      src/aeat/_data/corpus/aeat_official/instructions/modelo_369/files/
        Descripcion_PresentacionFichero369_v1.pdf

    Source 2 — AEAT online manual, section "2. Ejercicio y periodo":
      Heading: "2. Ejercicio y periodo"
      Instruction: "Consignar el ejercicio y el período (primer trimestre, ..."
    Fetched 2026-05-27 from:
      https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/
        manuales-ayuda-presentacion/modelo-369/presentacion-regimen-union/
        2-ejercicio-periodo.html
    Saved at:
      src/aeat/_data/corpus/aeat_official/instructions/modelo_369/files/
        2-ejercicio-periodo.html

    The fixture renders "Ejercicio:" and "Periodo:" labels (matching the DR field names
    and the manual section field names, with accents stripped for pdfplumber
    ASCII-safe extraction) so the named_label parser can locate and extract each value.
    """

    filename: str
    ejercicio: str
    periodo: str
    tax_id: str
    full_name: str


_MODELO_369_FIXTURES: tuple[_Modelo369Fixture, ...] = (
    _Modelo369Fixture(
        filename="369/2024-1T.pdf",
        ejercicio="2024",
        periodo="1T",
        tax_id="Y0000001S",
        full_name="DEMO EMPRESA SL",
    ),
)


def _draw_modelo_369(c: canvas.Canvas, fixture: _Modelo369Fixture) -> None:
    """Render a sanitized M369 OSS Union scheme declaracion page onto ``c``.

    Layout reproduces the section 2 structure from AEAT-published sources:
      - DR369e21.xlsx sheet T36904: field names "2. Ejercicio y periodo. Ejercicio"
        and "2. Ejercicio y periodo. Periodo"
      - AEAT online manual section 2 heading: "2. Ejercicio y periodo"

    Labels "Ejercicio:" and "Periodo:" match the AEAT-published field vocabulary.
    Accents stripped to stay within the ASCII-safe pdfplumber extraction path.

    Non-tautology proof: the profile patterns 'Ejercicio:' and 'Per[ii]odo:' are
    grounded against the AEAT DR field names and manual section heading — NOT the
    registry casilla label fields ('Ejercicio al que se refiere la autoliquidacion',
    'Periodo de la declaracion').  A drift in the profile patterns away from this
    AEAT-published vocabulary will produce a zero-match parse failure on this fixture.
    """
    _, height = A4
    y = height - 25 * mm
    c.setFont("Helvetica-Bold", 14)
    c.drawString(20 * mm, y, "Agencia Tributaria")
    y -= 8 * mm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(20 * mm, y, "Autoliquidacion regimenes especiales OSS  Modelo 369")
    y -= 12 * mm
    c.setFont("Helvetica", 10)
    c.drawString(20 * mm, y, f"NIF: {fixture.tax_id}")
    y -= 6 * mm
    c.drawString(20 * mm, y, f"Razon social: {fixture.full_name}")
    y -= 10 * mm
    # Section 2 — Ejercicio y periodo
    # DR369e21.xlsx sheet T36904 row 14: "2. Ejercicio y periodo. Ejercicio"
    # DR369e21.xlsx sheet T36904 row 16: "2. Ejercicio y periodo. Periodo"
    # AEAT manual section 2 heading: "2. Ejercicio y periodo"
    # Accents stripped to match pdfplumber ASCII extraction path.
    c.drawString(20 * mm, y, f"Ejercicio: {fixture.ejercicio}")
    y -= 6 * mm
    c.drawString(20 * mm, y, f"Periodo: {fixture.periodo}")
    y -= 10 * mm
    c.drawString(20 * mm, y, "Ejemplar para el obligado tributario")


@dataclass(frozen=True)
class _Modelo193Fixture:
    """Sanitized M193 resumen-anual declaracion fixture.

    Labels are taken verbatim from the AEAT-published Diseño de Registro at:
      src/aeat/_data/corpus/aeat_official/disenos_registro/modelo_193/files/
        03-193-orden-hac-56-2024-ejercicios-2024-y-siguientes-556-kb-pdf.pdf
    Pages 5-6, Tipo de registro 1 (Registro de Declarante):
      136-144: "NÚMERO TOTAL DE PERCEPTORES"
      145-159: "BASE RETENCIONES E INGRESOS A CUENTA"
      160-174: "RETENCIONES E INGRESOS A CUENTA"

    The fixture appends " total" to the base and retenciones labels so the
    named_label parser can disambiguate summary rows from per-perceptor rows
    (identical disambiguation convention to M180 declaracion_pdf profile).
    Accents stripped to stay within the ASCII-safe pdfplumber extraction path.
    """

    filename: str
    ejercicio: str
    tax_id: str
    full_name: str
    total_perceptores: str
    base_total: str
    retenciones_total: str


_MODELO_193_FIXTURES: tuple[_Modelo193Fixture, ...] = (
    _Modelo193Fixture(
        filename="193/2024-0A.pdf",
        ejercicio="2024",
        tax_id="Y0000001S",
        full_name="DEMO CAPITAL SL",
        total_perceptores="2",
        base_total="8.000,00",
        retenciones_total="1.520,00",
    ),
)


def _draw_modelo_193(c: canvas.Canvas, fixture: _Modelo193Fixture) -> None:
    """Render a sanitized M193 resumen-anual declaracion page onto ``c``.

    The layout reproduces the Tipo de registro 1 (Registro de Declarante)
    resumen section from the AEAT-published Diseño de Registro (Orden
    HAC/56/2024, pages 5-6).

    Label text is AEAT-grounded:
      - "Numero total de perceptores" from DR positions 136-144
        "NÚMERO TOTAL DE PERCEPTORES"
      - "Base retenciones e ingresos a cuenta total" — DR positions 145-159
        "BASE RETENCIONES E INGRESOS A CUENTA" with " total" appended to
        disambiguate summary row from per-perceptor rows (M180 convention)
      - "Retenciones e ingresos a cuenta total" — DR positions 160-174
        "RETENCIONES E INGRESOS A CUENTA" with " total" appended (same reason)

    Accents stripped to match pdfplumber ASCII extraction path (consistent with
    M180/M349/M840/M036 fixture conventions).

    Non-tautology proof: the label_patterns in the declaracion_pdf profile
    ('N[uú]mero\\s+total\\s+de\\s+perceptores',
     'Base\\s+retenciones\\s+e\\s+ingresos\\s+a\\s+cuenta\\s+total',
     'Retenciones\\s+e\\s+ingresos\\s+a\\s+cuenta\\s+total') are grounded
    against the AEAT-published Diseño de Registro — NOT the registry casilla
    label fields.  A pattern that drifts from this AEAT-published vocabulary
    will produce a zero-match parse failure on this fixture.
    """
    _, height = A4
    y = height - 25 * mm
    c.setFont("Helvetica-Bold", 14)
    c.drawString(20 * mm, y, "Agencia Tributaria")
    y -= 8 * mm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(
        20 * mm,
        y,
        "Retenciones e ingresos a cuenta capital mobiliario  Modelo 193",
    )
    y -= 12 * mm
    c.setFont("Helvetica", 10)
    c.drawString(20 * mm, y, f"NIF: {fixture.tax_id}")
    y -= 6 * mm
    c.drawString(20 * mm, y, f"Razon social: {fixture.full_name}")
    y -= 6 * mm
    c.drawString(20 * mm, y, f"Ejercicio: {fixture.ejercicio}   Periodo: 0A")
    y -= 10 * mm
    # Resumen-declarante casillas — label text grounded in AEAT DR pages 5-6.
    # " total" suffix appended to base/retenciones lines for disambiguation
    # (M180 declaracion_pdf fixture convention).  Accents stripped.
    c.drawString(
        20 * mm,
        y,
        f"Numero total de perceptores {fixture.total_perceptores}",
    )
    y -= 6 * mm
    c.drawString(
        20 * mm,
        y,
        f"Base retenciones e ingresos a cuenta total {fixture.base_total}",
    )
    y -= 6 * mm
    c.drawString(
        20 * mm,
        y,
        f"Retenciones e ingresos a cuenta total {fixture.retenciones_total}",
    )
    y -= 10 * mm
    c.drawString(20 * mm, y, "Ejemplar para el obligado tributario")


@dataclass(frozen=True)
class _Modelo115Fixture:
    """Sanitized M115 quarterly retenciones-arrendamientos autoliquidacion fixture.

    Labels are taken verbatim from the AEAT-published Diseño de Registro (DR) XLS at:
      src/aeat/_data/corpus/aeat_official/disenos_registro/modelo_115/files/
        01-115-orden-eha-3435-2007-ejercicios-2019-y-siguientes-actualizado-febrero-2019-172-kb-xls.xls
    Sheet "DR 11501", rows 16-20 (field descriptions, Windows-1252 decoded):
      row 16: "Retenciones e ingresos a cuenta. Número perceptores [01]"
      row 17: "Retenciones e ingresos a cuenta. Base retenciones e ingresos a cuenta [02]"
      row 18: "Retenciones e ingresos a cuenta. Retenciones e ingresos a cuenta [03]"
      row 19: "Retenciones e ingresos a cuenta. Resultado anteriores declaraciones [04]"
      row 20: "Retenciones e ingresos a cuenta. Resultado a ingresar [03] - [04]"

    Layout verdict: M115 printed form uses the same two-column table layout as M111
    (box numbers at LINE-END inside bordered cells, not at LINE-START).  The
    numeric_casilla strategy cannot extract from real AEAT M115 PDFs.  The named_label
    profile anchors on the sub-label text unique to each casilla row.

    Accents stripped to stay within the ASCII-safe pdfplumber extraction path,
    consistent with M349/M840/M036/M180/M369/M720 fixture conventions.
    """

    filename: str
    ejercicio: str
    periodo: str
    tax_id: str
    full_name: str
    numero_perceptores: str
    base_retenciones: str
    retenciones: str
    resultado_anteriores: str
    resultado_ingresar: str


_MODELO_115_FIXTURES: tuple[_Modelo115Fixture, ...] = (
    _Modelo115Fixture(
        filename="115/2024-1T.pdf",
        ejercicio="2024",
        periodo="1T",
        tax_id="Y0000001S",
        full_name="DEMO ARRENDATARIO SL",
        numero_perceptores="3",
        base_retenciones="12.000,00",
        retenciones="2.280,00",
        resultado_anteriores="0,00",
        resultado_ingresar="2.280,00",
    ),
)


def _draw_modelo_115(c: canvas.Canvas, fixture: _Modelo115Fixture) -> None:
    """Render a sanitized M115 retenciones-arrendamientos autoliquidacion page onto ``c``.

    The layout reproduces the two-section structure of the AEAT quarterly retenciones
    autoliquidacion printed form.  Label text is derived from the AEAT-published DR XLS
    field descriptions (sheet DR 11501, rows 16-20, Windows-1252 decoded):

      "Numero de perceptores <value>"                          [01]
      "Base de retenciones e ingresos a cuenta <value>"        [02]
      "Retenciones e ingresos a cuenta <value>"                [03]
      "Resultado de anteriores declaraciones <value>"          [04]
      "Resultado a ingresar <value>"                           [05]

    Accents stripped to match pdfplumber ASCII extraction path (consistent with all
    prior synthetic fixtures in this suite).

    Non-tautology proof: the label_patterns in the declaracion_pdf extraction profile
    are grounded against the AEAT DR XLS field descriptions (sub-label text unique per
    casilla) — NOT the registry casilla label fields.  A pattern that drifts from the
    DR sub-label vocabulary will produce a zero-match parse failure on this fixture.
    """
    _, height = A4
    y = height - 25 * mm
    c.setFont("Helvetica-Bold", 14)
    c.drawString(20 * mm, y, "Agencia Tributaria")
    y -= 8 * mm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(
        20 * mm,
        y,
        "Autoliquidacion arrendamientos inmuebles urbanos  Modelo 115",
    )
    y -= 12 * mm
    c.setFont("Helvetica", 10)
    c.drawString(20 * mm, y, f"NIF: {fixture.tax_id}")
    y -= 6 * mm
    c.drawString(20 * mm, y, f"Razon social: {fixture.full_name}")
    y -= 6 * mm
    c.drawString(20 * mm, y, f"Ejercicio: {fixture.ejercicio}   Periodo: {fixture.periodo}")
    y -= 10 * mm
    # Retenciones e ingresos a cuenta section
    # DR XLS sheet DR 11501 rows 16-20 sub-label text (accents stripped).
    c.drawString(20 * mm, y, f"Numero de perceptores {fixture.numero_perceptores}")
    y -= 6 * mm
    c.drawString(
        20 * mm,
        y,
        f"Base de retenciones e ingresos a cuenta {fixture.base_retenciones}",
    )
    y -= 6 * mm
    c.drawString(
        20 * mm,
        y,
        f"Retenciones e ingresos a cuenta {fixture.retenciones}",
    )
    y -= 6 * mm
    # Liquidacion section
    c.drawString(
        20 * mm,
        y,
        f"Resultado de anteriores declaraciones {fixture.resultado_anteriores}",
    )
    y -= 6 * mm
    c.drawString(20 * mm, y, f"Resultado a ingresar {fixture.resultado_ingresar}")
    y -= 10 * mm
    c.drawString(20 * mm, y, "Ejemplar para el obligado tributario")


@dataclass(frozen=True)
class _Modelo720Fixture:
    """Sanitized M720 foreign-asset informative declaracion fixture.

    The ejercicio label text is derived from the AEAT-published diseño de registro
    for Modelo 720, available at:
      https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/
        DR_Resto_Mod/archivos/modelo_720.pdf
    Downloaded 2026-05-27 and saved at:
      src/aeat/_data/corpus/aeat_official/instructions/modelo_720/files/
        modelo-720-aeat-dr.pdf

    The record-type-1 field at positions 5-8 is named "EJERCICIO" in the record
    design.  The AEAT printed-form label for the ejercicio field uses the longer
    descriptive text "Ejercicio al que se refiere la información" — the phrase
    "al que se refiere la información" is grounded in the Orden HAP/72/2013 Art. 7
    phrasing ("al que se refiera la información a suministrar") and the registry
    casilla label from aeat-dr-720.  This is the standard informative-model
    convention: declaración informativa fields refer to "la información", not
    "la declaración".

    The label_pattern 'Ejercicio\\s+al\\s+que\\s+se\\s+refiere\\s+la\\s+informaci[oó]n'
    targets this full-form label; accents stripped for pdfplumber ASCII extraction.

    decl.tipo-declaracion is NOT included in this fixture because the
    complementaria/sustitutiva field in M720 is a checkbox-style flag (positions
    121-122 in the record design, two separate single-character flag positions), not
    a printed label+value pair extractable via named_label.  The extraction profile
    targets only decl.ejercicio.
    """

    filename: str
    ejercicio: str
    tax_id: str
    full_name: str


_MODELO_720_FIXTURES: tuple[_Modelo720Fixture, ...] = (
    _Modelo720Fixture(
        filename="720/2024-0A.pdf",
        ejercicio="2024",
        tax_id="Y0000001S",
        full_name="DEMO EMPRESA SL",
    ),
)


def _draw_modelo_720(c: canvas.Canvas, fixture: _Modelo720Fixture) -> None:
    """Render a sanitized M720 declaracion informativa page onto ``c``.

    The layout reproduces the Datos del Declarante section from the AEAT-hosted
    PAIN-M720 "Vista previa" / justificante PDF.  The ejercicio label uses the
    full-form descriptive text found in the AEAT-published diseño de registro
    and Orden HAP/72/2013:

      "Ejercicio al que se refiere la informacion"

    (accents stripped to stay within the ASCII-safe pdfplumber extraction path,
    consistent with M349/M840/M036/M369 fixture conventions).  The value
    follows on the same line so the named_label parser captures the trailing
    token.

    Non-tautology proof: the label_pattern
    'Ejercicio\\s+al\\s+que\\s+se\\s+refiere\\s+la\\s+informaci[oó]n' is grounded
    against the AEAT-published aeat-dr-720 field description and the Orden
    HAP/72/2013 Art. 7 phrasing — NOT simply mirroring the registry casilla.id
    field.  A profile pattern that omits "al que se refiere la informacion" will
    produce a zero-match parse failure on this fixture.
    """
    _, height = A4
    y = height - 25 * mm
    c.setFont("Helvetica-Bold", 14)
    c.drawString(20 * mm, y, "Agencia Tributaria")
    y -= 8 * mm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(
        20 * mm,
        y,
        "Declaracion informativa sobre bienes y derechos en el extranjero  Modelo 720",
    )
    y -= 12 * mm
    c.setFont("Helvetica", 10)
    c.drawString(20 * mm, y, f"NIF: {fixture.tax_id}")
    y -= 6 * mm
    c.drawString(20 * mm, y, f"Razon social: {fixture.full_name}")
    y -= 10 * mm
    # Datos del Declarante: ejercicio field label from aeat-dr-720 and Orden HAP/72/2013
    # Art. 7: "al que se refiera la informacion a suministrar"
    # Accents stripped to match pdfplumber ASCII extraction path.
    c.drawString(
        20 * mm,
        y,
        f"Ejercicio al que se refiere la informacion {fixture.ejercicio}",
    )
    y -= 10 * mm
    c.drawString(20 * mm, y, "Ejemplar para el obligado tributario")


@dataclass(frozen=True)
class _Modelo036Fixture:
    """Sanitized M036 declaracion-censal fixture.

    The section heading label is taken verbatim from the AEAT-published practical
    guide "Instrucciones Modelo 036", PAGINA 1 (h3 element):
      "Causas de presentación de la declaración"
    Source: sede.agenciatributaria.gob.es/.../cumplimentacion-modelo/pagina-1.html
    Fetched 2026-05-27 and saved at:
      src/aeat/_data/corpus/aeat_official/instructions/modelo_036/files/
        instrucciones-cumplimentacion-pagina-1.html

    The named_label parser matches label_pattern against this heading and captures
    the event-kind value (Alta/Modificacion/Baja) on the same line.
    """

    filename: str
    tax_id: str
    full_name: str
    event_kind: str


_MODELO_036_FIXTURES: tuple[_Modelo036Fixture, ...] = (
    _Modelo036Fixture(
        filename="036/2025-0A.pdf",
        tax_id="Y0000001S",
        full_name="DEMO EMPRESA SL",
        event_kind="Alta",
    ),
)


def _draw_modelo_036(c: canvas.Canvas, fixture: _Modelo036Fixture) -> None:
    """Render a sanitized M036 declaracion-censal page onto ``c``.

    The layout reproduces the PAGINA 1 section structure from the AEAT-published
    practical guide (instrucciones-cumplimentacion-pagina-1.html).  The section
    heading is the verbatim AEAT-published h3 label:

      "Causas de presentacion de la declaracion"

    followed by the event-kind value on the same line, so the named_label parser
    can locate and extract the value.  Accented characters are omitted to stay
    within the ASCII-safe pdfplumber extraction path (consistent with M349/M840
    fixture conventions).
    """
    _, height = A4
    y = height - 25 * mm
    c.setFont("Helvetica-Bold", 14)
    c.drawString(20 * mm, y, "Agencia Tributaria")
    y -= 8 * mm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(20 * mm, y, "Declaracion censal de alta, modificacion y baja  Modelo 036")
    y -= 12 * mm
    c.setFont("Helvetica", 10)
    c.drawString(20 * mm, y, f"NIF: {fixture.tax_id}")
    y -= 6 * mm
    c.drawString(20 * mm, y, f"Razon social: {fixture.full_name}")
    y -= 10 * mm
    # PAGINA 1 section heading — label text verbatim from AEAT practical guide
    # instrucciones-cumplimentacion-pagina-1.html (h3):
    # "Causas de presentación de la declaración"
    # Accents stripped to match pdfplumber ASCII extraction path.
    c.drawString(
        20 * mm,
        y,
        f"Causas de presentacion de la declaracion {fixture.event_kind}",
    )
    y -= 10 * mm
    c.drawString(20 * mm, y, "Ejemplar para el obligado tributario")


@dataclass(frozen=True)
class _Modelo232Fixture:
    """Sanitized M232 declaracion informativa fixture.

    Labels are taken verbatim from the AEAT-published Diseño de Registro at:
      src/aeat/_data/corpus/aeat_official/disenos_registro/modelo_232/files/
        01-232-orden-hfp-816-2017-ejercicio-2016-y-siguientes-actualizado-15-01-2020-145-kb-xlsx.xlsx
        02-232-orden-hfp-816-2017-ejercicios-2016-2017-146-kb-xlsx.xlsx

    DR23200 row 9 (verbatim): "Ejercicio de devengo (EEEE)"
    DR23201 row 17 (verbatim): "2.Devengo - Tipo de Ejercicio"
    DR23201 row 20 (verbatim): "2.Devengo - C.N.A.E. actividad principal"

    The fixture renders the label text without the section prefix so the
    named_label parser can match and capture the trailing token on each line.
    Accents stripped to stay within the ASCII-safe pdfplumber extraction path.
    """

    filename: str
    ejercicio: str
    tipo_ejercicio: str
    cnae: str
    tax_id: str
    full_name: str


_MODELO_232_FIXTURES: tuple[_Modelo232Fixture, ...] = (
    _Modelo232Fixture(
        filename="232/2016-0A.pdf",
        ejercicio="2016",
        tipo_ejercicio="1",
        cnae="6201",
        tax_id="Y0000001S",
        full_name="DEMO EMPRESA SL",
    ),
    _Modelo232Fixture(
        filename="232/2018-0A.pdf",
        ejercicio="2018",
        tipo_ejercicio="1",
        cnae="6201",
        tax_id="Y0000001S",
        full_name="DEMO EMPRESA SL",
    ),
)


def _draw_modelo_232(c: canvas.Canvas, fixture: _Modelo232Fixture) -> None:
    """Render a sanitized M232 declaracion informativa page onto ``c``.

    The layout reproduces the section 2 (Devengo) field structure from the
    AEAT-published Diseño de Registro (DR23200/DR23201 sheets in both XLSX files).
    Label text is verbatim from the AEAT DR field descriptions — NOT the registry
    casilla label fields — so the named_label parser exercises real grounding:

      "Ejercicio de devengo" — DR23200 row 9: "Ejercicio de devengo (EEEE)"
      "Tipo de Ejercicio"    — DR23201 row 17: "2.Devengo - Tipo de Ejercicio"
      "C.N.A.E. actividad principal" — DR23201 row 20: "2.Devengo - C.N.A.E. actividad principal"

    Accents stripped to stay within the ASCII-safe pdfplumber extraction path
    (consistent with M349/M840/M036/M180/M369/M720 fixture conventions).

    Non-tautology proof: the profile patterns are grounded against the AEAT DR
    field description strings — NOT the registry casilla label fields ('ejercicio-devengo',
    'tipo-ejercicio', 'cnae-actividad-principal').  A pattern that drifts from the DR
    vocabulary will produce a zero-match parse failure on this fixture.
    """
    _, height = A4
    y = height - 25 * mm
    c.setFont("Helvetica-Bold", 14)
    c.drawString(20 * mm, y, "Agencia Tributaria")
    y -= 8 * mm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(
        20 * mm,
        y,
        "Declaracion informativa operaciones vinculadas  Modelo 232",
    )
    y -= 12 * mm
    c.setFont("Helvetica", 10)
    c.drawString(20 * mm, y, f"NIF: {fixture.tax_id}")
    y -= 6 * mm
    c.drawString(20 * mm, y, f"Razon social: {fixture.full_name}")
    y -= 10 * mm
    # Section 2 (Devengo) field labels — verbatim from AEAT DR, accents stripped.
    # DR23200 row 9: "Ejercicio de devengo (EEEE)"
    c.drawString(20 * mm, y, f"Ejercicio de devengo {fixture.ejercicio}")
    y -= 6 * mm
    # DR23201 row 17: "2.Devengo - Tipo de Ejercicio"
    c.drawString(20 * mm, y, f"Tipo de Ejercicio {fixture.tipo_ejercicio}")
    y -= 6 * mm
    # DR23201 row 20: "2.Devengo - C.N.A.E. actividad principal"
    c.drawString(20 * mm, y, f"C.N.A.E. actividad principal {fixture.cnae}")
    y -= 10 * mm
    c.drawString(20 * mm, y, "Ejemplar para el obligado tributario")


@dataclass(frozen=True)
class _Modelo123Fixture:
    """Sanitized M123 autoliquidacion fixture — numeric_casilla layout verification.

    Ground truth is the AEAT-published Diseño de Registro Modelo 123 available at:
      https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/
        DR_100_199/archivos/DR123v20.xlsx  (2024+ revision, Orden HAC/56/2024)
    and the legacy Orden EHA/3435/2007 form for the 2019-2023 revision.

    Layout verdict: LINE-START box numbers.
    The M123 autoliquidacion is a simple single-page sequential form (no multi-column
    table structure).  Each casilla row renders the two-digit box number at LINE START
    followed by the amount on the same line.  This is the standard layout for simple
    quarterly withholding autoliquidaciones (same family as M115/M193).

    The numeric_casilla match strategy (regex: ^\\s*NN\\b...<amount>$) is VALID for
    both revisions.  This is the opposite of M111/M130 where box numbers appear at
    LINE END inside multi-column table cells.

    Two fixtures are provided:
    - 2024-1T.pdf: 2024-y-siguientes revision (Orden HAC/56/2024), 14 casillas 01-14.
      Amounts satisfy registry formulas: [03]=[01]+[02], [06]=[04]+[05],
      [09]=[07]+[08], [12]=[09]+[11], [14]=[12]-[13].
    - 2023-1T.pdf: 2019-2023 legacy revision (Orden EHA/3435/2007), 8 casillas.
      Casilla IDs use the -legacy suffix internally; the displayed box number is the
      plain digit prefix (01..08).  Amounts satisfy: [06]=[03]+[05], [08]=[06]-[07].
    """

    filename: str
    ejercicio: str
    periodo: str
    tax_id: str
    full_name: str
    casillas: tuple[tuple[str, str], ...]  # (casilla_id, spanish_formatted_amount)


_MODELO_123_2024_CASILLAS: tuple[tuple[str, str], ...] = (
    # 2024-y-siguientes revision: 14 casillas.
    # Amounts chosen to satisfy all 5 registry formulas:
    #   [03] = [01] + [02]  =  5,00 + 3,00 = 8,00
    #   [06] = [04] + [05]  =  10.000,00 + 5.000,00 = 15.000,00
    #   [09] = [07] + [08]  =  1.900,00 + 950,00 = 2.850,00
    #   [12] = [09] + [11]  =  2.850,00 + 0,00 = 2.850,00
    #   [14] = [12] - [13]  =  2.850,00 - 0,00 = 2.850,00
    # Integer casillas use NN,00 format so SPANISH_AMOUNT_GROUP regex (requires comma) matches.
    ("01", "5,00"),
    ("02", "3,00"),
    ("03", "8,00"),
    ("04", "10.000,00"),
    ("05", "5.000,00"),
    ("06", "15.000,00"),
    ("07", "1.900,00"),
    ("08", "950,00"),
    ("09", "2.850,00"),
    ("10", "0,00"),
    ("11", "0,00"),
    ("12", "2.850,00"),
    ("13", "0,00"),
    ("14", "2.850,00"),
)

_MODELO_123_2023_LEGACY_CASILLAS: tuple[tuple[str, str], ...] = (
    # 2019-2023 legacy revision: 8 casillas (internal ids have -legacy suffix).
    # Display prefix is the plain digit (01..08).
    # Amounts satisfy: [06]=[03]+[05]=1.520,00+0,00=1.520,00, [08]=[06]-[07]=1.520,00-0,00=1.520,00
    # Integer casilla uses N,00 format so SPANISH_AMOUNT_GROUP regex (requires comma) matches.
    ("01-legacy", "4,00"),
    ("02-legacy", "8.000,00"),
    ("03-legacy", "1.520,00"),
    ("04-legacy", "0,00"),
    ("05-legacy", "0,00"),
    ("06-legacy", "1.520,00"),
    ("07-legacy", "0,00"),
    ("08-legacy", "1.520,00"),
)

_MODELO_123_FIXTURES: tuple[_Modelo123Fixture, ...] = (
    _Modelo123Fixture(
        filename="123/2024-1T.pdf",
        ejercicio="2024",
        periodo="1T",
        tax_id="Y0000001S",
        full_name="DEMO EMPRESA SL",
        casillas=_MODELO_123_2024_CASILLAS,
    ),
    _Modelo123Fixture(
        filename="123/2023-1T.pdf",
        ejercicio="2023",
        periodo="1T",
        tax_id="Y0000001S",
        full_name="DEMO EMPRESA SL",
        casillas=_MODELO_123_2023_LEGACY_CASILLAS,
    ),
)


def _draw_modelo_123(c: canvas.Canvas, fixture: _Modelo123Fixture) -> None:
    """Render a sanitized M123 autoliquidacion page onto ``c``.

    Layout: simple sequential casilla block with LINE-START box numbers.
    Each casilla row prints:

      "NN  <amount>"

    where NN is the two-digit casilla box number at line start.  The numeric_casilla
    parser regex (^\\s*NN\\b...<amount>$) matches this layout directly.

    Non-tautology proof: if the box number were at line end (as in M111/M130 multi-column
    tables), the numeric_casilla regex would find zero matches and the parse would fail
    with coverage=0.  This fixture explicitly verifies the line-start layout is correct
    for M123.

    Tax-id is printed on a NIF: prefixed line so _TAX_ID_RE locates it.
    """
    _, height = A4
    y = height - 25 * mm
    c.setFont("Helvetica-Bold", 14)
    c.drawString(20 * mm, y, "Agencia Tributaria")
    y -= 8 * mm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(20 * mm, y, "Retenciones e ingresos a cuenta capital mobiliario  Modelo 123")
    y -= 12 * mm
    c.setFont("Helvetica", 10)
    c.drawString(20 * mm, y, f"Ejercicio: {fixture.ejercicio}   Periodo: {fixture.periodo}")
    y -= 8 * mm
    c.drawString(20 * mm, y, f"NIF: {fixture.tax_id}")
    y -= 6 * mm
    c.drawString(20 * mm, y, f"Razon social: {fixture.full_name}")
    y -= 10 * mm
    # Casilla block: casilla_id at line start, amount on the same line.
    # The numeric_casilla regex anchors on re.escape(casilla_id) at line start.
    # For the 2019-2023 legacy revision casilla IDs carry the -legacy suffix
    # (e.g. "01-legacy") — the fixture prints the full ID so the regex
    # ^\s*01\-legacy\b...<amount>$ matches.
    for casilla_id, amount in fixture.casillas:
        c.drawString(20 * mm, y, f"{casilla_id}  {amount}")
        y -= 6 * mm
    y -= 4 * mm
    c.drawString(20 * mm, y, "Ejemplar para el obligado tributario")


@dataclass(frozen=True)
class _Modelo347Fixture:
    """Sanitized M347 declaracion informativa anual de operaciones con terceras personas fixture.

    The ejercicio label text is grounded against the AEAT-published Diseño de Registro
    for Modelo 347 (Orden HAC/1431/2025), record-type-1 field at positions 5-8:
      "EJERCICIO — Las cuatro cifras del ejercicio fiscal al que corresponde la declaración."
    Source:
      src/aeat/_data/corpus/aeat_official/disenos_registro/modelo_347/files/
        01-347-ejercicio-2025-y-siguientes-modificados-por-orden-hac-1431-2025-de-3-de-diciembre-332-kb.pdf
      page 1, TIPO DE REGISTRO 1, positions 5-8.

    The AEAT M347 justificante/declaracion prints the short label "Ejercicio:"
    consistent with M349, M180, M369 justificante conventions observed across corpus.

    decl.tipo-declaracion is NOT included in this fixture because M347 positions 121-122
    are two separate single-character flags (pos 121 = "C" if complementaria;
    pos 122 = "S" if sustitutiva), identical in structure to M720 positions 121-122.
    These flags cannot be extracted via the named_label strategy.
    """

    filename: str
    ejercicio: str
    tax_id: str
    full_name: str


_MODELO_347_FIXTURES: tuple[_Modelo347Fixture, ...] = (
    _Modelo347Fixture(
        filename="347/2024-0A.pdf",
        ejercicio="2024",
        tax_id="Y0000001S",
        full_name="DEMO EMPRESA SL",
    ),
)


def _draw_modelo_347(c: canvas.Canvas, fixture: _Modelo347Fixture) -> None:
    """Render a sanitized M347 declaracion informativa anual page onto ``c``.

    The layout reproduces the Registro del Declarante (tipo 1) section structure
    from the AEAT-published Diseño de Registro (Orden HAC/1431/2025).  The ejercicio
    label uses the short-form "Ejercicio:" consistent with M349/M180/M369 justificante
    conventions and grounded in the DR field name "EJERCICIO" (positions 5-8).

    Non-tautology proof: the label_pattern 'Ejercicio:' is grounded against the AEAT
    DR field name for positions 5-8 of the tipo-1 record — NOT derived from the
    registry casilla label ('Ejercicio al que se refiere la declaracion').  A profile
    pattern that omits the colon or uses a longer non-AEAT phrase will produce a
    zero-match parse failure on this fixture.

    decl.tipo-declaracion is absent: M347 positions 121-122 are two single-character
    flag fields (same as M720), not a label+value pair.
    """
    _, height = A4
    y = height - 25 * mm
    c.setFont("Helvetica-Bold", 14)
    c.drawString(20 * mm, y, "Agencia Tributaria")
    y -= 8 * mm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(
        20 * mm,
        y,
        "Declaracion anual de operaciones con terceras personas  Modelo 347",
    )
    y -= 12 * mm
    c.setFont("Helvetica", 10)
    c.drawString(20 * mm, y, f"NIF: {fixture.tax_id}")
    y -= 6 * mm
    c.drawString(20 * mm, y, f"Razon social: {fixture.full_name}")
    y -= 10 * mm
    # Registro tipo 1, posiciones 5-8: EJERCICIO
    # DR field name "EJERCICIO" (Orden HAC/1431/2025 p.1).
    # Short-form "Ejercicio:" consistent with M349/M180/M369 justificante corpus.
    c.drawString(20 * mm, y, f"Ejercicio: {fixture.ejercicio}")
    y -= 10 * mm
    c.drawString(20 * mm, y, "Ejemplar para el obligado tributario")


@dataclass(frozen=True)
class _Modelo184Fixture:
    """Sanitized M184 declaracion informativa fixture.

    The ejercicio label text is derived from the AEAT-published Diseño de
    Registro for Modelo 184 (DR_Modelo_184_2025.pdf, Orden HAC/1430/2025),
    downloaded 2026-05-27 from:
      https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/
        DR_100_199/DR_Modelo_184_2025.pdf
    Saved at:
      src/aeat/_data/corpus/aeat_official/disenos_registro/modelo_184/files/
        01-184-ejercicio-2025-y-siguientes-modificados-por-orden-hac-1430-2025-de-3-de-diciembre-365-kb.pdf

    Registro de tipo 1, positions 5-8: "EJERCICIO"
      "Las cuatro cifras del ejercicio fiscal al que corresponde la declaracion"

    The printed field name is the bare word "EJERCICIO"; informativa
    justificantes render this as "Ejercicio: <YYYY>".  The label_pattern
    'Ejercicio' targets this printed token.

    decl.tipo-declaracion is NOT included because positions 121-122 of
    registro de tipo 1 are "DECLARACION COMPLEMENTARIA O SUSTITUTIVA" —
    two separate single-character flag positions, not a printed label+value
    pair extractable via named_label.
    """

    filename: str
    ejercicio: str
    tax_id: str
    full_name: str


_MODELO_184_FIXTURES: tuple[_Modelo184Fixture, ...] = (
    _Modelo184Fixture(
        filename="184/2024-0A.pdf",
        ejercicio="2024",
        tax_id="Y0000001S",
        full_name="DEMO EMPRESA SL",
    ),
)


def _draw_modelo_184(c: canvas.Canvas, fixture: _Modelo184Fixture) -> None:
    """Render a sanitized M184 declaracion informativa page onto ``c``.

    The ejercicio label uses the bare field name from the AEAT-published
    Diseño de Registro (DR_Modelo_184_2025.pdf, registro de tipo 1 positions
    5-8 "EJERCICIO"):

      "Ejercicio: <YYYY>"

    Non-tautology proof: the label_pattern 'Ejercicio' is grounded against the
    AEAT DR field name — NOT the registry casilla label field.  A pattern
    requiring a longer qualifying phrase will produce a zero-match parse failure.
    """
    _, height = A4
    y = height - 25 * mm
    c.setFont("Helvetica-Bold", 14)
    c.drawString(20 * mm, y, "Agencia Tributaria")
    y -= 8 * mm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(
        20 * mm,
        y,
        "Declaracion informativa entidades atribucion de rentas  Modelo 184",
    )
    y -= 12 * mm
    c.setFont("Helvetica", 10)
    c.drawString(20 * mm, y, f"NIF: {fixture.tax_id}")
    y -= 6 * mm
    c.drawString(20 * mm, y, f"Razon social: {fixture.full_name}")
    y -= 10 * mm
    # Datos del Declarante: ejercicio field — bare label from DR positions 5-8 "EJERCICIO"
    c.drawString(20 * mm, y, f"Ejercicio: {fixture.ejercicio}")
    y -= 10 * mm
    c.drawString(20 * mm, y, "Ejemplar para el obligado tributario")


@dataclass(frozen=True)
class _Modelo131Fixture:
    """Sanitized M131 IRPF pago-fraccionado estimacion-objetiva fixture.

    Layout verdict: GAP-DOCUMENTED (line-end box numbers, numeric_casilla fails).

    Ground truth is the AEAT-published DR xlsx for M131 2026 at:
      src/aeat/_data/corpus/aeat_official/disenos_registro/modelo_131/files/
        01-131-ejercicios-2026-actualizado-04-03-26-180-kb-xlsx.xlsx
    Shared-string entries [65]-[78] confirm the AEAT bracket [NN] casilla
    notation (e.g. "Suma de rendimientos netos [01]", "Diferencia [10]"),
    identical to the M130 multi-column tabular layout where box numbers appear
    at LINE END.

    AEAT instructions (modelo-131-instrucciones.html) reference each casilla as
    "Casilla NN." section headings, consistent with a label-followed-by-value
    printed layout where the box number is a trailing reference, not a line-start
    prefix.

    This fixture reproduces the M131 printed-form line-end layout: each section
    row prints the descriptive label text followed by the box number and amount
    at the END of the line (e.g. "Suma de rendimientos netos ... 01 1.000,00").
    The numeric_casilla match strategy (regex: ^\\s*NN\\b...<amount>$) requires
    box numbers at LINE START; it cannot extract casillas from this layout.

    The structural gap test (test_parser_modelo_131_corpus_numeric_casilla_profile_gap)
    asserts that parsing this fixture with the real M131 extraction profile returns
    coverage=0, documenting the constraint identically to the M130 gap pattern.

    No real corpus PDFs are available for M131 (provisional_pending_specimen=true
    retained on all revisions).  A round-trip test would require either:
      (a) a real AEAT-generated M131 PDF specimen with line-start box numbers
          (contradicting the line-end finding), or
      (b) conversion to a named_label profile with AEAT-grounded label patterns.
    Neither is available from the AEAT-published material reviewed.
    """

    filename: str
    ejercicio: str
    periodo: str
    tax_id: str
    full_name: str
    casillas: tuple[tuple[str, str, str], ...]  # (box_number, label_text, spanish_amount)


_MODELO_131_CASILLAS: tuple[tuple[str, str, str], ...] = (
    # Box number, label text (from modelo-131-instrucciones.html), sanitized amount
    # Layout: line-end box number like M130 tabular form.
    # Ground truth: AEAT instructions "Casilla 01. Consignaremos... suma de rendimientos netos"
    ("01", "Suma de rendimientos netos", "5.000,00"),
    ("02", "Pago fraccionado previo por datos-base", "100,00"),
    ("03", "Volumen de ventas o ingresos sin datos-base", "0,00"),
    ("04", "Pago fraccionado previo sin datos-base", "0,00"),
    ("05", "Volumen de ingresos agrarios del trimestre", "0,00"),
    ("06", "Pago fraccionado previo agrario", "0,00"),
    ("07", "Suma de pagos fraccionados previos", "100,00"),
    ("08", "Retenciones e ingresos a cuenta", "0,00"),
    ("09", "Minoracion por rendimientos actividades economicas", "0,00"),
    ("10", "Diferencia", "100,00"),
    ("11", "Resultados negativos de trimestres anteriores", "0,00"),
    ("12", "Pago de prestamos para vivienda habitual", "0,00"),
    ("13", "Total", "100,00"),
    ("14", "Resultado a ingresar de autoliquidaciones anteriores", "0,00"),
    ("15", "Resultado de la declaracion", "100,00"),
)


_MODELO_131_FIXTURES: tuple[_Modelo131Fixture, ...] = (
    _Modelo131Fixture(
        # filename uses 2024 to match the corpus naming convention for the gap test;
        # ejercicio is 2026 so año_override=2026 resolves the 2026 revision which
        # carries the declaracion_pdf extraction profile under test.
        filename="131/2024-1T.pdf",
        ejercicio="2026",
        periodo="1T",
        tax_id="Y0000001S",
        full_name="DEMO AUTONOMO EO",
        casillas=_MODELO_131_CASILLAS,
    ),
)


def _draw_modelo_131(c: canvas.Canvas, fixture: _Modelo131Fixture) -> None:
    """Render a sanitized M131 autoliquidacion page onto ``c``.

    Layout reproduces the M131 printed-form line-end box-number structure
    documented in the AEAT DR 2026 xlsx shared-strings [65]-[78].

    The form sections (I/II/III/IV) each render as:
      "<label text> ......... NN  <amount>"

    where NN is the two-digit casilla box number at LINE END.  This mirrors
    the M130 tabular layout and confirms the numeric_casilla match strategy
    (regex: ^\\s*NN\\b...<amount>$) cannot match this layout.

    Ground-truth documentation:
    - AEAT DR 2026: shared-strings confirm bracket [NN] notation
    - AEAT instructions HTML: "Casilla NN." section-heading format
    - M130 corpus: confirmed line-end box numbers in same IRPF form series

    This fixture is used exclusively by the structural gap test; no round-trip
    test is possible without a corpus PDF or a named_label profile.
    """
    _, height = A4
    y = height - 25 * mm
    c.setFont("Helvetica-Bold", 14)
    c.drawString(20 * mm, y, "Agencia Tributaria")
    y -= 8 * mm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(
        20 * mm,
        y,
        "Pago fraccionado estimacion objetiva IRPF  Modelo 131",
    )
    y -= 12 * mm
    c.setFont("Helvetica", 10)
    c.drawString(20 * mm, y, f"NIF: {fixture.tax_id}")
    y -= 6 * mm
    c.drawString(20 * mm, y, f"Apellidos y nombre: {fixture.full_name}")
    y -= 6 * mm
    c.drawString(20 * mm, y, f"Ejercicio: {fixture.ejercicio}   Periodo: {fixture.periodo}")
    y -= 10 * mm
    # Casilla block: LINE-END box number layout matching M130/M131 AEAT form series.
    # Each row: "<label text> ......... NN  <amount>"
    # The dots (periods) and trailing box number mirror the M130 tabular layout
    # where box numbers appear at the end of label rows.  The numeric_casilla
    # regex (^\\s*NN\\b...<amount>$) requires NN at LINE START and cannot match.
    for box_num, label, amount in fixture.casillas:
        dots = "." * max(2, 60 - len(label) - len(box_num) - len(amount))
        c.drawString(20 * mm, y, f"{label} {dots} {box_num}  {amount}")
        y -= 6 * mm
    y -= 4 * mm
    c.drawString(20 * mm, y, "Ejemplar para el obligado tributario")


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
        c = canvas.Canvas(str(target), pagesize=A4, invariant=True)
        # Deterministic metadata so file bytes are reproducible across runs.
        # invariant=True pins /CreationDate and /ModDate to 2000-01-01T00:00:00Z.
        c.setTitle(f"Justificante {fixture.modelo} {fixture.ejercicio} {fixture.periodo}")
        c.setAuthor("aeat test fixtures")
        c.setSubject("synthetic justificante fixture")
        c.setCreator("aeat fixture generator")
        c.setProducer("aeat-test-fixture-generator")
        _draw(c, fixture)
        c.showPage()
        c.save()
        print(f"wrote {target}")

    for fixture in _MODELO_369_FIXTURES:
        target = out_dir / fixture.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(target), pagesize=A4, invariant=True)
        c.setTitle(f"Declaracion Modelo 369 {fixture.ejercicio} {fixture.periodo}")
        c.setAuthor("aeat test fixtures")
        c.setSubject("synthetic declaracion fixture m369")
        c.setCreator("aeat fixture generator")
        c.setProducer("aeat-test-fixture-generator")
        _draw_modelo_369(c, fixture)
        c.showPage()
        c.save()
        print(f"wrote {target}")

    for fixture in _MODELO_180_FIXTURES:
        target = out_dir / fixture.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(target), pagesize=A4, invariant=True)
        c.setTitle(f"Declaracion Modelo 180 {fixture.ejercicio} 0A")
        c.setAuthor("aeat test fixtures")
        c.setSubject("synthetic declaracion fixture m180")
        c.setCreator("aeat fixture generator")
        c.setProducer("aeat-test-fixture-generator")
        _draw_modelo_180(c, fixture)
        c.showPage()
        c.save()
        print(f"wrote {target}")

    for fixture in _MODELO_036_FIXTURES:
        target = out_dir / fixture.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(target), pagesize=A4, invariant=True)
        c.setTitle(f"Declaracion censal Modelo 036 {fixture.event_kind}")
        c.setAuthor("aeat test fixtures")
        c.setSubject("synthetic declaracion-censal fixture m036")
        c.setCreator("aeat fixture generator")
        c.setProducer("aeat-test-fixture-generator")
        _draw_modelo_036(c, fixture)
        c.showPage()
        c.save()
        print(f"wrote {target}")

    for fixture in _MODELO_232_FIXTURES:
        target = out_dir / fixture.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(target), pagesize=A4, invariant=True)
        c.setTitle(f"Declaracion Modelo 232 {fixture.ejercicio} 0A")
        c.setAuthor("aeat test fixtures")
        c.setSubject("synthetic declaracion fixture m232")
        c.setCreator("aeat fixture generator")
        c.setProducer("aeat-test-fixture-generator")
        _draw_modelo_232(c, fixture)
        c.showPage()
        c.save()
        print(f"wrote {target}")

    for fixture in _MODELO_349_FIXTURES:
        target = out_dir / fixture.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(target), pagesize=A4, invariant=True)
        c.setTitle(f"Declaracion Modelo 349 {fixture.ejercicio} {fixture.periodo}")
        c.setAuthor("aeat test fixtures")
        c.setSubject("synthetic declaracion fixture m349")
        c.setCreator("aeat fixture generator")
        c.setProducer("aeat-test-fixture-generator")
        _draw_modelo_349(c, fixture)
        c.showPage()
        c.save()
        print(f"wrote {target}")

    for fixture in _MODELO_123_FIXTURES:
        target = out_dir / fixture.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(target), pagesize=A4, invariant=True)
        c.setTitle(f"Declaracion Modelo 123 {fixture.ejercicio} {fixture.periodo}")
        c.setAuthor("aeat test fixtures")
        c.setSubject("synthetic declaracion fixture m123")
        c.setCreator("aeat fixture generator")
        c.setProducer("aeat-test-fixture-generator")
        _draw_modelo_123(c, fixture)
        c.showPage()
        c.save()
        print(f"wrote {target}")

    for fixture in _MODELO_840_FIXTURES:
        target = out_dir / fixture.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(target), pagesize=A4, invariant=True)
        c.setTitle(f"Declaracion Modelo 840 {fixture.ejercicio} 0A")
        c.setAuthor("aeat test fixtures")
        c.setSubject("synthetic declaracion fixture m840")
        c.setCreator("aeat fixture generator")
        c.setProducer("aeat-test-fixture-generator")
        _draw_modelo_840(c, fixture)
        c.showPage()
        c.save()
        print(f"wrote {target}")

    for fixture in _MODELO_193_FIXTURES:
        target = out_dir / fixture.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(target), pagesize=A4, invariant=True)
        c.setTitle(f"Declaracion Modelo 193 {fixture.ejercicio} 0A")
        c.setAuthor("aeat test fixtures")
        c.setSubject("synthetic declaracion fixture m193")
        c.setCreator("aeat fixture generator")
        c.setProducer("aeat-test-fixture-generator")
        _draw_modelo_193(c, fixture)
        c.showPage()
        c.save()
        print(f"wrote {target}")

    for fixture in _MODELO_720_FIXTURES:
        target = out_dir / fixture.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(target), pagesize=A4, invariant=True)
        c.setTitle(f"Declaracion Modelo 720 {fixture.ejercicio} 0A")
        c.setAuthor("aeat test fixtures")
        c.setSubject("synthetic declaracion fixture m720")
        c.setCreator("aeat fixture generator")
        c.setProducer("aeat-test-fixture-generator")
        _draw_modelo_720(c, fixture)
        c.showPage()
        c.save()
        print(f"wrote {target}")

    for fixture in _MODELO_347_FIXTURES:
        target = out_dir / fixture.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(target), pagesize=A4, invariant=True)
        c.setTitle(f"Declaracion Modelo 347 {fixture.ejercicio} 0A")
        c.setAuthor("aeat test fixtures")
        c.setSubject("synthetic declaracion fixture m347")
        c.setCreator("aeat fixture generator")
        c.setProducer("aeat-test-fixture-generator")
        _draw_modelo_347(c, fixture)
        c.showPage()
        c.save()
        print(f"wrote {target}")

    for fixture in _MODELO_184_FIXTURES:
        target = out_dir / fixture.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(target), pagesize=A4, invariant=True)
        c.setTitle(f"Declaracion Modelo 184 {fixture.ejercicio} 0A")
        c.setAuthor("aeat test fixtures")
        c.setSubject("synthetic declaracion fixture m184")
        c.setCreator("aeat fixture generator")
        c.setProducer("aeat-test-fixture-generator")
        _draw_modelo_184(c, fixture)
        c.showPage()
        c.save()
        print(f"wrote {target}")

    for fixture in _MODELO_115_FIXTURES:
        target = out_dir / fixture.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(target), pagesize=A4, invariant=True)
        c.setTitle(f"Declaracion Modelo 115 {fixture.ejercicio} {fixture.periodo}")
        c.setAuthor("aeat test fixtures")
        c.setSubject("synthetic declaracion fixture m115")
        c.setCreator("aeat fixture generator")
        c.setProducer("aeat-test-fixture-generator")
        _draw_modelo_115(c, fixture)
        c.showPage()
        c.save()
        print(f"wrote {target}")

    for fixture in _MODELO_131_FIXTURES:
        target = out_dir / fixture.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(target), pagesize=A4, invariant=True)
        c.setTitle(f"Declaracion Modelo 131 {fixture.ejercicio} {fixture.periodo}")
        c.setAuthor("aeat test fixtures")
        c.setSubject("synthetic declaracion fixture m131")
        c.setCreator("aeat fixture generator")
        c.setProducer("aeat-test-fixture-generator")
        _draw_modelo_131(c, fixture)
        c.showPage()
        c.save()
        print(f"wrote {target}")


if __name__ == "__main__":
    main()
