"""Typed read-only projection of a Modelo 390 filing.

Phase 1 declares the record shape only; the concrete parser that
projects :class:`aeat.remote.RemoteFiling` into :class:`FilingDetail390`
lands in Phase 2.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .._schema import RemoteFiling

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")


class FilingDetail390(BaseModel):
    """Casilla-level projection of a Modelo 390 annual VAT summary.

    Attributes:
        filing: Underlying :class:`aeat.remote.RemoteFiling` the detail
            record wraps.
        total_bases_devengado: Casilla 99 — sum of VAT bases accrued
            across every quarter of the exercise.
        total_cuotas_devengadas: Casilla 108 — sum of VAT cuotas
            accrued across the exercise.
        total_cuotas_deducibles: Casilla 511 — total VAT cuotas
            declared deductible on the annual summary.
        resultado_liquidacion_anual: Casilla 658 — annual settlement
            outcome.
        volumen_operaciones: Casilla 108bis equivalent — total
            operations volume declared on the summary.
        mode: Structural write-guard literal; always ``"read"``.
    """

    model_config = _STRICT_FROZEN

    filing: RemoteFiling
    total_bases_devengado: Decimal = Field(default=Decimal("0"))
    total_cuotas_devengadas: Decimal = Field(default=Decimal("0"))
    total_cuotas_deducibles: Decimal = Field(default=Decimal("0"))
    resultado_liquidacion_anual: Decimal = Field(default=Decimal("0"))
    volumen_operaciones: Decimal = Field(default=Decimal("0"))
    mode: Literal["read"] = "read"


__all__ = ["FilingDetail390"]
