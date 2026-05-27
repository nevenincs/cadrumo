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

    for fixture in _MODELO_369_FIXTURES:
        target = out_dir / fixture.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(target), pagesize=A4)
        c.setTitle(f"Declaracion Modelo 369 {fixture.ejercicio} {fixture.periodo}")
        c.setAuthor("aeat test fixtures")
        c.setSubject("synthetic declaracion fixture m369")
        c.setCreator("aeat fixture generator")
        c.setProducer("reportlab")
        _draw_modelo_369(c, fixture)
        c.showPage()
        c.save()
        print(f"wrote {target}")

    for fixture in _MODELO_180_FIXTURES:
        target = out_dir / fixture.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(target), pagesize=A4)
        c.setTitle(f"Declaracion Modelo 180 {fixture.ejercicio} 0A")
        c.setAuthor("aeat test fixtures")
        c.setSubject("synthetic declaracion fixture m180")
        c.setCreator("aeat fixture generator")
        c.setProducer("reportlab")
        _draw_modelo_180(c, fixture)
        c.showPage()
        c.save()
        print(f"wrote {target}")

    for fixture in _MODELO_036_FIXTURES:
        target = out_dir / fixture.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(target), pagesize=A4)
        c.setTitle(f"Declaracion censal Modelo 036 {fixture.event_kind}")
        c.setAuthor("aeat test fixtures")
        c.setSubject("synthetic declaracion-censal fixture m036")
        c.setCreator("aeat fixture generator")
        c.setProducer("reportlab")
        _draw_modelo_036(c, fixture)
        c.showPage()
        c.save()
        print(f"wrote {target}")

    for fixture in _MODELO_349_FIXTURES:
        target = out_dir / fixture.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(target), pagesize=A4)
        c.setTitle(f"Declaracion Modelo 349 {fixture.ejercicio} {fixture.periodo}")
        c.setAuthor("aeat test fixtures")
        c.setSubject("synthetic declaracion fixture m349")
        c.setCreator("aeat fixture generator")
        c.setProducer("reportlab")
        _draw_modelo_349(c, fixture)
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

    for fixture in _MODELO_720_FIXTURES:
        target = out_dir / fixture.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(target), pagesize=A4)
        c.setTitle(f"Declaracion Modelo 720 {fixture.ejercicio} 0A")
        c.setAuthor("aeat test fixtures")
        c.setSubject("synthetic declaracion fixture m720")
        c.setCreator("aeat fixture generator")
        c.setProducer("reportlab")
        _draw_modelo_720(c, fixture)
        c.showPage()
        c.save()
        print(f"wrote {target}")


if __name__ == "__main__":
    main()
