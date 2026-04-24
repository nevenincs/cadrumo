"""Synthetic Modelo 303 declaración PDF generator (EPIC #305 cluster D phase 2).

Mirrors AEAT's Modelo 303 layout across three apartados + resultado:

- Apartado 1 (régimen ordinario): casillas 01-09.
- Apartado 2 (operaciones asimiladas + IVA soportado): 28-43.
- Apartado 3 (resultado + compensaciones): 44, 45, 64-71.

Every casilla ID the runtime schema enumerates (33 total) gets a line
in the synthetic PDF; the extractor's line-anchored regex matches each
by ID + label + value.
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

# Modelo 303 has 33 casillas in the runtime schema; positions pack them
# across two "pages" of the synthetic PDF in declaration order. We keep
# them on page 1 for MVP — the extractor's ``_derive_status`` + line
# regex don't depend on page layout, only on line text.
_LABELS: Mapping[str, str] = {
    "01": "Base imponible tipo general",
    "02": "Tipo impositivo general (%)",
    "03": "Cuota repercutida tipo general",
    "04": "Base imponible tipo reducido",
    "05": "Tipo impositivo reducido (%)",
    "06": "Cuota repercutida tipo reducido",
    "07": "Base imponible tipo superreducido",
    "08": "Tipo impositivo superreducido (%)",
    "09": "Cuota repercutida tipo superreducido",
    "28": "Autoconsumo de bienes y servicios — base",
    "29": "Autoconsumo de bienes y servicios — cuota",
    "30": "Adquisiciones intracomunitarias — base",
    "31": "Adquisiciones intracomunitarias — cuota",
    "32": "Otros supuestos — base",
    "33": "Otros supuestos — cuota",
    "34": "IVA soportado operaciones interiores — base",
    "35": "IVA soportado operaciones interiores — cuota",
    "36": "IVA soportado importaciones — base",
    "37": "IVA soportado importaciones — cuota",
    "38": "IVA soportado intracomunitarias — base",
    "39": "IVA soportado intracomunitarias — cuota",
    "40": "IVA soportado bienes inversion — base",
    "41": "IVA soportado bienes inversion — cuota",
    "42": "Compensaciones régimen especial agrícola",
    "43": "Regularización de bienes de inversión",
    "44": "Suma IVA soportado deducible",
    "45": "Resultado régimen general (cuotas devengadas - cuotas deducibles)",
    "64": "Resultado de la liquidación antes de compensaciones",
    "65": "Compensaciones de períodos anteriores aplicadas",
    "66": "Resultado tras compensaciones",
    "67": "Entregas intracomunitarias y exportaciones",
    "69": "Resultado final antes del ingreso",
    "71": "Resultado a ingresar / a devolver",
}

_IDS_IN_ORDER: tuple[str, ...] = tuple(_LABELS.keys())

# Stack each casilla on a single line, 4.5mm apart, starting at y=50mm.
_ROW_HEIGHT_MM = 4.5
_START_Y_MM = 50.0
_BOXES: tuple[CasillaBox, ...] = tuple(
    CasillaBox(
        casilla_id=casilla_id,
        label_es=_LABELS[casilla_id],
        x_mm=15.0,
        y_mm=_START_Y_MM + i * _ROW_HEIGHT_MM,
    )
    for i, casilla_id in enumerate(_IDS_IN_ORDER)
)


class Modelo303GenParams(BaseModel):
    """Inputs to :func:`generate`."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    año: int = Field(ge=2000, le=2099)
    template_revision: str = Field(min_length=1, max_length=32)
    tax_id: str = Field(min_length=4, max_length=32)
    ejercicio: str = Field(min_length=4, max_length=4)
    period_printed: str = Field(min_length=1, max_length=4)
    casilla_values: Mapping[str, Decimal]
    csv: str | None = None
    presented_at: str = "2025-04-20 10:00:00"


class Modelo303GroundTruth(BaseModel):
    """Ground truth paired with the generated PDF."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    params: Modelo303GenParams
    expected_casillas: tuple[tuple[str, Decimal], ...]


def generate(params: Modelo303GenParams) -> tuple[bytes, Modelo303GroundTruth]:
    """Render a synthetic Modelo 303 declaración as PDF bytes."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=(210 * mm, 297 * mm))
    c.setTitle(f"Modelo 303 {params.ejercicio} {params.period_printed}")

    draw_header(
        c,
        modelo="303",
        ejercicio=params.ejercicio,
        periodo=params.period_printed,
        page_num=1,
        page_count=1,
    )
    for box in _BOXES:
        value = params.casilla_values.get(box.casilla_id)
        draw_casilla_box(c, box, value)

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
        (box.casilla_id, params.casilla_values[box.casilla_id])
        for box in _BOXES
        if box.casilla_id in params.casilla_values
    )
    ground_truth = Modelo303GroundTruth(params=params, expected_casillas=expected)
    return pdf_bytes, ground_truth


__all__ = [
    "Modelo303GenParams",
    "Modelo303GroundTruth",
    "generate",
]
