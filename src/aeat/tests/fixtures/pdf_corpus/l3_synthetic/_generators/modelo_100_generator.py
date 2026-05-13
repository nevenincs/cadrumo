"""Synthetic Modelo 100 (IRPF / Renta) summary-block PDF generator.

Renders a two-page Renta artefact with the summary-block casillas
the extractor targets. The caller picks the artefact kind (BORRADOR /
PREDECLARACION / DECLARACION); the generator stamps the
matching marker (BORRADOR header / VISTA PREVIA watermark / CSV foot)
so ``detect_artefact_kind`` routes correctly.
"""

from __future__ import annotations

import io
from collections.abc import Mapping
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from ._generator_shared import (
    A4_HEIGHT,
    A4_WIDTH,
    LABEL_FONT,
    LABEL_FONT_SIZE,
    MARGIN_BOTTOM,
    MARGIN_LEFT,
    MARGIN_RIGHT,
    MARGIN_TOP,
    CasillaBox,
    draw_casilla_box,
    format_amount,
)

_SUMMARY_LABELS: Mapping[str, str] = {
    "0022": "Rendimiento neto — rendimientos del trabajo",
    "0049": "Rendimiento neto — capital mobiliario",
    "0107": "Rendimiento neto — capital inmobiliario",
    "0175": "Rendimiento neto — actividades economicas (estimacion directa)",
    "0400": "Ganancia o perdida patrimonial total",
    "0435": "Base imponible general",
    "0460": "Base imponible del ahorro",
    "0500": "Minimo personal y familiar total",
    "0505": "Minimo del contribuyente",
    "0510": "Minimo por descendientes",
    "0515": "Minimo por ascendientes",
    "0520": "Minimo por discapacidad",
    "0545": "Base liquidable general",
    "0555": "Base liquidable del ahorro",
    "0550": "Cuota integra general estatal",
    "0551": "Cuota integra general autonomica",
    "0560": "Cuota integra del ahorro estatal",
    "0561": "Cuota integra del ahorro autonomica",
    "0595": "Cuota integra total",
    "0620": "Deducciones estatales",
    "0622": "Deducciones autonomicas",
    "0630": "Total deducciones",
    "0698": "Cuota liquida total",
    "0699": "Retenciones e ingresos a cuenta",
    "0700": "Pagos fraccionados (Modelo 130 / 131)",
    "0720": "Cuota resultante de la autoliquidacion",
    "0721": "Resultado a ingresar / a devolver",
}


_ROW_HEIGHT_MM = 5.0
_START_Y_MM = 40.0
_BOXES: tuple[CasillaBox, ...] = tuple(
    CasillaBox(
        casilla_id=casilla_id,
        label_es=_SUMMARY_LABELS[casilla_id],
        x_mm=15.0,
        y_mm=_START_Y_MM + i * _ROW_HEIGHT_MM,
    )
    for i, casilla_id in enumerate(_SUMMARY_LABELS.keys())
)


class Modelo100GenParams(BaseModel):
    """Inputs to :func:`generate`."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    año: int = Field(ge=2000, le=2099)
    ejercicio: str = Field(min_length=4, max_length=4)
    tax_id: str = Field(min_length=4, max_length=32)
    casilla_values: Mapping[str, Decimal]
    artefact_kind: str = Field(pattern=r"^(BORRADOR|PREDECLARACION|DECLARACION)$")
    csv: str | None = None  # required when artefact_kind == DECLARACION


class Modelo100GroundTruth(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    params: Modelo100GenParams
    expected_casillas: tuple[tuple[str, Decimal], ...]


def _draw_header(c: canvas.Canvas, params: Modelo100GenParams) -> None:
    y = A4_HEIGHT - MARGIN_TOP
    c.setFont("Helvetica-Bold", 14)
    c.drawString(MARGIN_LEFT, y, "AGENCIA TRIBUTARIA")
    y -= 6 * mm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(MARGIN_LEFT, y, "Declaracion IRPF — Modelo 100")
    c.drawRightString(A4_WIDTH - MARGIN_RIGHT, y, f"Ejercicio: {params.ejercicio}")
    y -= 5 * mm
    c.setFont(LABEL_FONT, LABEL_FONT_SIZE)
    c.drawString(MARGIN_LEFT, y, f"NIF: {params.tax_id}")

    # Stamp the artefact kind marker.
    if params.artefact_kind == "BORRADOR":
        y -= 5 * mm
        c.setFont("Helvetica-Bold", 12)
        c.drawString(MARGIN_LEFT, y, "BORRADOR")
    elif params.artefact_kind == "PREDECLARACION":
        # Real AEAT simulaciones carry both a diagonal watermark and a
        # non-rotated banner. The banner gives pdfplumber's text stream
        # something to match; the watermark is cosmetic.
        y -= 5 * mm
        c.setFont("Helvetica-Bold", 12)
        c.drawString(MARGIN_LEFT, y, "VISTA PREVIA — Documento no valido para presentar")
        c.saveState()
        c.setFont("Helvetica-Bold", 36)
        c.setFillGray(0.8)
        c.translate(A4_WIDTH / 2, A4_HEIGHT / 2)
        c.rotate(30)
        c.drawCentredString(0, 0, "VISTA PREVIA")
        c.restoreState()


def _draw_footer(c: canvas.Canvas, params: Modelo100GenParams) -> None:
    y = MARGIN_BOTTOM
    c.setFont(LABEL_FONT, LABEL_FONT_SIZE)
    if params.artefact_kind == "DECLARACION" and params.csv is not None:
        c.drawString(MARGIN_LEFT, y, f"Codigo Seguro de Verificacion: {params.csv}")


def generate(params: Modelo100GenParams) -> tuple[bytes, Modelo100GroundTruth]:
    """Render a synthetic Modelo 100 artefact as PDF bytes."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=(210 * mm, 297 * mm))
    c.setTitle(f"Modelo 100 {params.ejercicio} {params.artefact_kind}")

    _draw_header(c, params)

    for box in _BOXES:
        value = params.casilla_values.get(box.casilla_id)
        draw_casilla_box(c, box, value)

    _draw_footer(c, params)
    c.showPage()
    c.save()
    pdf_bytes = buffer.getvalue()

    expected = tuple(
        (box.casilla_id, params.casilla_values[box.casilla_id])
        for box in _BOXES
        if box.casilla_id in params.casilla_values
    )
    ground_truth = Modelo100GroundTruth(params=params, expected_casillas=expected)
    return pdf_bytes, ground_truth


__all__ = [
    "Modelo100GenParams",
    "Modelo100GroundTruth",
    "format_amount",
    "generate",
]
