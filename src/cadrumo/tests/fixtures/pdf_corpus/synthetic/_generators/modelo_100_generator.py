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

from ......adapters.inbound.borrador import ArtefactKind
from ......core import CasillaId, validated_casilla_id
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

_SUMMARY_LABELS: Mapping[CasillaId, str] = {
    validated_casilla_id(
        "0022", surface="modelo_100_pdf_fixture._SUMMARY_LABELS"
    ): "Rendimiento neto — rendimientos del trabajo",
    validated_casilla_id(
        "0049", surface="modelo_100_pdf_fixture._SUMMARY_LABELS"
    ): "Rendimiento neto — capital mobiliario",
    validated_casilla_id(
        "0107", surface="modelo_100_pdf_fixture._SUMMARY_LABELS"
    ): "Rendimiento neto — capital inmobiliario",
    validated_casilla_id(
        "0175", surface="modelo_100_pdf_fixture._SUMMARY_LABELS"
    ): "Rendimiento neto — actividades economicas (estimacion directa)",
    validated_casilla_id(
        "0400", surface="modelo_100_pdf_fixture._SUMMARY_LABELS"
    ): "Ganancia o perdida patrimonial total",
    validated_casilla_id("0435", surface="modelo_100_pdf_fixture._SUMMARY_LABELS"): "Base imponible general",
    validated_casilla_id("0460", surface="modelo_100_pdf_fixture._SUMMARY_LABELS"): "Base imponible del ahorro",
    validated_casilla_id("0500", surface="modelo_100_pdf_fixture._SUMMARY_LABELS"): "Minimo personal y familiar total",
    validated_casilla_id("0505", surface="modelo_100_pdf_fixture._SUMMARY_LABELS"): "Minimo del contribuyente",
    validated_casilla_id("0510", surface="modelo_100_pdf_fixture._SUMMARY_LABELS"): "Minimo por descendientes",
    validated_casilla_id("0515", surface="modelo_100_pdf_fixture._SUMMARY_LABELS"): "Minimo por ascendientes",
    validated_casilla_id("0520", surface="modelo_100_pdf_fixture._SUMMARY_LABELS"): "Minimo por discapacidad",
    validated_casilla_id("0545", surface="modelo_100_pdf_fixture._SUMMARY_LABELS"): "Base liquidable general",
    validated_casilla_id("0555", surface="modelo_100_pdf_fixture._SUMMARY_LABELS"): "Base liquidable del ahorro",
    validated_casilla_id("0550", surface="modelo_100_pdf_fixture._SUMMARY_LABELS"): "Cuota integra general estatal",
    validated_casilla_id("0551", surface="modelo_100_pdf_fixture._SUMMARY_LABELS"): "Cuota integra general autonomica",
    validated_casilla_id("0560", surface="modelo_100_pdf_fixture._SUMMARY_LABELS"): "Cuota integra del ahorro estatal",
    validated_casilla_id(
        "0561", surface="modelo_100_pdf_fixture._SUMMARY_LABELS"
    ): "Cuota integra del ahorro autonomica",
    validated_casilla_id("0595", surface="modelo_100_pdf_fixture._SUMMARY_LABELS"): "Cuota integra total",
    validated_casilla_id("0620", surface="modelo_100_pdf_fixture._SUMMARY_LABELS"): "Deducciones estatales",
    validated_casilla_id("0622", surface="modelo_100_pdf_fixture._SUMMARY_LABELS"): "Deducciones autonomicas",
    validated_casilla_id("0630", surface="modelo_100_pdf_fixture._SUMMARY_LABELS"): "Total deducciones",
    validated_casilla_id("0698", surface="modelo_100_pdf_fixture._SUMMARY_LABELS"): "Cuota liquida total",
    validated_casilla_id("0699", surface="modelo_100_pdf_fixture._SUMMARY_LABELS"): "Retenciones e ingresos a cuenta",
    validated_casilla_id(
        "0700", surface="modelo_100_pdf_fixture._SUMMARY_LABELS"
    ): "Pagos fraccionados (Modelo 130 / 131)",
    validated_casilla_id(
        "0720", surface="modelo_100_pdf_fixture._SUMMARY_LABELS"
    ): "Cuota resultante de la autoliquidacion",
    validated_casilla_id("0721", surface="modelo_100_pdf_fixture._SUMMARY_LABELS"): "Resultado a ingresar / a devolver",
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
    casilla_values: Mapping[CasillaId, Decimal]
    artefact_kind: str = Field(pattern=r"^(BORRADOR|PREDECLARACION|DECLARACION)$")
    csv: str | None = None  # required when artefact_kind == DECLARACION


class Modelo100GroundTruth(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    params: Modelo100GenParams
    expected_values_by_casilla_id: tuple[tuple[CasillaId, Decimal], ...]


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
    if params.artefact_kind == ArtefactKind.BORRADOR:
        y -= 5 * mm
        c.setFont("Helvetica-Bold", 12)
        c.drawString(MARGIN_LEFT, y, "BORRADOR")
    elif params.artefact_kind == ArtefactKind.PREDECLARACION:
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
    if params.artefact_kind == ArtefactKind.DECLARACION and params.csv is not None:
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
    ground_truth = Modelo100GroundTruth(params=params, expected_values_by_casilla_id=expected)
    return pdf_bytes, ground_truth


__all__ = [
    "Modelo100GenParams",
    "Modelo100GroundTruth",
    "format_amount",
    "generate",
]
