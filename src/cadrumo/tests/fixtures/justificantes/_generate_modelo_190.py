"""Synthetic Modelo 190 resumen-anual declaracion fixture.

Modelo 190 is a perceptor-level informative declaration: a type-1 declarante
record carrying the summary totals, followed by one type-2 record per
percepcion. The record structure is fixed by the diseno de registro in Orden
EHA/3127/2009, bundled at
``_data/corpus/normatives/html/orden-eha-3127-2009.html``. Two of its field
definitions are what the summary page below renders:

- positions 146-160, IMPORTE TOTAL DE LAS PERCEPCIONES: "la suma de las
  cantidades, sin coma decimal, reflejadas en las percepciones integras
  satisfechas (posiciones 82 a 94, 109 a 121, 256 a 268 y 283-295,
  correspondientes a los registros de percepciones), con independencia de la
  clave de percepcion a la que correspondan".
- positions 161-175, IMPORTE TOTAL DE LAS RETENCIONES E INGRESOS A CUENTA: "la
  suma de las cantidades reflejadas en los campos 'Retenciones practicadas',
  'Ingresos a cuenta efectuados', 'Retenciones practicadas sobre prestaciones
  derivadas de incapacidad laboral' e 'Ingresos a cuenta efectuados por
  prestaciones en especie derivadas de incapacidad laboral'".

Both totals are therefore sums over the type-2 records. This specimen carries
exactly one percepcion, so its two printed totals equal that record's two
printed amounts and its percepcion count is 1. That is the diseno's arithmetic,
not a tax claim.

This generator replaces a real sanitised specimen. The layout facts it
reproduces are the ones committed tests read:

- **The three numbered summary lines.** Label, dot leader, box number, amount,
  all on one printed line, which is what lets a label pattern anchored on the
  wording reach the right amount and what lets a box-number-anchored regex find
  it. The registry ``declaracion_pdf`` profile targets all three and floors at
  full coverage.
- **The perceptor identity row followed immediately by "Datos de la
  percepcion".** A cross-dependency test locates the type-2 record by that
  two-line shape, so the NIF must open its own line and the next line must open
  on that heading.
- **The clave/subclave line.** ``Clave: G Subclave: 01`` -- actividades
  profesionales -- read as the record's classification.
- **The wrapped "incapacidad laboral:" amount row.** AEAT breaks the label
  across two lines and prints the percepcion integra and the retencion
  practicada as the two trailing tokens of the second, which is the shape the
  detail reader matches.
- **The justificante trailer.** CSV, NIF, presentation timestamp and sede URL,
  and no labelled periodo -- this form prints only the ejercicio, and the
  sidecar roundtrip gate records that as an expected quirk of Modelo 190.

The amounts are PROBES. They assert no tax fact and no AEAT figure. They are
DISTINCT from one another on purpose: the specimen this replaces printed the
same redaction constant into both totals, so a reader that crossed
``percepciones-total`` with ``retenciones-total`` saw the same number and
nothing failed.

What this file CANNOT carry is AEAT behaviour nobody has looked for yet. It is
the only Modelo 190 render in the tree, so with the real specimen gone there is
no externally-authored evidence of this form's layout left; that gap is real.

See Also:
    :mod:`~adapters.inbound.declaracion.tests.test_parser_boundary_m190`
        Consumes this fixture through the full parser boundary.
"""

from __future__ import annotations

from dataclasses import dataclass

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from ._generate_base import _SEDE_ORIGIN


@dataclass(frozen=True)
class _Modelo190Percepcion:
    """One type-2 percepcion record as the interior sheet prints it."""

    perceptor_tax_id: str
    perceptor_name: str
    provincia: str
    clave: str
    subclave: str
    percepcion_integra: str
    retencion_practicada: str


@dataclass(frozen=True)
class _Modelo190Fixture:
    filename: str
    ejercicio: str
    tax_id: str
    full_name: str
    contact_phone: str
    contact_email: str
    total_percepciones: str
    importe_percepciones: str
    importe_retenciones: str
    percepciones: tuple[_Modelo190Percepcion, ...]


_MODELO_190_FIXTURES: tuple[_Modelo190Fixture, ...] = (
    _Modelo190Fixture(
        filename="190/2024-0A.pdf",
        ejercicio="2024",
        tax_id="Y0000001S",
        full_name="APELLIDO APELLIDO NOMBRE",
        contact_phone="000000000",
        contact_email="correo@example.invalid",
        # One type-2 record, so the two totals are that record's two amounts
        # and the count is 1 -- the diseno's own arithmetic (positions 146-160
        # and 161-175 are sums over the percepcion records).
        total_percepciones="1",
        importe_percepciones="12.345,60",
        importe_retenciones="1.851,84",
        percepciones=(
            _Modelo190Percepcion(
                # NIE-SHAPED but deliberately control-letter INVALID: the
                # AEAT algorithm gives Q for Y0000002, not A. Two reasons.
                # A checksum-invalid identifier cannot be a real person's under
                # any reading, which is a stronger guarantee than declaring it
                # in a manifest -- and declaring it is not available here
                # anyway, because the sidecar roundtrip gate identifies the
                # filer by finding exactly ONE tax-id-shaped token in
                # ``replacements_applied``, so a second one would silently drop
                # this fixture out of that gate. Nothing validates a perceptor
                # id (``WithholdingObservation.perceptor_tax_id`` is a bounded
                # free string) and nothing asserts this value; the detail
                # reader needs only nine alphanumerics opening the line.
                perceptor_tax_id="Y0000002A",
                perceptor_name="APELLIDO APELLIDO NOMBRE",
                provincia="08",
                clave="G",
                subclave="01",
                percepcion_integra="12.345,60",
                retencion_practicada="1.851,84",
            ),
        ),
    ),
)

_BODY_FONT = "Helvetica"
_BODY_SIZE = 7.0


def _leader(label: str, box: str, amount: str) -> str:
    """One numbered summary line: label, dot leader, box number, amount.

    The dot leader is what AEAT prints; the box number and the amount must be
    the last two tokens on the line, in that order, because the extraction
    target reads the line's final token as its value and the cross-dependency
    reader anchors on the box number that precedes it.
    """
    return f"{label} {'.' * 12} {box} {amount}"


def _draw_modelo_190(c: canvas.Canvas, fixture: _Modelo190Fixture) -> None:
    """Render the three-page resumen-anual specimen onto ``c``."""
    _, height = A4
    csv_value = f"SANITIZED190{fixture.ejercicio}"
    justificante = "1900000000000"

    def _new_page() -> float:
        c.setFont(_BODY_FONT, _BODY_SIZE)
        return height - 22 * mm

    def _footer() -> None:
        c.setFont(_BODY_FONT, _BODY_SIZE)
        c.drawString(
            18 * mm,
            14 * mm,
            "La autenticidad de este documento puede ser comprobada mediante el Código Seguro",
        )
        c.drawString(18 * mm, 10 * mm, f"de Verificación {csv_value} en {_SEDE_ORIGIN}")

    def _lines(y: float, lines: tuple[str, ...], *, step: float = 5 * mm) -> float:
        c.setFont(_BODY_FONT, _BODY_SIZE)
        for line in lines:
            c.drawString(18 * mm, y, line)
            y -= step
        return y

    # --- page 1: informacion de la presentacion (the justificante trailer) ---
    y = _new_page()
    c.setFont("Helvetica-Bold", 11)
    c.drawString(18 * mm, y, "INFORMACIÓN DE LA PRESENTACIÓN DE LA DECLARACIÓN")
    y -= 8 * mm
    y = _lines(
        y,
        (
            "Modelo 190",
            "Registro",
            "Presentación realizada el: 01-01-1900 a las 20:31:00",
            f"Expediente/Referencia (nº registro asignado): {justificante}",
            f"Código Seguro de Verificación: {csv_value}",
            f"Número de justificante: {justificante}",
            "Vía de entrada: Presentación por Internet",
            "Presentador",
            f"NIF Presentador: {fixture.tax_id}",
            f"Apellidos y Nombre / Razón social: {fixture.full_name}",
            "En calidad de: Titular",
        ),
    )
    _footer()
    c.showPage()

    # --- page 2: hoja resumen ---
    y = _new_page()
    y = _lines(
        y,
        (
            "Agencia Tributaria",
            "Retenciones e ingresos a cuenta del IRPF   Hoja Resumen",
            "Rendimientos del trabajo y de actividades económicas, premios y   Modelo 190",
            "determinadas ganancias patrimoniales e imputaciones de renta",
            f"MINISTERIO DE HACIENDA   {_SEDE_ORIGIN}   Resumen anual",
            "Declarante",
            f"Ejercicio (con 4 cifras) ....... {fixture.ejercicio}",
            "N.º de identificación fiscal (NIF)",
            f"{fixture.tax_id}   Modalidad de presentación: Telemática ..... X",
            "Apellidos y nombre (por este orden), denominación o razón social del declarante",
            fixture.full_name,
            f"Nº de justificante: {justificante}",
            "Persona con la que relacionarse y datos de contacto",
            "Apellidos y nombre",
            fixture.full_name,
            f"Teléfono {fixture.contact_phone}",
            f"Correo electrónico {fixture.contact_email}",
            "Declaración complementaria o sustitutiva",
            "Declaración complementaria por inclusión de datos .....",
            "Número identificativo de la declaración anterior .......",
            "Declaración sustitutiva ....................................................",
        ),
    )
    y -= 3 * mm
    c.setFont("Helvetica-Bold", 8)
    c.drawString(18 * mm, y, "Resumen de los datos incluidos en la declaración")
    y -= 7 * mm
    y = _lines(
        y,
        (
            _leader(
                "Número total de percepciones relacionadas en la declaración (1)",
                "01",
                fixture.total_percepciones,
            ),
            _leader("Importe total de las percepciones relacionadas", "02", fixture.importe_percepciones),
            _leader(
                "Importe total de las retenciones e ingresos a cuenta relacionados",
                "03",
                fixture.importe_retenciones,
            ),
        ),
    )
    y -= 2 * mm
    # The form's own footnote. Deliberately worded as AEAT words it -- "el
    # numero total de los apuntes o registros de percepcion" -- which does NOT
    # contain the "numero total de percepciones" phrase the extraction target
    # anchors on, so the target stays unambiguous.
    y = _lines(
        y,
        (
            "(1) Consigne el número total de los apuntes o registros de percepción contenidos en las hojas",
            "interiores de esta declaración o en el soporte.",
            "Fecha y firma",
            "Firma:",
        ),
    )
    _footer()
    c.showPage()

    # --- page 3: relacion de percepciones (type-2 records) ---
    y = _new_page()
    y = _lines(
        y,
        (
            "Agencia Tributaria   Modelo 190",
            "Retenciones e ingresos a cuenta del IRPF   Relación de percepciones",
            "Datos identificativos de esta hoja interior",
            "NIF del declarante   Ejercicio",
            f"{fixture.tax_id}   {fixture.ejercicio}",
            f"Nº de justificante: {justificante}",
        ),
    )
    for index, percepcion in enumerate(fixture.percepciones, start=1):
        y -= 3 * mm
        y = _lines(
            y,
            (
                f"Percepción {index}",
                "NIF del perceptor   NIF del representante legal   Apellidos y nombre del perceptor "
                "o denominación de la entidad perceptora   Provincia",
                # The identity row: the perceptor NIF opens the line and the
                # next line opens on "Datos de la percepcion". That two-line
                # shape is how the type-2 record is located.
                f"{percepcion.perceptor_tax_id}   {percepcion.perceptor_name}   {percepcion.provincia}",
                "Datos de la percepción   Ejercicio de devengo   Ceuta o Melilla",
                f"Clave: {percepcion.clave}   Subclave: {percepcion.subclave}",
                "Percepción íntegra   Retenciones practicadas",
                # AEAT wraps this label across two lines and prints the two
                # amounts as the trailing tokens of the second.
                "Percepciones dinerarias NO derivadas de",
                f"incapacidad laboral: {percepcion.percepcion_integra}   {percepcion.retencion_practicada}",
                "Valoración   Ingresos a cuenta efectuados   Ingresos a cuenta repercutidos",
                "Percepciones en especie NO derivadas de",
                "incapacidad laboral:",
                "Percepción íntegra   Retenciones practicadas",
                "Percepciones dinerarias derivadas de",
                "incapacidad laboral:",
                "Valoración   Ingresos a cuenta efectuados   Ingresos a cuenta repercutidos",
                "Percepciones en especie derivadas de",
                "incapacidad laboral:",
            ),
        )
    _footer()


__all__ = [
    "_MODELO_190_FIXTURES",
    "_Modelo190Fixture",
    "_Modelo190Percepcion",
    "_draw_modelo_190",
]
