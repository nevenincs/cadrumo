"""Generic synthetic generator for quarterly AEAT modelos (#305).

Renders a PDF whose text layer matches the line-anchored regex the
:class:`aeat.declaracion._generic_extractor.GenericDeclaracionExtractor`
reads: header (NIF / Ejercicio / Período), then each casilla on its
own line prefixed by the zero-padded ID + label + Spanish amount.

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
    labels: Mapping[str, str]
    casilla_values: Mapping[str, Decimal]
    csv: str | None = None
    presented_at: str = "2025-04-20 10:00:00"


class QuarterlyGroundTruth(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")
    params: QuarterlyGenParams
    expected_casillas: tuple[tuple[str, Decimal], ...]


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
        draw_casilla_box(c, box, params.casilla_values.get(casilla_id))

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
    return pdf_bytes, QuarterlyGroundTruth(params=params, expected_casillas=expected)


__all__ = ["QuarterlyGenParams", "QuarterlyGroundTruth", "generate"]
