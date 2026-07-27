"""Synthetic Modelo 111 quarterly declaracion fixtures for 2024 1T-4T.

These four replace the real sanitised renders, which carried name-shaped
strings the redaction pipeline never wrote.

Modelo 111 is the only bundled family whose extraction is entirely
``bbox_anchored``: no target has a label pattern. The parser finds each
casilla's printed BOX NUMBER as a standalone word, then takes the nearest word
to its right on the same y-row, bounded by ``value_x_max``. Reproducing that
means reproducing GEOMETRY, not text -- so the coordinates below are not
decoration, they are the contract.

The layout facts reproduced, and why each one is here:

- **Three money columns at fixed x.** AEAT prints the perceptor count in
  column A, the base in column B and the retencion in column C. The registry
  profile pins the anchor bands to x0 250-290, 330-370 and 450-490, and bounds
  column A's value search at x < 345 and column B's at x < 459. The box-number
  x positions below sit inside those bands and the value x positions inside
  those bounds.
- **A blank cell must find nothing.** Boxes 01-06 and 10-27 are printed with no
  value on these renders, and the guard that keeps them absent is arithmetic:
  the next word to the right of a blank column-A box is column B's box number
  at x0 347, which exceeds column A's ``value_x_max`` of 345. Two points of
  margin. If the columns were drawn closer together every blank box would
  silently read the neighbouring column's box number as its amount. That is why
  the x positions are pinned here rather than chosen for looks.
- **The sparse filing.** 1T/2T/3T print exactly casillas 07/08/09/28/30 --
  this filer declared only rendimientos de actividades economicas -- and 4T
  prints casilla 30 alone. Both sets are pinned by the consuming tests, and the
  4T case exists precisely because a render that prints almost nothing is the
  one that catches an assertion guarded on inputs it does not have.
- **Casilla 07 is a COUNT, not money.** It is the number of perceptores, so it
  is a bare integer where 08 and 09 are Spanish-formatted amounts.
- **The box-number-only rows.** Boxes 01-06 and 10-27 are still PRINTED; a
  render that simply omitted them would stop exercising the blank-cell arm
  entirely, and every one of those targets would be absent for the wrong
  reason.

The amounts are PROBES. They assert no tax fact and no AEAT figure. Within a
quarter the count, the base and the retencion are pairwise distinct, and every
quarter uses different amounts, so a test that read the wrong quarter's fixture
names itself. Casillas 09, 28 and 30 DO repeat inside a quarter, and that is
the form's own arithmetic rather than laziness: with only epigrafe 3 filled and
no prior autoliquidacion, ``28 = 03+06+09+...+27`` reduces to ``09`` and
``30 = 28 - 29`` reduces to ``28``. Printing three different numbers there
would render a form that contradicts its own stated formula, which is a worse
fixture than a repeated value.

What these files CANNOT carry is the class of AEAT behaviour nobody has looked
for yet. With all four replaced, Modelo 111 has no externally-authored render
left in the tree.

See Also:
    :mod:`~adapters.inbound.declaracion.tests.test_parser_boundary_m111`
        Consumes these fixtures through the full parser boundary.
    :mod:`~adapters.inbound.declaracion.tests.test_verification_chain_m111`
        Reads them as parse-fidelity anchors and drives the arithmetic from
        its own probes instead.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from ._generate_base import _SEDE_ORIGIN

_COLUMN_A_BOX_X = 264.0
"""Column A box-number x0, inside the profile's 250-290 anchor band."""

_COLUMN_A_VALUE_X = 327.0
"""Column A value x0. Must stay below the profile's ``value_x_max`` of 345."""

_COLUMN_B_BOX_X = 347.0
"""Column B box-number x0.

Above column A's ``value_x_max`` of 345 BY DESIGN: this is what stops a blank
column-A cell from reading column B's box number as its amount. The two-point
margin is the whole guard, so neither number moves without the other.
"""

_COLUMN_B_VALUE_X = 419.0
"""Column B value x0. Must stay below the profile's ``value_x_max`` of 459."""

_COLUMN_C_BOX_X = 461.0
"""Column C box-number x0, above column B's ``value_x_max`` of 459."""

_COLUMN_C_VALUE_X = 539.0
"""Column C value x0. Column C declares no upper bound; the 150-point
right-of-anchor gap tolerance is what bounds it."""

_BOX_NUMBER_SIZE = 7.5
_VALUE_SIZE = 9.0
_LABEL_SIZE = 7.0
_ROW_STEP = 6.5 * mm


@dataclass(frozen=True)
class _Modelo111Row:
    """One printed epigrafe row: a label and up to three column cells.

    Each cell is ``(box_number, printed_value_or_None)``. A ``None`` value
    prints the box number alone, which is how AEAT renders a box the filer left
    empty and what the absent-target expectations rest on.
    """

    label: str
    column_a: tuple[str, str | None]
    column_b: tuple[str, str | None]
    column_c: tuple[str, str | None]


@dataclass(frozen=True)
class _Modelo111Fixture:
    filename: str
    ejercicio: str
    periodo: str
    tax_id: str
    full_name: str
    perceptores: str | None
    base: str | None
    retencion: str | None
    suma_retenciones: str | None
    resultado: str
    rows: tuple[_Modelo111Row, ...] = field(default=())


#: The nine epigrafe rows AEAT prints, in order, with their column box numbers.
#:
#: Read off the printed form: three columns of nine rows numbering 01-27 in
#: row-major order.
_EPIGRAFE_ROWS: tuple[tuple[str, str, str, str], ...] = (
    ("Rendimientos dinerarios ...........................................................", "01", "02", "03"),
    ("Rendimientos en especie ..........................................................", "04", "05", "06"),
    ("Rendimientos dinerarios ...........................................................", "07", "08", "09"),
    ("Rendimientos en especie ..........................................................", "10", "11", "12"),
    ("Premios en metálico .................................................................", "13", "14", "15"),
    ("Premios en especie ..................................................................", "16", "17", "18"),
    ("Percepciones dinerarias ...........................................................", "19", "20", "21"),
    ("Percepciones en especie ..........................................................", "22", "23", "24"),
    ("Ganancias patrimoniales ...........................................................", "25", "26", "27"),
)

#: Printed values per quarter. See the module docstring on why 09/28/30 repeat.
_QUARTER_VALUES: dict[str, dict[str, str | None]] = {
    "1T": {"07": "3", "08": "12.480,00", "09": "2.371,20", "28": "2.371,20", "30": "2.371,20"},
    "2T": {"07": "4", "08": "15.630,50", "09": "2.969,80", "28": "2.969,80", "30": "2.969,80"},
    "3T": {"07": "2", "08": "9.145,25", "09": "1.737,60", "28": "1.737,60", "30": "1.737,60"},
    # The fourth quarter prints casilla 30 alone. This is a real filing shape --
    # the sparsest render in the corpus -- and the consuming test pins it,
    # because a case that supplies no inputs will otherwise execute no assertion
    # and still report success.
    "4T": {"07": None, "08": None, "09": None, "28": None, "30": "4.208,15"},
}


def _rows_for(periodo: str) -> tuple[_Modelo111Row, ...]:
    values = _QUARTER_VALUES[periodo]
    rows: list[_Modelo111Row] = []
    for label, box_a, box_b, box_c in _EPIGRAFE_ROWS:
        rows.append(
            _Modelo111Row(
                label=label,
                column_a=(box_a, values.get(box_a)),
                column_b=(box_b, values.get(box_b)),
                column_c=(box_c, values.get(box_c)),
            ),
        )
    return tuple(rows)


_MODELO_111_FIXTURES: tuple[_Modelo111Fixture, ...] = tuple(
    _Modelo111Fixture(
        filename=f"111/2024-{periodo}.pdf",
        ejercicio="2024",
        periodo=periodo,
        tax_id="Y0000001S",
        full_name="APELLIDO APELLIDO NOMBRE",
        perceptores=_QUARTER_VALUES[periodo]["07"],
        base=_QUARTER_VALUES[periodo]["08"],
        retencion=_QUARTER_VALUES[periodo]["09"],
        suma_retenciones=_QUARTER_VALUES[periodo]["28"],
        resultado=str(_QUARTER_VALUES[periodo]["30"]),
        rows=_rows_for(periodo),
    )
    for periodo in ("1T", "2T", "3T", "4T")
)


def _draw_cell(c: canvas.Canvas, box_x: float, value_x: float, y: float, cell: tuple[str, str | None]) -> None:
    """Draw one column cell: its box number, and its value when the box is filled."""
    box_number, value = cell
    c.setFont("Helvetica", _BOX_NUMBER_SIZE)
    c.drawString(box_x, y, box_number)
    if value is None:
        return
    c.setFont("Helvetica", _VALUE_SIZE)
    c.drawString(value_x, y, value)


def _draw_modelo_111(c: canvas.Canvas, fixture: _Modelo111Fixture) -> None:
    """Render the two-page quarterly declaracion specimen onto ``c``."""
    _, height = A4
    csv_value = f"SANITIZED111{fixture.ejercicio}"
    justificante = "1110000000000"

    def _footer(page_number: str) -> None:
        c.setFont("Helvetica", _LABEL_SIZE)
        c.drawString(
            18 * mm,
            14 * mm,
            "La autenticidad de este documento puede ser comprobada mediante el Código Seguro",
        )
        c.drawString(18 * mm, 10 * mm, f"de Verificación {csv_value} en {_SEDE_ORIGIN} {page_number}")

    # --- page 1: informacion de la presentacion (the justificante trailer) ---
    y = height - 22 * mm
    c.setFont("Helvetica-Bold", 11)
    c.drawString(18 * mm, y, "INFORMACIÓN DE LA PRESENTACIÓN DE LA DECLARACIÓN")
    y -= 8 * mm
    c.setFont("Helvetica", _LABEL_SIZE)
    for line in (
        "MODELO 111",
        "Registro",
        "Presentación realizada el: 01-01-1900 a las 09:12:44",
        f"Expediente/Referencia (nº registro asignado): {justificante}",
        f"Código Seguro de Verificación: {csv_value}",
        f"Número de justificante: {justificante}",
        "Vía de entrada: Presentación por Internet",
        "Presentador",
        f"NIF Presentador: {fixture.tax_id}",
        f"Apellidos y Nombre / Razón social: {fixture.full_name}",
        "En calidad de: Titular",
    ):
        c.drawString(18 * mm, y, line)
        y -= 5 * mm
    _footer("1")
    c.showPage()

    # --- page 2: the three-column epigrafe table ---
    y = height - 22 * mm
    c.setFont("Helvetica", _LABEL_SIZE)
    for line in (
        "Agencia Tributaria   Teléfono: 91 554 87 70",
        "Retenciones e ingresos a cuenta del IRPF   Modelo 111",
        f"Ejercicio {fixture.ejercicio}   Período {fixture.periodo}",
        f"NIF: {fixture.tax_id}   Apellidos y nombre o razón social: {fixture.full_name}",
    ):
        c.drawString(18 * mm, y, line)
        y -= 5 * mm
    y -= 4 * mm
    c.setFont("Helvetica", _LABEL_SIZE)
    c.drawString(18 * mm, y, "Liquidación   N.º de perceptores   Importe de las percepciones   Retenciones e ingresos")
    y -= 6 * mm

    for row in fixture.rows:
        c.setFont("Helvetica", _LABEL_SIZE)
        c.drawString(18 * mm, y, row.label)
        _draw_cell(c, _COLUMN_A_BOX_X, _COLUMN_A_VALUE_X, y, row.column_a)
        _draw_cell(c, _COLUMN_B_BOX_X, _COLUMN_B_VALUE_X, y, row.column_b)
        _draw_cell(c, _COLUMN_C_BOX_X, _COLUMN_C_VALUE_X, y, row.column_c)
        y -= _ROW_STEP

    y -= 2 * mm
    c.setFont("Helvetica", _LABEL_SIZE)
    c.drawString(
        18 * mm,
        y,
        "Suma de retenciones e ingresos a cuenta ( 03 + 06 + 09 + 12 + 15 + 18 + 21 + 24 + 27 ) ....",
    )
    _draw_cell(c, _COLUMN_C_BOX_X, _COLUMN_C_VALUE_X, y, ("28", fixture.suma_retenciones))
    y -= _ROW_STEP

    c.setFont("Helvetica", _LABEL_SIZE)
    c.drawString(
        18 * mm,
        y,
        "Resultados a ingresar de anteriores autoliquidaciones por el mismo concepto, ejercicio y período ....",
    )
    # Casilla 29 is printed and left blank, as on the render this replaces: the
    # filer had no prior autoliquidacion. It is not an extraction target (it is
    # a prior-payment box, not an epigrafe), so its blankness is layout fidelity
    # rather than a pinned expectation.
    _draw_cell(c, _COLUMN_C_BOX_X, _COLUMN_C_VALUE_X, y, ("29", None))
    y -= _ROW_STEP

    c.setFont("Helvetica", _LABEL_SIZE)
    c.drawString(18 * mm, y, "Resultado a ingresar ( 28 – 29 ) ..............................................")
    _draw_cell(c, _COLUMN_C_BOX_X, _COLUMN_C_VALUE_X, y, ("30", fixture.resultado))
    y -= _ROW_STEP

    y -= 4 * mm
    c.setFont("Helvetica", _LABEL_SIZE)
    c.drawString(18 * mm, y, "Ejemplar para el obligado tributario")
    y -= 5 * mm
    c.drawString(18 * mm, y, "Fecha y hora de presentación: 2024-04-15 09:12:44")
    y -= 5 * mm
    c.drawString(18 * mm, y, "Fecha de alta de la actividad: 01-01-1900")
    _footer("2")


__all__ = [
    "_MODELO_111_FIXTURES",
    "_Modelo111Fixture",
    "_Modelo111Row",
    "_draw_modelo_111",
]
