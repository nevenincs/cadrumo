"""Synthetic justificante fixtures for annual and specialist modelo families."""

from __future__ import annotations

from dataclasses import dataclass

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from ....core.casilla_id import CasillaId, validated_casilla_id
from ._generate_base import _SEDE_ORIGIN


@dataclass(frozen=True)
class _Modelo232Fixture:
    """Sanitized M232 declaracion informativa fixture.

    Labels are taken verbatim from the AEAT-published DiseÃ±o de Registro at:
      src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_232/files/
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
    AEAT-published DiseÃ±o de Registro (DR23200/DR23201 sheets in both XLSX files).
    Label text is verbatim from the AEAT DR field descriptions â€” NOT the registry
    casilla label fields â€” so the named_label parser exercises real grounding:

      "Ejercicio de devengo" â€” DR23200 row 9: "Ejercicio de devengo (EEEE)"
      "Tipo de Ejercicio"    â€” DR23201 row 17: "2.Devengo - Tipo de Ejercicio"
      "C.N.A.E. actividad principal" â€” DR23201 row 20: "2.Devengo - C.N.A.E. actividad principal"

    Accents stripped to stay within the ASCII-safe pdfplumber extraction path
    (consistent with M349/M840/M036/M180/M369/M720 fixture conventions).

    Non-tautology proof: the profile patterns are grounded against the AEAT DR
    field description strings â€” NOT the registry casilla label fields ('ejercicio-devengo',
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
    # Section 2 (Devengo) field labels â€” verbatim from AEAT DR, accents stripped.
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
    y -= 8 * mm
    # Justificante receipt trailer â€” required by TestRealCorpusParses and sidecar roundtrip test.
    # M232 is annual (no Periodo label). CSV token uses the ejercicio year.
    csv_val = f"SANITIZED232{fixture.ejercicio}"
    c.drawString(20 * mm, y, f"Codigo Seguro de Verificacion: {csv_val}")
    y -= 6 * mm
    c.drawString(20 * mm, y, "Fecha y hora de presentacion: 2024-01-01 10:00:00")
    y -= 6 * mm
    c.drawString(20 * mm, y, "Fecha de alta de la actividad: 01-01-1900")
    y -= 6 * mm
    c.drawString(20 * mm, y, _SEDE_ORIGIN)


@dataclass(frozen=True)
class _Modelo123Fixture:
    """Sanitized M123 autoliquidacion fixture â€” numeric_casilla layout verification.

    Ground truth is the AEAT-published DiseÃ±o de Registro Modelo 123 available at:
      https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/
        DR_100_199/archivos/DR123v20.xlsx  (2024+ revision, Orden HAC/56/2024)
    and the Orden EHA/3435/2007 form for the 2019-2023 revision.

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
    - 2023-1T.pdf: 2019-2023 revision (Orden EHA/3435/2007), 8 casillas.
      Casilla IDs use the official bare box numbers (01..08). Amounts satisfy:
      [06]=[03]+[05], [08]=[06]-[07].
    """

    filename: str
    ejercicio: str
    periodo: str
    tax_id: str
    full_name: str
    render_rows: tuple[tuple[CasillaId, str, str], ...]  # (casilla_id, printed_number, spanish_formatted_amount)


_MODELO_123_2024_RENDER_ROWS: tuple[tuple[CasillaId, str, str], ...] = (
    # 2024-y-siguientes revision: 14 casillas.
    # Amounts chosen to satisfy all 5 registry formulas:
    #   [03] = [01] + [02]  =  5,00 + 3,00 = 8,00
    #   [06] = [04] + [05]  =  10.000,00 + 5.000,00 = 15.000,00
    #   [09] = [07] + [08]  =  1.900,00 + 950,00 = 2.850,00
    #   [12] = [09] + [11]  =  2.850,00 + 0,00 = 2.850,00
    #   [14] = [12] - [13]  =  2.850,00 - 0,00 = 2.850,00
    # Integer casillas use NN,00 format so SPANISH_AMOUNT_GROUP regex (requires comma) matches.
    (validated_casilla_id("01", surface="justificante fixture casilla id"), "01", "5,00"),
    (validated_casilla_id("02", surface="justificante fixture casilla id"), "02", "3,00"),
    (validated_casilla_id("03", surface="justificante fixture casilla id"), "03", "8,00"),
    (validated_casilla_id("04", surface="justificante fixture casilla id"), "04", "10.000,00"),
    (validated_casilla_id("05", surface="justificante fixture casilla id"), "05", "5.000,00"),
    (validated_casilla_id("06", surface="justificante fixture casilla id"), "06", "15.000,00"),
    (validated_casilla_id("07", surface="justificante fixture casilla id"), "07", "1.900,00"),
    (validated_casilla_id("08", surface="justificante fixture casilla id"), "08", "950,00"),
    (validated_casilla_id("09", surface="justificante fixture casilla id"), "09", "2.850,00"),
    (validated_casilla_id("10", surface="justificante fixture casilla id"), "10", "0,00"),
    (validated_casilla_id("11", surface="justificante fixture casilla id"), "11", "0,00"),
    (validated_casilla_id("12", surface="justificante fixture casilla id"), "12", "2.850,00"),
    (validated_casilla_id("13", surface="justificante fixture casilla id"), "13", "0,00"),
    (validated_casilla_id("14", surface="justificante fixture casilla id"), "14", "2.850,00"),
)

_MODELO_123_2023_RENDER_ROWS: tuple[tuple[CasillaId, str, str], ...] = (
    # 2019-2023 revision: 8 casillas using official bare box numbers (01..08).
    # Amounts satisfy: [06]=[03]+[05]=1.520,00+0,00=1.520,00, [08]=[06]-[07]=1.520,00-0,00=1.520,00
    # Integer casilla uses N,00 format so SPANISH_AMOUNT_GROUP regex (requires comma) matches.
    (validated_casilla_id("01", surface="justificante fixture casilla id"), "01", "4,00"),
    (validated_casilla_id("02", surface="justificante fixture casilla id"), "02", "8.000,00"),
    (validated_casilla_id("03", surface="justificante fixture casilla id"), "03", "1.520,00"),
    (validated_casilla_id("04", surface="justificante fixture casilla id"), "04", "0,00"),
    (validated_casilla_id("05", surface="justificante fixture casilla id"), "05", "0,00"),
    (validated_casilla_id("06", surface="justificante fixture casilla id"), "06", "1.520,00"),
    (validated_casilla_id("07", surface="justificante fixture casilla id"), "07", "0,00"),
    (validated_casilla_id("08", surface="justificante fixture casilla id"), "08", "1.520,00"),
)

_MODELO_123_FIXTURES: tuple[_Modelo123Fixture, ...] = (
    _Modelo123Fixture(
        filename="123/2024-1T.pdf",
        ejercicio="2024",
        periodo="1T",
        tax_id="Y0000001S",
        full_name="DEMO EMPRESA SL",
        render_rows=_MODELO_123_2024_RENDER_ROWS,
    ),
    _Modelo123Fixture(
        filename="123/2023-1T.pdf",
        ejercicio="2023",
        periodo="1T",
        tax_id="Y0000001S",
        full_name="DEMO EMPRESA SL",
        render_rows=_MODELO_123_2023_RENDER_ROWS,
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
    # Casilla block: printed AEAT box number at line start, amount on the same line.
    # The parser resolves this printed number back to the canonical registry casilla_id.
    for _casilla_id, printed_number, amount in fixture.render_rows:
        c.drawString(20 * mm, y, f"{printed_number}  {amount}")
        y -= 6 * mm
    y -= 4 * mm
    c.drawString(20 * mm, y, "Ejemplar para el obligado tributario")
    y -= 8 * mm
    # Justificante receipt trailer â€” required by TestRealCorpusParses and sidecar roundtrip test.
    # M123 is quarterly; Ejercicio and Periodo labels are already printed above.
    csv_val = f"SANITIZED123{fixture.ejercicio}"
    c.drawString(20 * mm, y, f"Codigo Seguro de Verificacion: {csv_val}")
    y -= 6 * mm
    c.drawString(20 * mm, y, "Fecha y hora de presentacion: 2024-01-01 10:00:00")
    y -= 6 * mm
    c.drawString(20 * mm, y, "Fecha de alta de la actividad: 01-01-1900")
    y -= 6 * mm
    c.drawString(20 * mm, y, _SEDE_ORIGIN)


@dataclass(frozen=True)
class _Modelo347Fixture:
    """Sanitized M347 declaracion informativa anual de operaciones con terceras personas fixture.

    The ejercicio label text is grounded against the AEAT-published DiseÃ±o de Registro
    for Modelo 347 (Orden HAC/1431/2025), record-type-1 field at positions 5-8:
      "EJERCICIO â€” Las cuatro cifras del ejercicio fiscal al que corresponde la declaraciÃ³n."
    Source:
      src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_347/files/
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
    from the AEAT-published DiseÃ±o de Registro (Orden HAC/1431/2025).  The ejercicio
    label uses the short-form "Ejercicio:" consistent with M349/M180/M369 justificante
    conventions and grounded in the DR field name "EJERCICIO" (positions 5-8).

    Non-tautology proof: the label_pattern 'Ejercicio:' is grounded against the AEAT
    DR field name for positions 5-8 of the tipo-1 record â€” NOT derived from the
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
    y -= 8 * mm
    # Justificante receipt trailer â€” required by TestRealCorpusParses and sidecar roundtrip test.
    # M347 has no Periodo label; parser fallback returns the ejercicio year as period.
    csv_val = f"SANITIZED347{fixture.ejercicio}"
    c.drawString(20 * mm, y, f"Codigo Seguro de Verificacion: {csv_val}")
    y -= 6 * mm
    c.drawString(20 * mm, y, "Fecha y hora de presentacion: 2024-01-01 10:00:00")
    y -= 6 * mm
    c.drawString(20 * mm, y, "Fecha de alta de la actividad: 01-01-1900")
    y -= 6 * mm
    c.drawString(20 * mm, y, _SEDE_ORIGIN)


@dataclass(frozen=True)
class _Modelo184Fixture:
    """Sanitized M184 declaracion informativa fixture.

    The ejercicio label text is derived from the AEAT-published DiseÃ±o de
    Registro for Modelo 184 (DR_Modelo_184_2025.pdf, Orden HAC/1430/2025),
    downloaded 2026-05-27 from:
      https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/
        DR_100_199/DR_Modelo_184_2025.pdf
    Saved at:
      src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_184/files/
        01-184-ejercicio-2025-y-siguientes-modificados-por-orden-hac-1430-2025-de-3-de-diciembre-365-kb.pdf

    Registro de tipo 1, positions 5-8: "EJERCICIO"
      "Las cuatro cifras del ejercicio fiscal al que corresponde la declaracion"

    The printed field name is the bare word "EJERCICIO"; informativa
    justificantes render this as "Ejercicio: <YYYY>".  The label_pattern
    'Ejercicio' targets this printed token.

    decl.tipo-declaracion is NOT included because positions 121-122 of
    registro de tipo 1 are "DECLARACION COMPLEMENTARIA O SUSTITUTIVA" â€”
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
    DiseÃ±o de Registro (DR_Modelo_184_2025.pdf, registro de tipo 1 positions
    5-8 "EJERCICIO"):

      "Ejercicio: <YYYY>"

    Non-tautology proof: the label_pattern 'Ejercicio' is grounded against the
    AEAT DR field name â€” NOT the registry casilla label field.  A pattern
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
    # Datos del Declarante: ejercicio field â€” bare label from DR positions 5-8 "EJERCICIO"
    c.drawString(20 * mm, y, f"Ejercicio: {fixture.ejercicio}")
    y -= 10 * mm
    c.drawString(20 * mm, y, "Ejemplar para el obligado tributario")
    y -= 8 * mm
    # Justificante receipt trailer â€” required by TestRealCorpusParses and sidecar roundtrip test.
    # M184 has no Periodo label; parser fallback returns the ejercicio year as period.
    csv_val = f"SANITIZED184{fixture.ejercicio}"
    c.drawString(20 * mm, y, f"Codigo Seguro de Verificacion: {csv_val}")
    y -= 6 * mm
    c.drawString(20 * mm, y, "Fecha y hora de presentacion: 2024-01-01 10:00:00")
    y -= 6 * mm
    c.drawString(20 * mm, y, "Fecha de alta de la actividad: 01-01-1900")
    y -= 6 * mm
    c.drawString(20 * mm, y, _SEDE_ORIGIN)


@dataclass(frozen=True)
class _Modelo131Fixture:
    """Sanitized M131 IRPF pago-fraccionado estimacion-objetiva fixture.

    Layout verdict: GAP-DOCUMENTED (line-end box numbers, numeric_casilla fails).

    Ground truth is the AEAT-published DR xlsx for M131 2026 at:
      src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_131/files/
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
    printed_rows: tuple[tuple[str, str, str], ...]  # (box_number, label_text, spanish_amount)


_MODELO_131_PRINTED_ROWS: tuple[tuple[str, str, str], ...] = (
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
        # filename and ejercicio both use 2024 so TestRealCorpusParses passes the
        # ejercicio assertion (filepath stem "2024-1T" â†’ ejercicio_expected "2024").
        # The declaracion parser tests use aÃ±o_override=2026 explicitly, so they
        # are not affected by the ejercicio value printed in the PDF.
        filename="131/2024-1T.pdf",
        ejercicio="2024",
        periodo="1T",
        tax_id="Y0000001S",
        full_name="DEMO AUTONOMO EO",
        printed_rows=_MODELO_131_PRINTED_ROWS,
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
    for box_num, label, amount in fixture.printed_rows:
        dots = "." * max(2, 60 - len(label) - len(box_num) - len(amount))
        c.drawString(20 * mm, y, f"{label} {dots} {box_num}  {amount}")
        y -= 6 * mm
    y -= 4 * mm
    c.drawString(20 * mm, y, "Ejemplar para el obligado tributario")
    y -= 8 * mm
    # Justificante receipt trailer â€” required by TestRealCorpusParses and sidecar roundtrip test.
    # M131 is quarterly; Ejercicio and Periodo labels are already printed above.
    csv_val = f"SANITIZED131{fixture.ejercicio}"
    c.drawString(20 * mm, y, f"Codigo Seguro de Verificacion: {csv_val}")
    y -= 6 * mm
    c.drawString(20 * mm, y, "Fecha y hora de presentacion: 2024-01-01 10:00:00")
    y -= 6 * mm
    c.drawString(20 * mm, y, "Fecha de alta de la actividad: 01-01-1900")
    y -= 6 * mm
    c.drawString(20 * mm, y, _SEDE_ORIGIN)


@dataclass(frozen=True)
class _Modelo840Fixture:
    """Sanitized M840 declaracion fixture.

    Labels are taken verbatim from the AEAT-published printed form PDF at
    src/cadrumo/_data/corpus/aeat_official/forms/modelo_840/files/
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
    # Apartado II: Declaracion â€” labels verbatim from AEAT printed form (corpus-grounded)
    c.drawString(20 * mm, y, f"14Ejercicio: {fixture.ejercicio}")
    y -= 6 * mm
    c.drawString(20 * mm, y, f"15Declaracion de: {fixture.tipo_declaracion}")
    y -= 10 * mm
    c.drawString(20 * mm, y, "Ejemplar para la Administracion")
    y -= 8 * mm
    # Justificante receipt trailer â€” required by TestRealCorpusParses and sidecar roundtrip test.
    # M840 has no Periodo label; parser fallback returns the ejercicio year as period.
    csv_val = f"SANITIZED840{fixture.ejercicio}"
    c.drawString(20 * mm, y, f"Codigo Seguro de Verificacion: {csv_val}")
    y -= 6 * mm
    c.drawString(20 * mm, y, "Fecha y hora de presentacion: 2024-01-01 10:00:00")
    y -= 6 * mm
    c.drawString(20 * mm, y, "Fecha de alta de la actividad: 01-01-1900")
    y -= 6 * mm
    c.drawString(20 * mm, y, _SEDE_ORIGIN)


@dataclass(frozen=True)
class _Modelo202Fixture:
    """Sanitized M202 pago fraccionado liquidacion fixture.

    Box numbers and labels are taken verbatim from the bundled AEAT Diseno
    de Registro (per-clave [NN] notation confirmed against
    src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_202/files/
    01-202-ejercicio-2025-y-siguientes-actualizado-17-03-26-132-kb-xlsx.xlsx.extracted.md)
    and the AEAT-published instructions HTML
    (modelo-202-instrucciones-2023-2024.html), which references "clave 01",
    "clave 03", "clave 34" for the same casillas.

    No real M202 declaracion-copy PDF specimen is bundled, so the exact
    on-page label wording and column layout are unconfirmed (mirrors the
    M131 gap this fixture avoids repeating): this fixture renders each
    casilla as "<label> ... <box_number> <amount>" on one row so the
    bbox_anchored strategy (anchor on the box number, read the value
    immediately to its right) can locate and extract the value regardless
    of exact label wording.
    """

    filename: str
    ejercicio: str
    periodo: str
    tax_id: str
    full_name: str
    printed_rows: tuple[tuple[str, str, str], ...]  # (box_number, label_text, spanish_amount)


_MODELO_202_PRINTED_ROWS: tuple[tuple[str, str, str], ...] = (
    ("01", "Mod. 40.2 LIS Base del pago fraccionado", "50.000,00"),
    ("03", "Mod. 40.2 LIS A ingresar", "8.500,00"),
    ("04", "Mod. 40.3 LIS Resultado contable despues del IS", "140.000,00"),
    ("34", "Mod. 40.3 LIS Cantidad a ingresar", "29.400,00"),
)

_MODELO_202_FIXTURES: tuple[_Modelo202Fixture, ...] = (
    _Modelo202Fixture(
        filename="202/2025-1P.pdf",
        ejercicio="2025",
        periodo="1P",
        tax_id="B00000000",
        full_name="DEMO SOCIEDAD SL",
        printed_rows=_MODELO_202_PRINTED_ROWS,
    ),
)


def _draw_modelo_202(c: canvas.Canvas, fixture: _Modelo202Fixture) -> None:
    """Render a sanitized M202 liquidacion page onto ``c``.

    Layout reproduces the printed box-number notation confirmed in the
    bundled AEAT Diseno de Registro ("... [01]", "... [03]", "... [04]",
    "... [34]"): each row prints the descriptive label text followed by
    the box number, then the amount immediately to its right on the same
    row, so the bbox_anchored ``right_of_number`` strategy can resolve
    the value regardless of the exact label wording (no real specimen is
    bundled to confirm on-page wording -- see the fixture docstring).
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
        "Pago fraccionado Impuesto sobre Sociedades  Modelo 202",
    )
    y -= 12 * mm
    c.setFont("Helvetica", 10)
    c.drawString(20 * mm, y, f"NIF: {fixture.tax_id}")
    y -= 6 * mm
    c.drawString(20 * mm, y, f"Denominacion: {fixture.full_name}")
    y -= 6 * mm
    c.drawString(20 * mm, y, f"Ejercicio: {fixture.ejercicio}   Periodo: {fixture.periodo}")
    y -= 10 * mm
    for box_num, label, amount in fixture.printed_rows:
        dots = "." * max(2, 60 - len(label) - len(box_num))
        c.drawString(20 * mm, y, f"{label} {dots} {box_num} {amount}")
        y -= 6 * mm
    y -= 4 * mm
    c.drawString(20 * mm, y, "Ejemplar para el obligado tributario")
    y -= 8 * mm
    csv_val = f"SANITIZED202{fixture.ejercicio}"
    c.drawString(20 * mm, y, f"Codigo Seguro de Verificacion: {csv_val}")
    y -= 6 * mm
    c.drawString(20 * mm, y, "Fecha y hora de presentacion: 2025-04-15 10:00:00")
    y -= 6 * mm
    c.drawString(20 * mm, y, "Fecha de alta de la actividad: 01-01-1900")
    y -= 6 * mm
    c.drawString(20 * mm, y, _SEDE_ORIGIN)
