"""Synthetic Modelo 100 annual-declaracion fixtures for ejercicios 2021-2023.

These three replace the real sanitised specimens that could not stay in the
repository: each carried personal data the redaction pipeline never wrote --
a checksum-valid IBAN on the 2021 render, and name-shaped strings on all three
that appear in no sanitiser manifest and nowhere in the bundled AEAT corpus.

This is NOT a general-purpose M100 renderer. Every line below reproduces a
layout fact that a committed test reads off the ``declaracion_pdf`` extraction
profile, and the value of these files is that those facts survive, not that the
amounts mean anything. The 2021, 2022 and 2023 revisions declare byte-identical
label patterns, so one row table serves all three.

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
  amount.** The profile's patterns for casilla ``0595`` and casilla ``0670``
  also match the section headings AEAT prints above them
  (``CUOTA RESULTANTE DE LA AUTOLIQUIDACION``, ``RESULTADO DE LA DECLARACION``,
  ``Calculo del impuesto y resultado de la declaracion``). Those headings carry
  no trailing amount, so they are not candidates and the target still resolves.
  A generator that printed only the amount-bearing line would stop exercising
  that, and the two targets would go on passing for the wrong reason.
- **The formula-bracket label text.** Several patterns anchor on the opening
  ``[`` that distinguishes a formula-bearing body line from a same-worded
  summary line (``0500``/``0505``, ``0224``/``0226``, ``0586``/``0671``). The
  label strings below are the ones AEAT prints, brackets and all.
- **The justificante trailer.** CSV, NIF, presentation timestamp and sede URL,
  because the sidecar roundtrip gate parses these files as justificantes and
  not only as declaraciones. No labelled periodo: the annual render prints only
  the ejercicio.

The amounts are PROBES. They assert no tax fact, they are not an AEAT figure,
and nothing derives them from a formula. They are deliberately distinct WITHIN
each specimen and ACROSS the three: the renders these replace printed one
redaction constant into every box of all three files, so a label pattern that
drifted onto a neighbouring line -- or a test that read the wrong year's
fixture -- saw the same number and nothing failed.

What these files CANNOT carry is the class of AEAT behaviour nobody has looked
for yet. A real render is evidence about a document this project did not
author; these are evidence about the facts already pinned. With all three
replaced, Modelo 100 has no externally-authored render left in the tree.

See Also:
    :mod:`~adapters.inbound.declaracion.tests.test_parser_boundary_m100`
        Consumes these fixtures through the full parser boundary.
    :mod:`~tests.fixtures.justificantes._generate_modelo_100_current`
        The 2024/2025 sibling, built from the AEAT Diseno de Registro field
        dictionaries rather than from a printed render.
"""

from __future__ import annotations

from dataclasses import dataclass

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from ....core.casilla_id import CasillaId, validated_casilla_id
from ._generate_base import _SEDE_ORIGIN


@dataclass(frozen=True)
class _Modelo100CorpusRow:
    """One printed declaracion line.

    ``box_number`` is the four-digit casilla number AEAT prints over the right
    edge of the amount. ``amount`` of ``None`` marks a section heading: it
    matches a target's label pattern but carries no value, which is the
    multi-match tolerance these fixtures exist to keep exercised.
    """

    casilla_id: CasillaId | None
    label: str
    amount: str | None
    box_number: str | None


@dataclass(frozen=True)
class _Modelo100CorpusFixture:
    filename: str
    ejercicio: str
    tax_id: str
    full_name: str
    apartado_rows: tuple[_Modelo100CorpusRow, ...]
    cuota_rows: tuple[_Modelo100CorpusRow, ...]


def _heading(label: str) -> _Modelo100CorpusRow:
    return _Modelo100CorpusRow(None, label, None, None)


# Label text as AEAT prints it on the declaracion body, shared by the 2021,
# 2022 and 2023 revisions (their extraction profiles declare byte-identical
# label patterns). The accents are the form's own; the patterns accept both
# accented and unaccented spellings, and keeping the accented form is what
# makes these specimens exercise the same branch the real renders did.
_APARTADO_LABELS: tuple[tuple[str, str], ...] = (
    ("0171", "Ingresos de explotación."),
    ("0180", "Total ingresos computables [(171)a(179)]."),
    ("0218", "Suma de gastos fiscalmente deducibles."),
    ("0223", "Total gastos deducibles, modalidad simplificada [(218)+(222)]."),
    ("0224", "Rendimiento neto [(180)-(220) ó (180)-(223)]."),
    ("0226", "Rendimiento neto reducido [(224)-(225)]."),
    ("0231", "Suma de rendimientos netos reducidos"),
    (
        "0235",
        "Suma del rendimiento neto reducido total de las actividades económicas en estimación directa",
    ),
    (
        "0432",
        "Saldo neto de rendimientos a integrar en la base imponible general y de las imputaciones de renta",
    ),
    ("0500", "Base liquidable general [(435)-(491)-(492)-(493)-(494)-(495)-(496)-(497)]"),
    ("0505", "Base liquidable general sometida a gravamen [(500)-(501)]"),
    ("0510", "Base liquidable del ahorro [(460)-(506)-(507)]"),
)

_CUOTA_LABELS: tuple[tuple[str, str], ...] = (
    ("0545", "Cuota íntegra estatal [(532)+(540)]"),
    ("0546", "Cuota íntegra autonómica [(533)+(541)]"),
    ("0585", "Cuota líquida estatal incrementada [(570)+(572)+(573)+(574)+(576)]"),
    ("0586", "Cuota líquida autonómica incrementada [(571)+(577)+(578)+(579)+(581)]"),
    ("0587", "Cuota líquida incrementada total [(585)+(586)]"),
    ("0595", "Cuota resultante de la autoliquidación [(587)-(588)-(589)-(590)-(591)]"),
    ("0604", "Pagos fraccionados ingresados por actividades económicas"),
    ("0610", "Cuota diferencial [(595)-(609)]"),
    ("0670", "Resultado de la declaración"),
)

#: Printed amount per casilla per ejercicio.
#:
#: Every value is distinct from every other value in the SAME specimen and from
#: the same casilla in the OTHER two, so a cross-line or cross-year misread
#: names itself. Nothing here is derived from a formula and nothing asserts a
#: tax fact.
M100_CORPUS_AMOUNTS: dict[str, dict[str, str]] = {
    "2021": {
        "0171": "58.412,37",
        "0180": "61.907,44",
        "0218": "12.430,55",
        "0223": "14.664,74",
        "0224": "47.242,70",
        "0226": "45.881,19",
        "0231": "44.517,88",
        "0235": "43.156,02",
        "0432": "41.803,66",
        "0500": "37.869,21",
        "0505": "36.502,88",
        "0510": "1.204,38",
        "0545": "4.827,13",
        "0546": "5.106,44",
        "0585": "4.213,07",
        "0586": "4.492,38",
        "0587": "8.705,45",
        "0595": "8.219,63",
        "0604": "3.211,90",
        "0610": "1.947,62",
        "0670": "1.658,04",
    },
    "2022": {
        "0171": "63.518,92",
        "0180": "66.204,17",
        "0218": "13.877,41",
        "0223": "16.093,26",
        "0224": "50.110,91",
        "0226": "48.762,35",
        "0231": "47.398,04",
        "0235": "46.031,79",
        "0432": "44.675,53",
        "0500": "40.744,68",
        "0505": "39.377,25",
        "0510": "2.318,47",
        "0545": "5.934,26",
        "0546": "6.213,57",
        "0585": "5.320,18",
        "0586": "5.599,49",
        "0587": "10.919,67",
        "0595": "10.433,85",
        "0604": "4.318,03",
        "0610": "3.054,75",
        "0670": "2.765,17",
    },
    "2023": {
        "0171": "71.603,48",
        "0180": "74.288,73",
        "0218": "15.961,97",
        "0223": "18.177,82",
        "0224": "56.195,47",
        "0226": "54.846,91",
        "0231": "53.482,60",
        "0235": "52.116,35",
        "0432": "50.760,09",
        "0500": "46.829,24",
        "0505": "45.461,81",
        "0510": "3.402,53",
        "0545": "7.018,82",
        "0546": "7.298,13",
        "0585": "6.404,74",
        "0586": "6.684,05",
        "0587": "13.088,79",
        "0595": "12.602,97",
        "0604": "5.402,59",
        "0610": "4.139,31",
        "0670": "3.849,73",
    },
}


def _rows(labels: tuple[tuple[str, str], ...], ejercicio: str) -> tuple[_Modelo100CorpusRow, ...]:
    amounts = M100_CORPUS_AMOUNTS[ejercicio]
    return tuple(
        _Modelo100CorpusRow(
            validated_casilla_id(casilla, surface="modelo_100_corpus_fixture casilla id"),
            label,
            amounts[casilla],
            casilla,
        )
        for casilla, label in labels
    )


def _apartado_rows(ejercicio: str) -> tuple[_Modelo100CorpusRow, ...]:
    return (
        *_rows(_APARTADO_LABELS, ejercicio),
        # Matches the 0670 label pattern and carries no amount, exactly as printed.
        _heading("Cálculo del impuesto y resultado de la declaración"),
    )


def _cuota_rows(ejercicio: str) -> tuple[_Modelo100CorpusRow, ...]:
    rows = _rows(_CUOTA_LABELS, ejercicio)
    by_casilla = {str(row.casilla_id): row for row in rows}
    return (
        by_casilla["0545"],
        by_casilla["0546"],
        by_casilla["0585"],
        by_casilla["0586"],
        by_casilla["0587"],
        # The section heading AEAT prints above the 0595 body line: it matches
        # the same label pattern and carries no amount.
        _heading("CUOTA RESULTANTE DE LA AUTOLIQUIDACIÓN"),
        by_casilla["0595"],
        by_casilla["0604"],
        by_casilla["0610"],
        _heading("RESULTADO DE LA DECLARACIÓN"),
        by_casilla["0670"],
    )


_MODELO_100_CORPUS_FIXTURES: tuple[_Modelo100CorpusFixture, ...] = tuple(
    _Modelo100CorpusFixture(
        filename=f"100/{ejercicio}-0A.pdf",
        ejercicio=ejercicio,
        tax_id="Y0000001S",
        full_name="APELLIDO APELLIDO NOMBRE",
        apartado_rows=_apartado_rows(ejercicio),
        cuota_rows=_cuota_rows(ejercicio),
    )
    for ejercicio in ("2021", "2022", "2023")
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


def _draw_row(c: canvas.Canvas, row: _Modelo100CorpusRow, y: float) -> None:
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


def _draw_modelo_100_corpus(c: canvas.Canvas, fixture: _Modelo100CorpusFixture) -> None:
    """Render the four-page annual declaracion specimen onto ``c``."""
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
    c.drawString(18 * mm, y, f"Fecha y hora de presentación: {int(fixture.ejercicio) + 1}-06-15 10:00:00")
    y -= 5 * mm
    c.drawString(18 * mm, y, "Fecha de alta de la actividad: 01-01-1900")
    _footer()


__all__ = [
    "M100_CORPUS_AMOUNTS",
    "_MODELO_100_CORPUS_FIXTURES",
    "_Modelo100CorpusFixture",
    "_Modelo100CorpusRow",
    "_draw_modelo_100_corpus",
]
