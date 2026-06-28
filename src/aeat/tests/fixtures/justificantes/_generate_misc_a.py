"""Synthetic justificante fixtures for common non-IVA modelo families."""

from __future__ import annotations

from dataclasses import dataclass

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from ._generate_base import _SEDE_ORIGIN


@dataclass(frozen=True)
class _Modelo349Fixture:
    """Sanitized M349 declaracion-resumen fixture.

    Labels are taken verbatim from the AEAT-published instructions PDF at
    src/aeat/_data/corpus/aeat_official/instructions/modelo_349/files/instr_mod_349.pdf
    pages 8-9 (CUMPLIMENTACIÃ“N DE LA HOJA-RESUMEN).

    AEAT text (verbatim):
      "Casilla 01 NÃºmero total de operadores intracomunitarios."
      "Casilla 02 Importe de las operaciones intracomunitarias."
      "Casilla 03 NÃºmero total de operadores intracomunitarios con rectificaciones."
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
    # Hoja-resumen casillas â€” label text verbatim from instr_mod_349.pdf pages 8-9
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
    y -= 8 * mm
    # Justificante receipt trailer â€” required by TestRealCorpusParses and sidecar roundtrip test.
    # M349 is quarterly; Ejercicio/Periodo labels are already printed above.
    csv_val = f"SANITIZED349{fixture.ejercicio}"
    c.drawString(20 * mm, y, f"Codigo Seguro de Verificacion: {csv_val}")
    y -= 6 * mm
    c.drawString(20 * mm, y, "Fecha y hora de presentacion: 2024-01-01 10:00:00")
    y -= 6 * mm
    c.drawString(20 * mm, y, "Fecha de alta de la actividad: 01-01-1900")
    y -= 6 * mm
    c.drawString(20 * mm, y, _SEDE_ORIGIN)


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

    The Orden HAP/1732/2014 EDI spec (01-180-orden-hap-1732-2014-actualizadoâ€¦pdf)
    confirms the same label vocabulary:
      p.4 "NÃšMERO TOTAL DE PERCEPTORES"
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
    printed-form template â€” NOT the registry casilla label fields.
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
    # Resumen-declarante casillas â€” label text verbatim from AEAT printed form
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
    y -= 8 * mm
    # Justificante receipt trailer â€” required by TestRealCorpusParses and sidecar roundtrip test.
    # M180 prints "Periodo: 0A" above, so the parser extracts "0A" as the period.
    # TestRealCorpusParses explicit_annual_fixtures includes ("180", "2024-0A") to match.
    csv_val = f"SANITIZED180{fixture.ejercicio}"
    c.drawString(20 * mm, y, f"Codigo Seguro de Verificacion: {csv_val}")
    y -= 6 * mm
    c.drawString(20 * mm, y, "Fecha y hora de presentacion: 2024-01-01 10:00:00")
    y -= 6 * mm
    c.drawString(20 * mm, y, "Fecha de alta de la actividad: 01-01-1900")
    y -= 6 * mm
    c.drawString(20 * mm, y, _SEDE_ORIGIN)


@dataclass(frozen=True)
class _Modelo369Fixture:
    """Sanitized M369 OSS Union scheme declaracion fixture.

    Labels are derived from AEAT-published material:

    Source 1 â€” DR369e21.xlsx (DiseÃ±o de Registro Modelo 369, VersiÃ³n 1.1), sheet T36904 Un:
      Row 14: "2. Ejercicio y perÃ­odo. Ejercicio"
      Row 16: "2. Ejercicio y perÃ­odo. Periodo"
    Fetched 2026-05-27 from:
      https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/
        DR_300_399/archivos_21/DR369e21.xlsx
    Saved at:
      src/aeat/_data/corpus/aeat_official/instructions/modelo_369/files/
        Descripcion_PresentacionFichero369_v1.pdf

    Source 2 â€” AEAT online manual, section "2. Ejercicio y periodo":
      Heading: "2. Ejercicio y periodo"
      Instruction: "Consignar el ejercicio y el perÃ­odo (primer trimestre, ..."
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
    grounded against the AEAT DR field names and manual section heading â€” NOT the
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
    # Section 2 â€” Ejercicio y periodo
    # DR369e21.xlsx sheet T36904 row 14: "2. Ejercicio y periodo. Ejercicio"
    # DR369e21.xlsx sheet T36904 row 16: "2. Ejercicio y periodo. Periodo"
    # AEAT manual section 2 heading: "2. Ejercicio y periodo"
    # Accents stripped to match pdfplumber ASCII extraction path.
    c.drawString(20 * mm, y, f"Ejercicio: {fixture.ejercicio}")
    y -= 6 * mm
    c.drawString(20 * mm, y, f"Periodo: {fixture.periodo}")
    y -= 10 * mm
    c.drawString(20 * mm, y, "Ejemplar para el obligado tributario")
    y -= 8 * mm
    # Justificante receipt trailer â€” required by TestRealCorpusParses and sidecar roundtrip test.
    # M369 is quarterly; Ejercicio and Periodo labels are already printed above.
    csv_val = f"SANITIZED369{fixture.ejercicio}"
    c.drawString(20 * mm, y, f"Codigo Seguro de Verificacion: {csv_val}")
    y -= 6 * mm
    c.drawString(20 * mm, y, "Fecha y hora de presentacion: 2024-01-01 10:00:00")
    y -= 6 * mm
    c.drawString(20 * mm, y, "Fecha de alta de la actividad: 01-01-1900")
    y -= 6 * mm
    c.drawString(20 * mm, y, _SEDE_ORIGIN)


@dataclass(frozen=True)
class _Modelo193Fixture:
    """Sanitized M193 resumen-anual declaracion fixture.

    Labels are taken verbatim from the AEAT-published DiseÃ±o de Registro at:
      src/aeat/_data/corpus/aeat_official/disenos_registro/modelo_193/files/
        03-193-orden-hac-56-2024-ejercicios-2024-y-siguientes-556-kb-pdf.pdf
    Pages 5-6, Tipo de registro 1 (Registro de Declarante):
      136-144: "NÃšMERO TOTAL DE PERCEPTORES"
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
    resumen section from the AEAT-published DiseÃ±o de Registro (Orden
    HAC/56/2024, pages 5-6).

    Label text is AEAT-grounded:
      - "Numero total de perceptores" from DR positions 136-144
        "NÃšMERO TOTAL DE PERCEPTORES"
      - "Base retenciones e ingresos a cuenta total" â€” DR positions 145-159
        "BASE RETENCIONES E INGRESOS A CUENTA" with " total" appended to
        disambiguate summary row from per-perceptor rows (M180 convention)
      - "Retenciones e ingresos a cuenta total" â€” DR positions 160-174
        "RETENCIONES E INGRESOS A CUENTA" with " total" appended (same reason)

    Accents stripped to match pdfplumber ASCII extraction path (consistent with
    M180/M349/M840/M036 fixture conventions).

    Non-tautology proof: the label_patterns in the declaracion_pdf profile
    ('N[uÃº]mero\\s+total\\s+de\\s+perceptores',
     'Base\\s+retenciones\\s+e\\s+ingresos\\s+a\\s+cuenta\\s+total',
     'Retenciones\\s+e\\s+ingresos\\s+a\\s+cuenta\\s+total') are grounded
    against the AEAT-published DiseÃ±o de Registro â€” NOT the registry casilla
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
    # Resumen-declarante casillas â€” label text grounded in AEAT DR pages 5-6.
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
    y -= 8 * mm
    # Justificante receipt trailer â€” required by TestRealCorpusParses and sidecar roundtrip test.
    # M193 prints "Periodo: 0A" above, so the parser extracts "0A" as the period.
    # TestRealCorpusParses explicit_annual_fixtures includes ("193", "2024-0A") to match.
    csv_val = f"SANITIZED193{fixture.ejercicio}"
    c.drawString(20 * mm, y, f"Codigo Seguro de Verificacion: {csv_val}")
    y -= 6 * mm
    c.drawString(20 * mm, y, "Fecha y hora de presentacion: 2024-01-01 10:00:00")
    y -= 6 * mm
    c.drawString(20 * mm, y, "Fecha de alta de la actividad: 01-01-1900")
    y -= 6 * mm
    c.drawString(20 * mm, y, _SEDE_ORIGIN)


@dataclass(frozen=True)
class _Modelo115Fixture:
    """Sanitized M115 quarterly retenciones-arrendamientos autoliquidacion fixture.

    Labels are taken verbatim from the AEAT-published DiseÃ±o de Registro (DR) XLS at:
      src/aeat/_data/corpus/aeat_official/disenos_registro/modelo_115/files/
        01-115-orden-eha-3435-2007-ejercicios-2019-y-siguientes-actualizado-febrero-2019-172-kb-xls.xls
    Sheet "DR 11501", rows 16-20 (field descriptions, Windows-1252 decoded):
      row 16: "Retenciones e ingresos a cuenta. NÃºmero perceptores [01]"
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
    casilla) â€” NOT the registry casilla label fields.  A pattern that drifts from the
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
    y -= 8 * mm
    # Justificante receipt trailer â€” required by TestRealCorpusParses and sidecar roundtrip test.
    # M115 is quarterly; Ejercicio and Periodo labels are already printed above.
    csv_val = f"SANITIZED115{fixture.ejercicio}"
    c.drawString(20 * mm, y, f"Codigo Seguro de Verificacion: {csv_val}")
    y -= 6 * mm
    c.drawString(20 * mm, y, "Fecha y hora de presentacion: 2024-01-01 10:00:00")
    y -= 6 * mm
    c.drawString(20 * mm, y, "Fecha de alta de la actividad: 01-01-1900")
    y -= 6 * mm
    c.drawString(20 * mm, y, _SEDE_ORIGIN)


@dataclass(frozen=True)
class _Modelo720Fixture:
    """Sanitized M720 foreign-asset informative declaracion fixture.

    The ejercicio label text is derived from the AEAT-published diseÃ±o de registro
    for Modelo 720, available at:
      https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/
        DR_Resto_Mod/archivos/modelo_720.pdf
    Downloaded 2026-05-27 and saved at:
      src/aeat/_data/corpus/aeat_official/instructions/modelo_720/files/
        modelo-720-aeat-dr.pdf

    The record-type-1 field at positions 5-8 is named "EJERCICIO" in the record
    design.  The AEAT printed-form label for the ejercicio field uses the longer
    descriptive text "Ejercicio al que se refiere la informaciÃ³n" â€” the phrase
    "al que se refiere la informaciÃ³n" is grounded in the Orden HAP/72/2013 Art. 7
    phrasing ("al que se refiera la informaciÃ³n a suministrar") and the registry
    casilla label from aeat-dr-720.  This is the standard informative-model
    convention: declaraciÃ³n informativa fields refer to "la informaciÃ³n", not
    "la declaraciÃ³n".

    The label_pattern 'Ejercicio\\s+al\\s+que\\s+se\\s+refiere\\s+la\\s+informaci[oÃ³]n'
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
    full-form descriptive text found in the AEAT-published diseÃ±o de registro
    and Orden HAP/72/2013:

      "Ejercicio al que se refiere la informacion"

    (accents stripped to stay within the ASCII-safe pdfplumber extraction path,
    consistent with M349/M840/M036/M369 fixture conventions).  The value
    follows on the same line so the named_label parser captures the trailing
    token.

    Non-tautology proof: the label_pattern
    'Ejercicio\\s+al\\s+que\\s+se\\s+refiere\\s+la\\s+informaci[oÃ³]n' is grounded
    against the AEAT-published aeat-dr-720 field description and the Orden
    HAP/72/2013 Art. 7 phrasing â€” NOT simply mirroring the registry casilla.id
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
    y -= 8 * mm
    # Justificante receipt trailer â€” required by TestRealCorpusParses and sidecar roundtrip test.
    # M720 has no Periodo label; parser fallback returns the ejercicio year as period.
    csv_val = f"SANITIZED720{fixture.ejercicio}"
    c.drawString(20 * mm, y, f"Codigo Seguro de Verificacion: {csv_val}")
    y -= 6 * mm
    c.drawString(20 * mm, y, "Fecha y hora de presentacion: 2024-01-01 10:00:00")
    y -= 6 * mm
    c.drawString(20 * mm, y, "Fecha de alta de la actividad: 01-01-1900")
    y -= 6 * mm
    c.drawString(20 * mm, y, _SEDE_ORIGIN)


@dataclass(frozen=True)
class _Modelo036Fixture:
    """Sanitized M036 declaracion-censal fixture.

    The section heading label is taken verbatim from the AEAT-published practical
    guide "Instrucciones Modelo 036", PAGINA 1 (h3 element):
      "Causas de presentaciÃ³n de la declaraciÃ³n"
    Source: sede.agenciatributaria.gob.es/.../cumplimentacion-modelo/pagina-1.html
    Fetched 2026-05-27 and saved at:
      src/aeat/_data/corpus/aeat_official/instructions/modelo_036/files/
        instrucciones-cumplimentacion-pagina-1.html

    The named_label parser matches label_pattern against this heading and captures
    the event-kind value (Alta/Modificacion/Baja) on the same line.

    ``ejercicio`` is included so the sidecar CSV token SANITIZED036{ejercicio} can be
    derived deterministically.  M036 has no calendar period (it uses event codes
    alta/modificacion/baja), so the justificante trailer does not print a Periodo label.
    """

    filename: str
    ejercicio: str
    tax_id: str
    full_name: str
    event_kind: str
    presented_at: str = "2025-01-01 10:00:00"


_MODELO_036_FIXTURES: tuple[_Modelo036Fixture, ...] = (
    _Modelo036Fixture(
        filename="036/2025-0A.pdf",
        ejercicio="2025",
        tax_id="Y0000001S",
        full_name="DEMO EMPRESA SL",
        event_kind="Alta",
    ),
    _Modelo036Fixture(
        filename="036/2025-alta.pdf",
        ejercicio="2025",
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
    y -= 6 * mm
    # Ejercicio label â€” required by the justificante parser's _extract_period_and_ejercicio
    # to locate the fiscal year.  M036 has no Periodo token; the parser falls back to
    # returning the ejercicio year as the period, consistent with other annual declaraciones.
    c.drawString(20 * mm, y, f"Ejercicio: {fixture.ejercicio}")
    y -= 10 * mm
    # PAGINA 1 section heading â€” label text verbatim from AEAT practical guide
    # instrucciones-cumplimentacion-pagina-1.html (h3):
    # "Causas de presentaciÃ³n de la declaraciÃ³n"
    # Accents stripped to match pdfplumber ASCII extraction path.
    c.drawString(
        20 * mm,
        y,
        f"Causas de presentacion de la declaracion {fixture.event_kind}",
    )
    y -= 10 * mm
    c.drawString(20 * mm, y, "Ejemplar para el obligado tributario")
    y -= 8 * mm
    # Justificante receipt trailer â€” required by TestRealCorpusParses and sidecar roundtrip test.
    # M036 has no calendar Periodo; the CSV token uses the ejercicio year.
    # SANITIZED036{ejercicio} matches _CSV_SYNTHETIC_RE in the sidecar roundtrip test.
    csv_val = f"SANITIZED036{fixture.ejercicio}"
    c.drawString(20 * mm, y, f"Codigo Seguro de Verificacion: {csv_val}")
    y -= 6 * mm
    c.drawString(20 * mm, y, f"Fecha y hora de presentacion: {fixture.presented_at}")
    y -= 6 * mm
    c.drawString(20 * mm, y, "Fecha de alta de la actividad: 01-01-1900")
    y -= 6 * mm
    c.drawString(20 * mm, y, _SEDE_ORIGIN)
