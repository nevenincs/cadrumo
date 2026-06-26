"""Synthetic Modelo 130 declaración PDF generator.

Mirrors AEAT's real Modelo 130 layout closely enough that the same
label-anchored regex extractor designed for real AEAT PDFs succeeds
against our synthetic output. Ground-truth casilla values are provided
by the caller; the extractor's unit tests assert parse-output equals
input.

Usage:

    from .modelo_130_generator import Modelo130GenParams, generate

    params = Modelo130GenParams(
        año=2025,
        template_revision="2025.01",
        tax_id="00000000T",
        ejercicio="2025",
        period_printed="1T",
        casilla_values={_M130_INGRESOS_CASILLA: Decimal("12500.00"), ...},
    )
    pdf_bytes, ground_truth = generate(params)
"""

from __future__ import annotations

import io
from collections.abc import Mapping
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from ......domain.calculations.registry import CasillaId, validated_casilla_id
from ._generator_shared import (
    CasillaBox,
    draw_casilla_box,
    draw_footer,
    draw_header,
)

# Fixed Modelo 130 casilla ids + labels + positions on the synthetic
# A4 page. Positions roughly mirror AEAT's real form but are not
# pixel-identical — parity targets text content, not rendering.
#
# The casilla inventory is the full 19-casilla liquidación block.
# Casillas 01-07 keep their established y_mm positions; casillas
# 08-19 occupy y_mm=140..250 with a 10 mm vertical pitch.


def _casilla_id(value: object) -> CasillaId:
    return validated_casilla_id(value, surface="modelo_130_pdf_fixture._MODELO_130_BOXES")


_MODELO_130_BOXES: tuple[CasillaBox, ...] = (
    CasillaBox(casilla_id=_casilla_id("01"), label_es="Ingresos integros del periodo", x_mm=20, y_mm=60),
    CasillaBox(casilla_id=_casilla_id("02"), label_es="Gastos deducibles del periodo", x_mm=20, y_mm=70),
    CasillaBox(casilla_id=_casilla_id("03"), label_es="Rendimiento neto (01 - 02)", x_mm=20, y_mm=80),
    CasillaBox(casilla_id=_casilla_id("04"), label_es="Pago fraccionado bruto (20% de 03)", x_mm=20, y_mm=90),
    CasillaBox(casilla_id=_casilla_id("05"), label_es="Retenciones soportadas en el periodo", x_mm=20, y_mm=105),
    CasillaBox(
        casilla_id=_casilla_id("06"),
        label_es="Pagos fraccionados de periodos anteriores",
        x_mm=20,
        y_mm=115,
    ),
    CasillaBox(casilla_id=_casilla_id("07"), label_es="Resultado a ingresar (04 - 05 - 06)", x_mm=20, y_mm=125),
    CasillaBox(
        casilla_id=_casilla_id("08"),
        label_es="Volumen de ingresos del trimestre (Apartado II)",
        x_mm=20,
        y_mm=140,
    ),
    CasillaBox(casilla_id=_casilla_id("09"), label_es="Pago fraccionado bruto agraria (2% de 08)", x_mm=20, y_mm=150),
    CasillaBox(casilla_id=_casilla_id("10"), label_es="Retenciones del trimestre (Apartado II)", x_mm=20, y_mm=160),
    CasillaBox(casilla_id=_casilla_id("11"), label_es="Resultado parcial Apartado II (09 - 10)", x_mm=20, y_mm=170),
    CasillaBox(casilla_id=_casilla_id("12"), label_es="Suma de resultados parciales (clamp >= 0)", x_mm=20, y_mm=180),
    CasillaBox(casilla_id=_casilla_id("13"), label_es="Minoracion por rendimientos netos <= 12 000", x_mm=20, y_mm=190),
    CasillaBox(casilla_id=_casilla_id("14"), label_es="Neto tras minoracion (12 - 13)", x_mm=20, y_mm=200),
    CasillaBox(casilla_id=_casilla_id("15"), label_es="Arrastre de negativos trimestres anteriores", x_mm=20, y_mm=210),
    CasillaBox(
        casilla_id=_casilla_id("16"),
        label_es="Deduccion por inversion en vivienda habitual",
        x_mm=20,
        y_mm=220,
    ),
    CasillaBox(casilla_id=_casilla_id("17"), label_es="Diferencia (14 - 15 - 16)", x_mm=20, y_mm=230),
    CasillaBox(
        casilla_id=_casilla_id("18"),
        label_es="Resultado a ingresar de autoliquidaciones anteriores",
        x_mm=20,
        y_mm=240,
    ),
    CasillaBox(casilla_id=_casilla_id("19"), label_es="Resultado final (17 - 18)", x_mm=20, y_mm=250),
)


class Modelo130GenParams(BaseModel):
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


class Modelo130GroundTruth(BaseModel):
    """Ground truth paired with the generated PDF."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    params: Modelo130GenParams
    expected_values_by_casilla_id: tuple[tuple[CasillaId, Decimal], ...]


def generate(params: Modelo130GenParams) -> tuple[bytes, Modelo130GroundTruth]:
    """Render a synthetic Modelo 130 declaración as PDF bytes.

    Returns ``(pdf_bytes, ground_truth)``. Ground truth lists casillas
    in declaration order so extractor tests can walk them sequentially.
    """
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=(210 * mm, 297 * mm))
    c.setTitle(f"Modelo 130 {params.ejercicio} {params.period_printed}")

    draw_header(
        c,
        modelo="130",
        ejercicio=params.ejercicio,
        periodo=params.period_printed,
        page_num=1,
        page_count=1,
    )

    for box in _MODELO_130_BOXES:
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
        for box in _MODELO_130_BOXES
        if box.casilla_id in params.casilla_values
    )
    ground_truth = Modelo130GroundTruth(params=params, expected_values_by_casilla_id=expected)
    return pdf_bytes, ground_truth


__all__ = [
    "Modelo130GenParams",
    "Modelo130GroundTruth",
    "generate",
]
