"""Synthetic Modelo 303 declaración PDF generator.

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

from ......core import CasillaId, validated_casilla_id
from ._generator_shared import (
    CasillaBox,
    draw_casilla_box,
    draw_footer,
    draw_header,
)

# Modelo 303 has 33 casillas in the runtime schema; positions pack them
# across two "pages" of the synthetic PDF in declaration order. We keep
# them on page 1 because the extractor's ``_derive_status`` + line
# regex don't depend on page layout, only on line text.


_LABELS: Mapping[CasillaId, str] = {
    validated_casilla_id("01", surface="modelo_303_pdf_fixture._LABELS"): "Base imponible tipo general",
    validated_casilla_id("02", surface="modelo_303_pdf_fixture._LABELS"): "Tipo impositivo general (%)",
    validated_casilla_id("03", surface="modelo_303_pdf_fixture._LABELS"): "Cuota repercutida tipo general",
    validated_casilla_id("04", surface="modelo_303_pdf_fixture._LABELS"): "Base imponible tipo reducido",
    validated_casilla_id("05", surface="modelo_303_pdf_fixture._LABELS"): "Tipo impositivo reducido (%)",
    validated_casilla_id("06", surface="modelo_303_pdf_fixture._LABELS"): "Cuota repercutida tipo reducido",
    validated_casilla_id("07", surface="modelo_303_pdf_fixture._LABELS"): "Base imponible tipo superreducido",
    validated_casilla_id("08", surface="modelo_303_pdf_fixture._LABELS"): "Tipo impositivo superreducido (%)",
    validated_casilla_id("09", surface="modelo_303_pdf_fixture._LABELS"): "Cuota repercutida tipo superreducido",
    validated_casilla_id("28", surface="modelo_303_pdf_fixture._LABELS"): "Autoconsumo de bienes y servicios — base",
    validated_casilla_id("29", surface="modelo_303_pdf_fixture._LABELS"): "Autoconsumo de bienes y servicios — cuota",
    validated_casilla_id("30", surface="modelo_303_pdf_fixture._LABELS"): "Adquisiciones intracomunitarias — base",
    validated_casilla_id("31", surface="modelo_303_pdf_fixture._LABELS"): "Adquisiciones intracomunitarias — cuota",
    validated_casilla_id("32", surface="modelo_303_pdf_fixture._LABELS"): "Otros supuestos — base",
    validated_casilla_id("33", surface="modelo_303_pdf_fixture._LABELS"): "Otros supuestos — cuota",
    validated_casilla_id("34", surface="modelo_303_pdf_fixture._LABELS"): "IVA soportado operaciones interiores — base",
    validated_casilla_id(
        "35", surface="modelo_303_pdf_fixture._LABELS"
    ): "IVA soportado operaciones interiores — cuota",
    validated_casilla_id("36", surface="modelo_303_pdf_fixture._LABELS"): "IVA soportado importaciones — base",
    validated_casilla_id("37", surface="modelo_303_pdf_fixture._LABELS"): "IVA soportado importaciones — cuota",
    validated_casilla_id("38", surface="modelo_303_pdf_fixture._LABELS"): "IVA soportado intracomunitarias — base",
    validated_casilla_id("39", surface="modelo_303_pdf_fixture._LABELS"): "IVA soportado intracomunitarias — cuota",
    validated_casilla_id("40", surface="modelo_303_pdf_fixture._LABELS"): "IVA soportado bienes inversion — base",
    validated_casilla_id("41", surface="modelo_303_pdf_fixture._LABELS"): "IVA soportado bienes inversion — cuota",
    validated_casilla_id("42", surface="modelo_303_pdf_fixture._LABELS"): "Compensaciones régimen especial agrícola",
    validated_casilla_id("43", surface="modelo_303_pdf_fixture._LABELS"): "Regularización de bienes de inversión",
    validated_casilla_id("44", surface="modelo_303_pdf_fixture._LABELS"): "Suma IVA soportado deducible",
    validated_casilla_id(
        "45", surface="modelo_303_pdf_fixture._LABELS"
    ): "Resultado régimen general (cuotas devengadas - cuotas deducibles)",
    validated_casilla_id(
        "64", surface="modelo_303_pdf_fixture._LABELS"
    ): "Resultado de la liquidación antes de compensaciones",
    validated_casilla_id(
        "65", surface="modelo_303_pdf_fixture._LABELS"
    ): "Compensaciones de períodos anteriores aplicadas",
    validated_casilla_id("66", surface="modelo_303_pdf_fixture._LABELS"): "Resultado tras compensaciones",
    validated_casilla_id("67", surface="modelo_303_pdf_fixture._LABELS"): "Entregas intracomunitarias y exportaciones",
    validated_casilla_id("69", surface="modelo_303_pdf_fixture._LABELS"): "Resultado final antes del ingreso",
    validated_casilla_id("71", surface="modelo_303_pdf_fixture._LABELS"): "Resultado a ingresar / a devolver",
}

_IDS_IN_ORDER: tuple[CasillaId, ...] = tuple(_LABELS.keys())

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
    casilla_values: Mapping[CasillaId, Decimal]
    csv: str | None = None
    presented_at: str = "2025-04-20 10:00:00"


class Modelo303GroundTruth(BaseModel):
    """Ground truth paired with the generated PDF."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    params: Modelo303GenParams
    expected_values_by_casilla_id: tuple[tuple[CasillaId, Decimal], ...]


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
    ground_truth = Modelo303GroundTruth(params=params, expected_values_by_casilla_id=expected)
    return pdf_bytes, ground_truth


__all__ = [
    "Modelo303GenParams",
    "Modelo303GroundTruth",
    "generate",
]
