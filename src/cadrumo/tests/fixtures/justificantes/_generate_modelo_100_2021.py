"""Synthetic Modelo 100 ejercicio-2021 declaracion fixture.

This generator exists to replace a real sanitised 2021 specimen that could not
stay in the repository. It is NOT a general-purpose M100 renderer: every line
below reproduces a layout fact that a committed test reads off the 2021
``declaracion_pdf`` extraction profile, and the value of the file is that those
facts survive, not that the amounts mean anything.

The layout facts reproduced, and why each one is here:

- **The printed box number overlaps the amount.** AEAT prints a casilla's box
  number in a smaller font whose x-range sits inside the amount's own, so
  ``extract_text`` interleaves the two into a single unreadable token
  (``1.001.0000,50405``) while ``extract_words`` carrying font size keeps them
  apart. This is the quirk that made every Modelo 100 target extract a value
  that was neither the printed amount nor a parse failure, and it is the one
  the ``named_label`` word-based amount capture exists to survive. The rows
  below draw the box number as a second, smaller text object positioned inside
  the amount's span, which reproduces the interleaving exactly.
- **A label that matches more than one line, only one of which carries an
  amount.** The 2021 profile's patterns for casilla ``0595`` and casilla
  ``0670`` also match the section headings AEAT prints above them
  (``CUOTA RESULTANTE DE LA AUTOLIQUIDACION``, ``RESULTADO DE LA DECLARACION``,
  ``Calculo del impuesto y resultado de la declaracion``). Those headings carry
  no trailing amount, so they are not candidates and the target still resolves.
  A generator that printed only the amount-bearing line would stop exercising
  that, and the two targets would go on passing for the wrong reason.
- **The formula-bracket label text.** Several 2021 patterns anchor on the
  opening ``[`` that distinguishes a formula-bearing body line from a
  same-worded summary line (``0500``/``0505``, ``0224``/``0226``,
  ``0586``/``0671``). The label strings below are the ones AEAT prints,
  brackets and all.
- **The justificante trailer.** CSV, NIF, presentation timestamp and sede URL,
  because the sidecar roundtrip gate parses this file as a justificante and not
  only as a declaracion.

The amounts are PROBES. They assert no tax fact, they are not an AEAT figure,
and no test compares them against anything. They are deliberately all DISTINCT:
the specimen this replaces printed one constant into every box, so a label
pattern that drifted onto a neighbouring line read the same number and nothing
failed. Twenty-one distinct amounts make that drift visible.

What this file CANNOT carry is the class of AEAT behaviour nobody has looked
for yet. A real render is evidence about a document this project did not
author; this one is evidence about the facts already pinned. Modelo 100 keeps
two real specimens (2022-0A, 2023-0A) and they remain the anchor.

See Also:
    :mod:`~adapters.inbound.declaracion.tests.test_parser_boundary_m100`
        Consumes this fixture through the full parser boundary.
    :mod:`~tests.fixtures.justificantes._generate_modelo_100_current`
        The 2024/2025 sibling, built from the AEAT Diseno de Registro field
        dictionaries rather than from a printed render.
"""

from __future__ import annotations

from dataclasses import dataclass

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from ....domain.calculations.registry import CasillaId, validated_casilla_id
from ._generate_base import _SEDE_ORIGIN


def _casilla_id(value: object) -> CasillaId:
    try:
        return validated_casilla_id(value, surface="modelo_100_2021_fixture casilla id")
    except ValueError as exc:  # pragma: no cover - authoring guard
        raise AssertionError(f"M100 2021 fixture casilla key {value!r} is not canonical") from exc


@dataclass(frozen=True)
class _Modelo1002021Row:
    """One printed declaracion line.

    ``box_number`` is the four-digit casilla number AEAT prints over the right
    edge of the amount. ``amount`` of ``None`` marks a section heading: it
    matches a target's label pattern but carries no value, which is the
    multi-match tolerance this fixture exists to keep exercised.
    """

    casilla_id: CasillaId | None
    label: str
    amount: str | None
    box_number: str | None


@dataclass(frozen=True)
class _Modelo1002021Fixture:
    filename: str
    ejercicio: str
    tax_id: str
    full_name: str
    apartado_rows: tuple[_Modelo1002021Row, ...]
    cuota_rows: tuple[_Modelo1002021Row, ...]


def _row(casilla: str, label: str, amount: str) -> _Modelo1002021Row:
    return _Modelo1002021Row(_casilla_id(casilla), label, amount, casilla)


def _heading(label: str) -> _Modelo1002021Row:
    return _Modelo1002021Row(None, label, None, None)


# Label text as AEAT prints it on the ejercicio-2021 declaracion body. The
# accents are the form's own; the 2021 profile patterns accept both accented
# and unaccented spellings, and keeping the accented form is what makes this
# specimen exercise the same branch the real renders did.
_M100_2021_APARTADO_ROWS: tuple[_Modelo1002021Row, ...] = (
    _row("0171", "Ingresos de explotación.", "58.412,37"),
    _row("0180", "Total ingresos computables [(171)a(179)].", "61.907,44"),
    _row("0218", "Suma de gastos fiscalmente deducibles.", "12.430,55"),
    _row("0223", "Total gastos deducibles, modalidad simplificada [(218)+(222)].", "14.664,74"),
    _row("0224", "Rendimiento neto [(180)-(220) ó (180)-(223)].", "47.242,70"),
    _row("0226", "Rendimiento neto reducido [(224)-(225)].", "45.881,19"),
    _row("0231", "Suma de rendimientos netos reducidos", "44.517,88"),
    _row(
        "0235",
        "Suma del rendimiento neto reducido total de las actividades económicas en estimación directa",
        "43.156,02",
    ),
    _row(
        "0432",
        "Saldo neto de rendimientos a integrar en la base imponible general y de las imputaciones de renta",
        "41.803,66",
    ),
    _row(
        "0500",
        "Base liquidable general [(435)-(491)-(492)-(493)-(494)-(495)-(496)-(497)]",
        "37.869,21",
    ),
    _row("0505", "Base liquidable general sometida a gravamen [(500)-(501)]", "36.502,88"),
    _row("0510", "Base liquidable del ahorro [(460)-(506)-(507)]", "1.204,38"),
    # Matches the 0670 label pattern and carries no amount, exactly as printed.
    _heading("Cálculo del impuesto y resultado de la declaración"),
)

_M100_2021_CUOTA_ROWS: tuple[_Modelo1002021Row, ...] = (
    _row("0545", "Cuota íntegra estatal [(532)+(540)]", "4.827,13"),
    _row("0546", "Cuota íntegra autonómica [(533)+(541)]", "5.106,44"),
    _row("0585", "Cuota líquida estatal incrementada [(570)+(572)+(573)+(574)+(576)]", "4.213,07"),
    _row("0586", "Cuota líquida autonómica incrementada [(571)+(577)+(578)+(579)+(581)]", "4.492,38"),
    _row("0587", "Cuota líquida incrementada total [(585)+(586)]", "8.705,45"),
    # The section heading AEAT prints above the 0595 body line: it matches the
    # same label pattern and carries no amount.
    _heading("CUOTA RESULTANTE DE LA AUTOLIQUIDACIÓN"),
    _row("0595", "Cuota resultante de la autoliquidación [(587)-(588)-(589)-(590)-(591)]", "8.219,63"),
    _row("0604", "Pagos fraccionados ingresados por actividades económicas", "3.211,90"),
    _row("0610", "Cuota diferencial [(595)-(609)]", "1.947,62"),
    _heading("RESULTADO DE LA DECLARACIÓN"),
    _row("0670", "Resultado de la declaración", "1.658,04"),
)

_MODELO_100_2021_FIXTURES: tuple[_Modelo1002021Fixture, ...] = (
    _Modelo1002021Fixture(
        filename="100/2021-0A.pdf",
        ejercicio="2021",
        tax_id="Y0000001S",
        full_name="APELLIDO APELLIDO NOMBRE",
        apartado_rows=_M100_2021_APARTADO_ROWS,
        cuota_rows=_M100_2021_CUOTA_ROWS,
    ),
)

_BODY_FONT = "Helvetica"
_BODY_SIZE = 7.0
_BOX_NUMBER_SIZE = 5.0
"""Smaller than the amount, as AEAT prints it.

Font size is the only signal that separates the box number from the amount it
overlaps, so this must stay strictly below ``_BODY_SIZE``.
"""

_AMOUNT_RIGHT_EDGE = 185 * mm
_BOX_NUMBER_INSET = 4.0 * mm
"""How far inside the amount's right edge the box number starts.

Positive, so the two spans overlap and ``extract_text`` interleaves them. A
zero or negative inset would place the box number clear of the amount and the
merged-token quirk would stop being reproduced.
"""


def _draw_row(c: canvas.Canvas, row: _Modelo1002021Row, y: float) -> None:
    c.setFont(_BODY_FONT, _BODY_SIZE)
    c.drawString(18 * mm, y, row.label)
    if row.amount is None:
        return
    amount_width = c.stringWidth(row.amount, _BODY_FONT, _BODY_SIZE)
    amount_x = _AMOUNT_RIGHT_EDGE - amount_width
    c.drawString(amount_x, y, row.amount)
    if row.box_number is not None:
        c.setFont(_BODY_FONT, _BOX_NUMBER_SIZE)
        c.drawString(_AMOUNT_RIGHT_EDGE - _BOX_NUMBER_INSET, y - 0.4, row.box_number)


def _draw_modelo_100_2021(c: canvas.Canvas, fixture: _Modelo1002021Fixture) -> None:
    """Render the four-page ejercicio-2021 declaracion specimen onto ``c``."""
    _, height = A4
    csv_value = f"SANITIZED100{fixture.ejercicio}"

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

    # --- page 1: informacion de la presentacion (the justificante trailer) ---
    y = _new_page()
    c.setFont("Helvetica-Bold", 11)
    c.drawString(18 * mm, y, "INFORMACIÓN DE LA PRESENTACIÓN DE LA DECLARACIÓN")
    y -= 8 * mm
    c.setFont(_BODY_FONT, _BODY_SIZE)
    for line in (
        "MODELO 100",
        "Registro",
        "Presentación realizada el: 01-01-1900 a las 01:15:28",
        f"Expediente/Referencia (nº registro asignado): {fixture.ejercicio}10010000000",
        f"Código Seguro de Verificación: {csv_value}",
        "Número de justificante: 1000000000000",
        "Vía de entrada: Presentación por Internet",
        "Presentador",
        f"NIF Presentador: {fixture.tax_id}",
        f"Apellidos y Nombre / Razón social: {fixture.full_name}",
        "En calidad de: Titular",
        "DOMICILIACIÓN DEL IMPORTE A INGRESAR",
        # ISO 13616-SHAPED but deliberately mod-97 INVALID. The real specimen
        # this replaces printed a checksum-valid account, and one of them was an
        # identity the redaction pipeline never wrote. A placeholder that fails
        # the checksum cannot be a real account under any reading, which is a
        # stronger guarantee than declaring it in a manifest, and it is why the
        # residual-identity scan has nothing to find here.
        "Código Cuenta Cliente (IBAN): ES0000000000000000000000",
    ):
        c.drawString(18 * mm, y, line)
        y -= 5 * mm
    _footer()
    c.showPage()

    # --- page 2: identificacion del declarante ---
    y = _new_page()
    for line in (
        "Agencia Tributaria   Impuesto sobre la Renta de las Personas Físicas   Modelo 100",
        f"Ejercicio {fixture.ejercicio}",
        f"{_SEDE_ORIGIN}   D-100",
        "Primer declarante y cónyuge, en caso de matrimonio no separado legalmente",
        "Primer declarante",
        "NIF   Apellidos y nombre",
        f"01 {fixture.tax_id}   02 {fixture.full_name}",
        f"Estado civil (el 31-12-{fixture.ejercicio})",
        "Fecha de nacimiento 01/01/1900",
        "Cónyuge (los datos identificativos del cónyuge son obligatorios en caso de matrimonio no separado legalmente)",
        "NIF   Apellidos y nombre",
        "13   14",
    ):
        c.drawString(18 * mm, y, line)
        y -= 5 * mm
    _footer()
    c.showPage()

    # --- page 3: actividades economicas y bases liquidables ---
    y = _new_page()
    c.setFont("Helvetica-Bold", 8)
    c.drawString(18 * mm, y, "Rendimientos de actividades económicas en estimación directa")
    y -= 7 * mm
    for row in fixture.apartado_rows:
        _draw_row(c, row, y)
        y -= 6 * mm
    _footer()
    c.showPage()

    # --- page 4: cuotas y resultado ---
    y = _new_page()
    c.setFont("Helvetica-Bold", 8)
    c.drawString(18 * mm, y, "Determinación de las cuotas íntegras")
    y -= 7 * mm
    for row in fixture.cuota_rows:
        _draw_row(c, row, y)
        y -= 6 * mm
    y -= 4 * mm
    c.setFont(_BODY_FONT, _BODY_SIZE)
    c.drawString(18 * mm, y, "Ejemplar para el obligado tributario")
    y -= 5 * mm
    c.drawString(18 * mm, y, "Fecha y hora de presentación: 2022-06-15 10:00:00")
    y -= 5 * mm
    c.drawString(18 * mm, y, "Fecha de alta de la actividad: 01-01-1900")
    _footer()


__all__ = [
    "_MODELO_100_2021_FIXTURES",
    "_Modelo1002021Fixture",
    "_Modelo1002021Row",
    "_draw_modelo_100_2021",
]
