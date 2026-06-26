"""Generic synthetic generator for declaration-like AEAT PDFs.

Renders a PDF with header text (NIF / Ejercicio / Período) and each
casilla on its own line prefixed by the zero-padded ID + label + Spanish
amount.

Per-modelo generator modules compose a ``QuarterlyGenParams`` instance
with their own label map and call :func:`generate`.
"""

from __future__ import annotations

import io
from collections.abc import Mapping
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from ......domain.calculations.registry import CasillaId
from ._generator_shared import (
    CasillaBox,
    draw_casilla_box,
    draw_footer,
    draw_header,
)


class QuarterlyGenParams(BaseModel):
    """Inputs to :func:`generate` for any quarterly modelo."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    modelo: str = Field(min_length=1, max_length=8)
    año: int = Field(ge=2000, le=2099)
    template_revision: str = Field(min_length=1, max_length=32)
    tax_id: str = Field(min_length=4, max_length=32)
    ejercicio: str = Field(min_length=4, max_length=4)
    period_printed: str = Field(min_length=1, max_length=4)
    labels: Mapping[CasillaId, str]
    casilla_values: Mapping[CasillaId, Decimal | str]
    csv: str | None = None
    presented_at: str = "2025-04-20 10:00:00"
    thousands_sep: str = Field(
        default=".",
        min_length=1,
        max_length=1,
        pattern=r"^[.\xa0\u202f]$",
    )
    """Thousands-group separator used by rendered amounts.

    Defaults to ``"."`` (the canonical AEAT print separator). Set to
    ``"\\xa0"`` (NBSP) or ``"\\u202f"`` (narrow NBSP) to exercise the
    label-regex NBSP path end-to-end through a real PDF
    round-trip, rather than only via synthetic text tests.

    Pattern-constrained to the valid AEAT separators per UNE 82100. A
    digit / comma / letter would ambiguate the amount regex, so those
    inputs are rejected at construction time.
    """


class QuarterlyGroundTruth(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")
    params: QuarterlyGenParams
    expected_values_by_casilla_id: tuple[tuple[CasillaId, Decimal | str], ...]


def generate(params: QuarterlyGenParams) -> tuple[bytes, QuarterlyGroundTruth]:
    """Render a quarterly declaración PDF with one line per casilla."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=(210 * mm, 297 * mm))
    c.setTitle(f"Modelo {params.modelo} {params.ejercicio} {params.period_printed}")

    draw_header(
        c,
        modelo=params.modelo,
        ejercicio=params.ejercicio,
        periodo=params.period_printed,
        page_num=1,
        page_count=1,
    )

    row_height_mm = 4.5
    start_y_mm = 50.0
    ids_in_order = tuple(params.labels.keys())
    for i, casilla_id in enumerate(ids_in_order):
        box = CasillaBox(
            casilla_id=casilla_id,
            label_es=params.labels[casilla_id],
            x_mm=15.0,
            y_mm=start_y_mm + i * row_height_mm,
        )
        draw_casilla_box(
            c,
            box,
            params.casilla_values.get(casilla_id),
            thousands_sep=params.thousands_sep,
        )

    draw_footer(
        c,
        tax_id=params.tax_id,
        presented_at=params.presented_at,
        csv=params.csv,
    )
    c.showPage()
    c.save()
    pdf_bytes = buffer.getvalue()

    expected = tuple(
        (casilla_id, params.casilla_values[casilla_id])
        for casilla_id in ids_in_order
        if casilla_id in params.casilla_values
    )
    return pdf_bytes, QuarterlyGroundTruth(params=params, expected_values_by_casilla_id=expected)


__all__ = ["QuarterlyGenParams", "QuarterlyGroundTruth", "generate"]
