"""Synthetic Modelo 390 annual-summary fixture rendered in ENGLISH.

This replaces the most load-bearing anchor in the tree, and the reason it was
load-bearing is worth stating before anything else. AEAT serves the same receipt
template in Spanish or English depending on the sede UI language the filer used.
Before an English render was bundled, the parser refused one outright with
``tax_id_unresolved``, because both of its tax-id patterns hardcoded the Spanish
``NIF Presentador`` literal, and its template detector looked only for
``Modelo``/``Ejercicio``. Two independent single-render assumptions on one
document, neither visible until a real English receipt arrived.

The render it replaces carried name-shaped strings the redaction pipeline never
wrote. So this file has to carry the same evidence deliberately, where the real
one carried it by being real. Three properties are the whole point:

1. **It renders in English.** The consuming test asserts the literal markers
   ``Tax identification number``, ``Surname(s)`` and
   ``INFORMATION ON FILING THE TAX RETURN`` are present, precisely so the
   bilingual coverage cannot quietly become vacuous if the fixture is
   regenerated in Spanish.
2. **The tax id is printed ABOVE its label, not after it.** AEAT's column-split
   layout means pdfplumber's left-right traversal emits the VALUE line before
   the LABEL line. An extractor that only ever looked to the right of a label
   reads nothing here.
3. **A NIF-shaped decoy precedes the real one.** The expediente/reference number
   ends in eight digits and a letter, and is printed on the same page above its
   own label, in exactly the position an unanchored value pattern would grab.
   Reproducing it is what keeps the anchoring honest rather than incidental.

Also reproduced:

- **The English header stamp** (``FORM 390`` / ``Financial year 2021``), which
  is what lets the receipt be identified without a modelo or year override.
  A Spanish-only detector fails before tax-id extraction is ever reached.
- **A form page that opens mid-section.** Page 3 opens on
  "5. Transactions made under the general system (continued)" with no preceding
  start, so the four rate rows and box 47 sit on a page this document does not
  contain. Their absence is a fact about which pages AEAT emitted, not a parser
  defect, and it is pinned as such.
- **Box 662 printed and BLANK.** Its line ends on its own printed box number,
  which is exactly what a ``named_label`` amount capture would otherwise read as
  a value. This is the only render in the tree that exercises that guard end to
  end: without it the profile would report 662 euros of cuotas pendientes de
  compensacion the filing never declared.
- **The kerned formula label.** ``Result of the general system ( 4 7 - 64 )`` --
  AEAT splits the ``47`` across two glyph runs, which is why the profile pattern
  is written ``\\(\\s*4\\s*7\\s*-\\s*64\\s*\\)`` rather than matching ``(47``.
  Printing it unkerned would leave that tolerance untested.
- **No labelled periodo.** M390 receipts print none in either render, which the
  sidecar roundtrip gate records as an expected quirk of this modelo.

The amounts are PROBES. They assert no tax fact and no AEAT figure, and they are
pairwise distinct so a target that read a neighbouring box names itself.

What this file CANNOT carry is the class of AEAT behaviour nobody has looked for
yet -- and here that loss is sharpest, because this fixture is the standing
proof that such behaviour exists. Every property above is preserved because
somebody had already written it down. Whatever else the real receipt contained
is gone.

See Also:
    :mod:`~adapters.inbound.declaracion.tests.test_parser_bilingual_presentador_nif`
        The bilingual regression gate this fixture anchors.
"""

from __future__ import annotations

from dataclasses import dataclass

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from ._generate_base import _SEDE_ORIGIN

_BOX_ANCHOR_X = 412.0
"""Box-number x0 for the ``bbox_anchored`` targets.

The registry profile constrains those anchors to x0 407-425. Box 49 is the only
one this render prints; boxes 02/04/06/26 belong to the page it omits, so they
must NOT appear anywhere in this band or their targets would resolve and the
pinned absent-set would break.
"""

_BOX_VALUE_X = 470.0
"""Value x0 for a ``bbox_anchored`` cell, within the 150-point right-of-anchor
gap tolerance."""

_LABEL_SIZE = 7.0
_VALUE_SIZE = 8.0


@dataclass(frozen=True)
class _Modelo390EnglishFixture:
    filename: str
    ejercicio: str
    tax_id: str
    full_name: str
    expediente: str
    base_interiores: str
    cuota_interiores: str
    total_deductions: str
    result_general_system: str
    to_offset: str


_MODELO_390_ENGLISH_FIXTURES: tuple[_Modelo390EnglishFixture, ...] = (
    _Modelo390EnglishFixture(
        filename="390/2021-0A.pdf",
        ejercicio="2021",
        tax_id="Y0000001S",
        full_name="APELLIDO APELLIDO NOMBRE",
        # NIF-SHAPED DECOY, deliberately control-letter invalid. Its trailing
        # eight digits and letter are the shape an unanchored tax-id pattern
        # would mistake for the filer's identity, which is the trap the parser's
        # label anchoring exists to survive; the invalid control letter means
        # the string cannot be a real identity under any reading.
        expediente="202139000012345R",
        base_interiores="5.735,00",
        cuota_interiores="1.204,55",
        total_deductions="3.117,40",
        result_general_system="1.882,90",
        to_offset="742,35",
    ),
)


def _draw_modelo_390_english(c: canvas.Canvas, fixture: _Modelo390EnglishFixture) -> None:
    """Render the five-page English annual-summary receipt onto ``c``."""
    _, height = A4
    csv_value = f"SANITIZED390{fixture.ejercicio}"

    def _footer(page_number: str) -> None:
        c.setFont("Helvetica", _LABEL_SIZE)
        c.drawString(
            18 * mm,
            14 * mm,
            f"The authenticity of this document can be verified using the Secure Verification {page_number}",
        )
        c.drawString(18 * mm, 10 * mm, f"Code {csv_value} in {_SEDE_ORIGIN}")

    def _lines(y: float, lines: tuple[str, ...]) -> float:
        c.setFont("Helvetica", _LABEL_SIZE)
        for line in lines:
            c.drawString(18 * mm, y, line)
            y -= 5 * mm
        return y

    # --- page 1: information on filing, value-above-label throughout ---
    y = height - 22 * mm
    c.setFont("Helvetica-Bold", 11)
    c.drawString(18 * mm, y, "INFORMATION ON FILING THE TAX RETURN")
    y -= 8 * mm
    y = _lines(
        y,
        (
            "FORM 390",
            "Register",
            "Filed on 01-01-1900 at 20:46:29",
            # The decoy and the identity are both printed ABOVE their labels,
            # in this order, exactly as AEAT's column-split layout emits them.
            fixture.expediente,
            "File/Reference (assigned registration no.):",
            f"Secure Verification Code: {csv_value}",
            "Filer",
            fixture.tax_id,
            "Tax identification number(NIF)of filer:",
            fixture.full_name,
            "Surname(s) and first name/Company name:",
            "In the capacity of: Owner",
            "Way in: Filing via Internet",
            "3900000000000",
            "RECEIPT NUMBER:",
        ),
    )
    _footer("1")
    c.showPage()

    # --- page 2: taxpayer identification, English header stamp ---
    y = height - 22 * mm
    y = _lines(
        y,
        (
            "Form 390 for filing Annual Value Added Tax return   Pg. 1",
            "Tax Agency   Value Added Tax   Form 390",
            f"Financial year {fixture.ejercicio}   Annual summary return",
            f"{_SEDE_ORIGIN}",
            "1.Taxpayer   2.Liability",
            "Tax code",
            f"{fixture.tax_id}   Receipt number: 3900000000000",
            "Surname(s) and First Name or Company Name",
            fixture.full_name,
            "Have you been declared bankrupt this year? YES NO X",
            "3.Statistical data",
            "A Activities to which the declaration refers   B Key   C IAE heading",
            "4.Details of the representative",
            "Tax code   Surname(s) and First Name or Company Name",
        ),
    )
    _footer("2")
    c.showPage()

    # --- page 3: opens MID-SECTION, so the rate rows and box 47 are absent ---
    y = height - 22 * mm
    y = _lines(
        y,
        (
            "Tax code   Surname(s) and First Name or Company Name   Pg. 3",
            f"{fixture.tax_id}   {fixture.full_name}",
            "5. Transactions made under the general system (continued)",
            "Deductible VAT",
            "Taxable base   Rate %   Deductible amount",
            "Deductible VAT from internal transactions of current goods and services",
        ),
    )
    # Box 48 (base) and box 49 (cuota) share a row. Only 49 is a profile target;
    # 48 is printed alongside it because the form prints both, and because its
    # presence is what makes 49's anchor band do real work.
    c.setFont("Helvetica", _LABEL_SIZE)
    c.drawString(18 * mm, y, "Total taxable bases and deductible amounts from internal transactions ....")
    c.setFont("Helvetica", _VALUE_SIZE)
    c.drawString(222.0, y, "48")
    c.drawString(258.0, y, fixture.base_interiores)
    c.drawString(_BOX_ANCHOR_X, y, "49")
    c.drawString(_BOX_VALUE_X, y, fixture.cuota_interiores)
    y -= 6 * mm
    _footer("3")
    c.showPage()

    # --- page 4: the deduction totals and the kerned formula label ---
    y = height - 22 * mm
    y = _lines(
        y,
        (
            "Tax code   Surname(s) and First Name or Company Name   Pg. 4",
            f"{fixture.tax_id}   {fixture.full_name}",
            "5. Transactions made under the general system (continued)",
        ),
    )
    c.setFont("Helvetica", _LABEL_SIZE)
    c.drawString(
        18 * mm,
        y,
        "Total deductions (49 + 513 + 51 + 521 + 53 + 55 + 57 + 59 + 598 + 61 + 661 + 62 + 652 + 63 + 522) ....",
    )
    c.setFont("Helvetica", _VALUE_SIZE)
    c.drawString(411.0, y, "64")
    c.drawString(_BOX_VALUE_X, y, fixture.total_deductions)
    y -= 8 * mm
    # AEAT splits the "47" of this formula across two glyph runs; the profile
    # pattern tolerates the gap, and printing it unkerned would leave that
    # tolerance untested.
    c.setFont("Helvetica", _LABEL_SIZE)
    c.drawString(18 * mm, y, "Result of the general system ( 4 7 - 64 ) ..........................................")
    c.setFont("Helvetica", _VALUE_SIZE)
    c.drawString(410.0, y, "65")
    c.drawString(_BOX_VALUE_X, y, fixture.result_general_system)
    y -= 8 * mm
    _footer("4")
    c.showPage()

    # --- page 5: the settlement result, including the printed-but-BLANK box 662 ---
    y = height - 22 * mm
    y = _lines(
        y,
        (
            "9. Result of the settlements",
            "9.1 Periods that are not taxed under the group of entities special system",
            "If the result of the self-assessment of the last period is to offset or refund, enter the amount:",
        ),
    )
    c.setFont("Helvetica", _LABEL_SIZE)
    c.drawString(18 * mm, y, "{To offset .............................................")
    c.setFont("Helvetica", _VALUE_SIZE)
    c.drawString(428.0, y, "97")
    c.drawString(_BOX_VALUE_X, y, fixture.to_offset)
    y -= 8 * mm
    c.setFont("Helvetica", _LABEL_SIZE)
    c.drawString(18 * mm, y, "To refund ............................................ 98")
    y -= 8 * mm
    # Printed and BLANK: the line's last token is the box's own number, which is
    # what the blank-box guard must refuse to read as an amount.
    c.setFont("Helvetica", _LABEL_SIZE)
    c.drawString(
        18 * mm,
        y,
        "Amounts pending offset arising in the year and other than those included in box 97 ................ 662",
    )
    y -= 8 * mm
    y = _lines(
        y,
        (
            "10. Volume of transactions",
            "Transactions under the general system ................................................ 99",
        ),
    )
    _footer("5")


__all__ = [
    "_MODELO_390_ENGLISH_FIXTURES",
    "_Modelo390EnglishFixture",
    "_draw_modelo_390_english",
]
