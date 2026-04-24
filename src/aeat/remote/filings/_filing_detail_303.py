"""Typed read-only projection of a Modelo 303 filing.

Phase 1 declares the record shape only; the concrete parser that
projects :class:`aeat.remote.RemoteFiling` into :class:`FilingDetail303`
lands in Phase 2.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .._schema import RemoteFiling

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")


class FilingDetail303(BaseModel):
    """Casilla-level projection of a Modelo 303 filing as AEAT holds it.

    Attributes:
        filing: Underlying :class:`aeat.remote.RemoteFiling` the detail
            record wraps.
        total_devengado: Casilla 27 — total VAT accrued this period.
        total_deducir: Casilla 45 — total VAT deductible this period.
        diferencia: Casilla 46 — difference between accrued and
            deductible VAT (the core reconciliation anchor).
        resultado_liquidacion: Casilla 69 — settlement outcome after
            regularisations and prior-quarter adjustments.
        a_ingresar: Casilla 71 — amount to pay AEAT, when positive.
        a_devolver: Casilla 73 — amount AEAT owes Kent, when positive.
        mode: Structural write-guard literal; always ``"read"``.
    """

    model_config = _STRICT_FROZEN

    filing: RemoteFiling
    total_devengado: Decimal = Field(default=Decimal("0"))
    total_deducir: Decimal = Field(default=Decimal("0"))
    diferencia: Decimal = Field(default=Decimal("0"))
    resultado_liquidacion: Decimal = Field(default=Decimal("0"))
    a_ingresar: Decimal = Field(default=Decimal("0"))
    a_devolver: Decimal = Field(default=Decimal("0"))
    mode: Literal["read"] = "read"


__all__ = ["FilingDetail303"]
