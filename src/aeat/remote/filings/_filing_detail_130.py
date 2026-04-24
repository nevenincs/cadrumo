"""Typed read-only projection of a Modelo 130 filing.

Phase 1 declares the record shape only; the concrete parser that
projects :class:`aeat.remote.RemoteFiling` into :class:`FilingDetail130`
lands in Phase 2.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .._schema import RemoteFiling

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")


class FilingDetail130(BaseModel):
    """Casilla-level projection of a Modelo 130 filing as AEAT holds it.

    Attributes:
        filing: Underlying :class:`aeat.remote.RemoteFiling` the detail
            record wraps.
        ingresos_computables: Casilla 01 — computable income.
        gastos_deducibles: Casilla 02 — deductible expenses.
        rendimiento_neto: Casilla 03 — net yield for the period.
        pagos_fraccionados_anteriores: Casilla 06 — prior quarter
            fractional payments already lodged.
        retenciones_soportadas: Casilla 07 — retentions already borne.
        resultado: Casilla 08 — settlement outcome for the period.
        mode: Structural write-guard literal; always ``"read"``.
    """

    model_config = _STRICT_FROZEN

    filing: RemoteFiling
    ingresos_computables: Decimal = Field(default=Decimal("0"))
    gastos_deducibles: Decimal = Field(default=Decimal("0"))
    rendimiento_neto: Decimal = Field(default=Decimal("0"))
    pagos_fraccionados_anteriores: Decimal = Field(default=Decimal("0"))
    retenciones_soportadas: Decimal = Field(default=Decimal("0"))
    resultado: Decimal = Field(default=Decimal("0"))
    mode: Literal["read"] = "read"


__all__ = ["FilingDetail130"]
