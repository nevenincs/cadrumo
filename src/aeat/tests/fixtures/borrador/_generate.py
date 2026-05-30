"""Synthetic M100 borrador corpus fixture generator.

Renders minimal Renta Web Open borrador artefacts for the M100 verification
chain test.  Each fixture contains formula-consistent casilla values derived
from the registry engine:

    leaf input  0505 (base liquidable general sometida a gravamen)
    computed    0545 (cuota integra estatal) = lookup_bracket(0505, escala-estatal)
    computed    0546 (cuota integra autonomica) = lookup_bracket_by_ccaa(0505, escalas)
    computed    0585 (cuota liquida estatal incrementada) = 0570 + deducciones-estatales
    computed    0586 (cuota liquida autonomica incrementada) = 0571 + deducciones-autonomicas

For Cataluña with zero deductions (simplest verifiable case), the cuota-liquida
casillas equal the cuota-integra casillas, i.e., 0585 = 0545, 0586 = 0546.

Legal grounding:
    Ley 35/2006 art.50 (base liquidable general)
    Ley 35/2006 art.62-63 (cuota escala estatal)
    Ley 35/2006 art.66-67 (cuota escala autonomica)
    Ley 35/2006 art.68    (cuota liquida = cuota integra - deducciones)

Corpus values are anchored to the registry's committed bracket tables
(src/aeat/_data/registry/aeat/modelos/100/revisions/<year>/formulas/).
A formula regression in the registry WILL cause the verification chain test
to fail, which is the intended safety gate.

Usage (regenerate committed PDFs):
    uv run --no-sync python src/aeat/tests/fixtures/borrador/_generate.py
"""

from __future__ import annotations

import io
from decimal import Decimal
from pathlib import Path

from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

_FIXTURES_DIR = Path(__file__).parent

# ---------------------------------------------------------------------------
# Engine-derived corpus values (Cataluna CCAA, simplificada, zero deductions)
# Values anchored to registry bracket tables.  See module docstring.
# Derived by running calculate_registry_snapshot with inputs={'0505': '30000.00'}
# for each year with binding renta-{year}-profile-tax-residence-ccaa='cataluna'.
# ---------------------------------------------------------------------------

_CORPUS_VALUES: dict[int, dict[str, Decimal]] = {
    2021: {
        "0505": Decimal("30000.00"),
        "0545": Decimal("3582.75"),
        "0546": Decimal("3845.85"),
        "0585": Decimal("3582.75"),
        "0586": Decimal("3845.85"),
    },
    2022: {
        "0505": Decimal("30000.00"),
        "0545": Decimal("3582.75"),
        "0546": Decimal("3749.10"),
        "0585": Decimal("3582.75"),
        "0586": Decimal("3749.10"),
    },
    2023: {
        "0505": Decimal("30000.00"),
        "0545": Decimal("3582.75"),
        "0546": Decimal("3749.10"),
        "0585": Decimal("3582.75"),
        "0586": Decimal("3749.10"),
    },
}

# Casilla labels: used for readability in the PDF but not matched by parser.
_CASILLA_LABELS: dict[str, str] = {
    "0505": "Base liquidable general sometida a gravamen",
    "0545": "Cuota integra estatal",
    "0546": "Cuota integra autonomica",
    "0585": "Cuota liquida estatal incrementada",
    "0586": "Cuota liquida autonomica incrementada",
}

_PRINT_ORDER: tuple[str, ...] = ("0505", "0545", "0546", "0585", "0586")


def _format_spanish_decimal(value: Decimal) -> str:
    """Format a Decimal as a Spanish-locale amount string.

    ``1234.56`` → ``1.234,56``
    ``30000.00`` → ``30.000,00``
    """
    whole, fractional = f"{value:.2f}".split(".")
    groups: list[str] = []
    while whole:
        groups.append(whole[-3:])
        whole = whole[:-3]
    return f"{'.'.join(reversed(groups))},{fractional}"


def _render_borrador_pdf(year: int, casilla_values: dict[str, Decimal]) -> bytes:
    """Render a minimal borrador-format PDF for the given year and casilla values.

    Layout follows the AEAT Renta Web Open borrador text stream:
      - Header: ``AGENCIA TRIBUTARIA``, modelo, ejercicio, NIF, ``BORRADOR`` marker.
      - One row per casilla: ``NNNN <label> <amount>`` on its own line.

    The ``_CASILLA_VALUE_RE`` borrador-parser regex expects::
        (?m)^\\s*(?P<casilla_id>[0-9]{4})\\s[^\\n]{0,160}?SPANISH_AMOUNT

    Each rendered row satisfies this pattern exactly.
    """
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(210 * mm, 297 * mm), invariant=True)
    c.setTitle(f"Modelo 100 Borrador Ejercicio {year}")

    height = 297 * mm
    margin = 15 * mm
    y = height - margin

    c.setFont("Helvetica-Bold", 11)
    c.drawString(margin, y, "AGENCIA TRIBUTARIA")
    y -= 6 * mm

    c.setFont("Helvetica", 10)
    c.drawString(margin, y, "Impuesto sobre la Renta de las Personas Fisicas  Modelo 100")
    y -= 5 * mm

    c.drawString(margin, y, f"Ejercicio: {year}")
    c.drawRightString(210 * mm - margin, y, f"Ejercicio: {year}")
    y -= 5 * mm

    c.drawString(margin, y, "NIF: 12345678T")
    y -= 5 * mm

    c.setFont("Helvetica-Bold", 11)
    c.drawString(margin, y, "BORRADOR")
    y -= 7 * mm

    c.setFont("Helvetica", 9)
    for casilla_id in _PRINT_ORDER:
        value = casilla_values.get(casilla_id)
        if value is None:
            continue
        label = _CASILLA_LABELS.get(casilla_id, "")
        amount_str = _format_spanish_decimal(value)
        # Render: ``NNNN Label  amount`` — matches borrador regex
        line = f"{casilla_id} {label}  {amount_str}"
        c.drawString(margin, y, line)
        y -= 5 * mm

    c.showPage()
    c.save()
    return buf.getvalue()


def generate_corpus() -> None:
    """Render and write the three M100 borrador corpus PDFs to fixtures/borrador/."""
    _FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    for year, casilla_values in _CORPUS_VALUES.items():
        pdf_bytes = _render_borrador_pdf(year, casilla_values)
        out_path = _FIXTURES_DIR / f"modelo_100_{year}.pdf"
        out_path.write_bytes(pdf_bytes)
        print(f"Written {out_path} ({len(pdf_bytes)} bytes)")


if __name__ == "__main__":
    generate_corpus()
