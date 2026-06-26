"""Shared rendering primitives for every synthetic modelo generator.

Mirrors AEAT's declaración layout conventions: A4 pages with Helvetica
(Arial-compatible metrics), Spanish thousands formatting (``1.234,56``),
label-prefixed casilla boxes, header + footer bands. Each per-modelo
generator composes these primitives to produce a PDF the extractors
can parse with the same primitive stack they'd use against a real AEAT
declaración.

The module is test-only — it lives under ``src/aeat/tests/fixtures/`` and is not
importable from ``src/aeat/``. Reusing reportlab keeps the dependency
surface identical to the existing ``src/aeat/tests/fixtures/justificantes/
_generate.py`` helper.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as _canvas

from ......domain.calculations.registry import CasillaId

# A4 dimensions and standard AEAT-like margins.
A4_WIDTH, A4_HEIGHT = A4
MARGIN_LEFT = 20 * mm
MARGIN_RIGHT = 20 * mm
MARGIN_TOP = 20 * mm
MARGIN_BOTTOM = 20 * mm

# AEAT's actual forms render Arial; Helvetica is metrics-compatible and
# ships with reportlab by default.
HEADER_FONT = "Helvetica-Bold"
HEADER_FONT_SIZE = 12
LABEL_FONT = "Helvetica"
LABEL_FONT_SIZE = 9
VALUE_FONT = "Helvetica"
VALUE_FONT_SIZE = 10


@dataclass(frozen=True)
class CasillaBox:
    """One casilla's rendering footprint on the page."""

    casilla_id: CasillaId  # e.g. "01"
    label_es: str  # e.g. "Ingresos íntegros"
    x_mm: float  # left edge in millimetres
    y_mm: float  # top edge in millimetres (measured from page top)
    width_mm: float = 50.0  # value-box width
    height_mm: float = 6.0  # value-box height


def format_amount(value: Decimal, *, thousands_sep: str = ".") -> str:
    """Format ``value`` as an AEAT-style Spanish amount.

    Accepts a ``thousands_sep`` opt-in parameter so the synthetic
    generator can exercise NBSP handling end-to-end. AEAT per UNE 82100
    may use ``"."`` (canonical), ``"\\xa0"``
    (U+00A0 NBSP) or ``"\\u202f"`` (U+202F narrow NBSP) between
    thousand groups. Default stays ``"."`` so existing fixtures and
    tests continue to match the committed canonical rendering.

    Negative values carry a leading minus; zero prints as ``0,00``.
    """
    if value.is_zero():
        return "0,00"
    sign = "-" if value.is_signed() else ""
    abs_value = abs(value)
    quantised = abs_value.quantize(Decimal("0.01"))
    whole, _, frac = f"{quantised:,.2f}".partition(".")
    whole_es = whole.replace(",", thousands_sep)
    return f"{sign}{whole_es},{frac}"


def draw_header(
    canvas: _canvas.Canvas,
    *,
    modelo: str,
    ejercicio: str,
    periodo: str,
    page_num: int,
    page_count: int,
) -> None:
    """Draw the AEAT-style header band at the top of the page."""
    y = A4_HEIGHT - MARGIN_TOP
    canvas.setFont(HEADER_FONT, HEADER_FONT_SIZE + 2)
    canvas.drawString(MARGIN_LEFT, y, "AGENCIA TRIBUTARIA")
    y -= 6 * mm
    canvas.setFont(HEADER_FONT, HEADER_FONT_SIZE)
    canvas.drawString(MARGIN_LEFT, y, f"Declaracion - Modelo {modelo}")
    canvas.drawRightString(A4_WIDTH - MARGIN_RIGHT, y, f"Pagina {page_num} de {page_count}")
    y -= 5 * mm
    canvas.setFont(LABEL_FONT, LABEL_FONT_SIZE)
    canvas.drawString(MARGIN_LEFT, y, f"Ejercicio: {ejercicio}   Periodo: {periodo}")


def draw_casilla_box(
    canvas: _canvas.Canvas,
    box: CasillaBox,
    value: Decimal | str | int | None,
    *,
    thousands_sep: str = ".",
) -> None:
    """Render one casilla as a single-line ``<id>  <label>    <value>`` row.

    Drawing label + value as one drawString call (rather than at two
    x coordinates) dodges pdfplumber's reading-order heuristic which
    interleaves columns unreliably on tight A4 layouts. Real AEAT
    declaración PDFs render boxed values in their own column; the
    extractor can use bbox-anchored parsing against the visual layout.

    Blank values still render the casilla label so extractors can
    distinguish ``not-present`` (no label emitted) from ``blank``
    (label emitted, no value).

    The ``thousands_sep`` option lets synthetic fixtures exercise the
    NBSP / narrow-NBSP label-regex path end-to-end, not just via
    string-level tests.
    """
    y = A4_HEIGHT - box.y_mm * mm
    canvas.setFont(VALUE_FONT, VALUE_FONT_SIZE)
    label_text = f"{box.casilla_id}  {box.label_es}"
    if value is not None and value != "":
        rendered = (
            format_amount(Decimal(value), thousands_sep=thousands_sep)
            if isinstance(value, Decimal | int)
            else str(value)
        )
        line = f"{label_text}    {rendered}"
    else:
        line = label_text
    canvas.drawString(box.x_mm * mm, y, line)


def draw_footer(
    canvas: _canvas.Canvas,
    *,
    tax_id: str,
    presented_at: str,
    csv: str | None = None,
) -> None:
    """Draw the AEAT-style footer (NIF, submission timestamp, optional CSV)."""
    y = MARGIN_BOTTOM
    canvas.setFont(LABEL_FONT, LABEL_FONT_SIZE)
    canvas.drawString(MARGIN_LEFT, y, f"NIF: {tax_id}")
    canvas.drawString(MARGIN_LEFT, y - 4 * mm, f"Fecha y hora: {presented_at}")
    if csv is not None:
        canvas.drawRightString(A4_WIDTH - MARGIN_RIGHT, y, f"CSV: {csv}")


__all__ = [
    "A4_HEIGHT",
    "A4_WIDTH",
    "HEADER_FONT",
    "HEADER_FONT_SIZE",
    "LABEL_FONT",
    "LABEL_FONT_SIZE",
    "MARGIN_BOTTOM",
    "MARGIN_LEFT",
    "MARGIN_RIGHT",
    "MARGIN_TOP",
    "VALUE_FONT",
    "VALUE_FONT_SIZE",
    "CasillaBox",
    "draw_casilla_box",
    "draw_footer",
    "draw_header",
    "format_amount",
]
